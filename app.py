import ast
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, g, jsonify, redirect, render_template, request, session, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from database import (
    get_all_questions,
    get_daily_question_archive,
    get_db,
    get_or_create_daily_question,
    get_question,
    get_user,
    init_db,
    record_submission,
    user_stats,
)

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "change-this-secret-key")
init_db()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def get_question_from_ai():
    try:
        from google import genai

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None, "Gemini API key is missing. Add GEMINI_API_KEY to your .env file."

        client = genai.Client(api_key=api_key)
        today_label = time.strftime("%Y-%m-%d")
        prompt = f"""
Generate ONE original beginner-friendly coding practice question for {today_label}.
The question must be different from common classics like Two Sum, Valid Parentheses, Merge Intervals, and FizzBuzz.
It should be solvable with a single Python function and have clear examples for a new programmer.
Return ONLY valid JSON with this exact shape:
{{
  "title": "",
  "difficulty": "Easy | Medium | Hard",
  "description": "",
  "example_input": "variable assignments, one per line, e.g. nums = [2,7,11,15]\\ntarget = 9",
  "example_output": "the expected return value as a Python literal string",
  "hidden_input": "a second test case using the same variable format",
  "hidden_output": "expected output for hidden_input",
  "constraints": [],
  "function_signature": "def function_name(param1, param2):"
}}
"""
        response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        text = response.text.strip().replace("```json", "").replace("```", "").strip()
        data = json.loads(text)
        required = {
            "title",
            "difficulty",
            "description",
            "example_input",
            "example_output",
            "hidden_input",
            "hidden_output",
            "constraints",
            "function_signature",
        }
        if not required.issubset(data):
            return None, "Gemini returned an incomplete question. Please try again later."
        return data, None
    except Exception as exc:
        return None, f"Could not generate today's AI question right now: {exc}"


def normalize_output(value):
    return "\n".join(line.rstrip() for line in (value or "").strip().splitlines()).strip()


def parse_example_bindings(example_input):
    bindings = {}
    for line in (example_input or "").strip().splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        value = value.strip()
        if not name:
            continue
        bindings[name] = ast.literal_eval(value)
    return bindings


def extract_function_info(signature):
    match = re.match(r"def\s+(\w+)\s*\((.*?)\)\s*:", (signature or "").strip())
    if not match:
        return None, []
    params = [
        part.strip().split("=")[0].strip()
        for part in match.group(2).split(",")
        if part.strip()
    ]
    return match.group(1), params


def wrap_python_solution(source_code, example_input, function_signature):
    func_name, param_names = extract_function_info(function_signature)
    if not func_name or not param_names:
        return source_code, None

    bindings = parse_example_bindings(example_input)
    missing = [name for name in param_names if name not in bindings]
    if missing:
        return source_code, f"Could not parse example input for: {', '.join(missing)}"

    setup = "\n".join(f"{name} = {repr(value)}" for name, value in bindings.items())
    args = ", ".join(param_names)
    wrapped = (
        f"{source_code.rstrip()}\n\n"
        f"{setup}\n"
        f"_result = {func_name}({args})\n"
        f"print(_result)\n"
    )
    return wrapped, None


def outputs_match(actual, expected):
    actual_norm = normalize_output(actual)
    expected_norm = normalize_output(expected)
    if actual_norm.lower() in {"true", "false"} and expected_norm.lower() in {"true", "false"}:
        return actual_norm.lower() == expected_norm.lower()
    try:
        return ast.literal_eval(actual_norm) == ast.literal_eval(expected_norm)
    except (ValueError, SyntaxError):
        pass
    return actual_norm == expected_norm


def prepare_source(language, source_code, example_input, function_signature):
    language = language.lower()
    if language != "python" or not function_signature:
        return source_code, None
    return wrap_python_solution(source_code, example_input, function_signature)


def run_code(language, source_code, stdin_text, expected_output=None, function_signature=None):
    start = time.perf_counter()
    language = language.lower()
    prepared, prep_error = prepare_source(language, source_code, stdin_text, function_signature)
    if prep_error:
        return {
            "output": "",
            "errors": prep_error,
            "execution_time": 0,
            "verdict": "Error",
        }

    try:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            if language == "python":
                code_file = temp_path / "main.py"
                code_file.write_text(prepared, encoding="utf-8")
                command = [sys.executable, str(code_file)]
            elif language == "c":
                if function_signature:
                    return {
                        "output": "",
                        "errors": "Function-based problems are currently supported in Python only.",
                        "execution_time": 0,
                        "verdict": "Error",
                    }
                code_file = temp_path / "main.c"
                exe_file = temp_path / "main.exe"
                code_file.write_text(source_code, encoding="utf-8")
                compile_proc = subprocess.run(
                    ["gcc", str(code_file), "-O2", "-o", str(exe_file)],
                    capture_output=True,
                    text=True,
                    timeout=8,
                )
                if compile_proc.returncode:
                    return {"output": "", "errors": compile_proc.stderr, "execution_time": 0, "verdict": "Compile Error"}
                command = [str(exe_file)]
            elif language == "cpp":
                if function_signature:
                    return {
                        "output": "",
                        "errors": "Function-based problems are currently supported in Python only.",
                        "execution_time": 0,
                        "verdict": "Error",
                    }
                code_file = temp_path / "main.cpp"
                exe_file = temp_path / "main.exe"
                code_file.write_text(source_code, encoding="utf-8")
                compile_proc = subprocess.run(
                    ["g++", str(code_file), "-O2", "-std=c++17", "-o", str(exe_file)],
                    capture_output=True,
                    text=True,
                    timeout=8,
                )
                if compile_proc.returncode:
                    return {"output": "", "errors": compile_proc.stderr, "execution_time": 0, "verdict": "Compile Error"}
                command = [str(exe_file)]
            elif language == "java":
                if function_signature:
                    return {
                        "output": "",
                        "errors": "Function-based problems are currently supported in Python only.",
                        "execution_time": 0,
                        "verdict": "Error",
                    }
                code_file = temp_path / "Main.java"
                code_file.write_text(source_code, encoding="utf-8")
                compile_proc = subprocess.run(
                    ["javac", str(code_file)],
                    cwd=temp,
                    capture_output=True,
                    text=True,
                    timeout=8,
                )
                if compile_proc.returncode:
                    return {"output": "", "errors": compile_proc.stderr, "execution_time": 0, "verdict": "Compile Error"}
                command = ["java", "-cp", temp, "Main"]
            else:
                return {"output": "", "errors": "Unsupported language.", "execution_time": 0, "verdict": "Error"}

            proc = subprocess.run(
                command,
                input=stdin_text if not function_signature or language != "python" else None,
                capture_output=True,
                text=True,
                timeout=5,
            )
            elapsed = round(time.perf_counter() - start, 4)
            verdict = "Runtime Error" if proc.returncode else "Accepted"
            if expected_output is not None and proc.returncode == 0:
                verdict = "Accepted" if outputs_match(proc.stdout, expected_output) else "Wrong Answer"
            return {
                "output": proc.stdout,
                "errors": proc.stderr,
                "execution_time": elapsed,
                "verdict": verdict,
            }
    except subprocess.TimeoutExpired:
        return {"output": "", "errors": "Execution timed out.", "execution_time": 5, "verdict": "Time Limit Exceeded"}
    except FileNotFoundError as exc:
        return {
            "output": "",
            "errors": f"Compiler or runtime is not installed: {exc.filename}",
            "execution_time": 0,
            "verdict": "Environment Error",
        }


@app.context_processor
def inject_user():
    if not session.get("user_id"):
        return {"current_user": None, "current_stats": None}
    user = get_user(session["user_id"])
    return {"current_user": user, "current_stats": user_stats(session["user_id"])}


@app.route("/")
def home():
    return redirect(url_for("dashboard") if session.get("user_id") else url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    message = ""
    if request.method == "POST":
        fullname = request.form.get("fullname", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if len(password) < 6:
            message = "Password must be at least 6 characters."
        else:
            try:
                with get_db() as conn:
                    conn.execute(
                        "INSERT INTO users (fullname, email, password) VALUES (?, ?, ?)",
                        (fullname, email, generate_password_hash(password)),
                    )
                return redirect(url_for("login", registered="1"))
            except Exception:
                message = "That email is already registered."
    return render_template("register.html", message=message)


@app.route("/login", methods=["GET", "POST"])
def login():
    message = "Registration successful. Please log in." if request.args.get("registered") else ""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password"], password):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))
        message = "Invalid email or password."
    return render_template("login.html", message=message)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    stats = user_stats(session["user_id"])
    return render_template("dashboard.html", stats=stats)


@app.route("/daily-question")
@login_required
def daily_question():
    question, error = get_or_create_daily_question(get_question_from_ai)
    return render_template(
        "daily_question.html",
        question=question,
        error=error,
        page_label="Today's Question",
        stats=user_stats(session["user_id"]),
        is_daily=True,
    )


@app.route("/problems/<int:question_id>")
@login_required
def practice_question(question_id):
    question = get_question(question_id)
    if not question:
        return redirect(url_for("problems"))
    return render_template(
        "daily_question.html",
        question=question,
        error=None,
        page_label="Practice Problem",
        stats=user_stats(session["user_id"]),
        is_daily=False,
    )


@app.route("/problems")
@login_required
def problems():
    library = get_all_questions()
    archive = get_daily_question_archive()
    stats = user_stats(session["user_id"])
    solved_ids = set()
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT question_id FROM submissions WHERE user_id = ? AND verdict = 'Accepted'",
            (session["user_id"],),
        ).fetchall()
        solved_ids = {row["question_id"] for row in rows}
    return render_template(
        "problems.html",
        library=library,
        questions=archive,
        solved_ids=solved_ids,
        stats=stats,
    )


@app.route("/profile")
@login_required
def profile():
    user = get_user(session["user_id"])
    stats = user_stats(session["user_id"])
    return render_template("profile.html", user=user, stats=stats)


@app.route("/api/run", methods=["POST"])
@login_required
def api_run():
    payload = request.get_json(force=True)
    question = get_question(payload.get("question_id"))
    if not question:
        return jsonify({"verdict": "Error", "errors": "Question not found.", "output": "", "execution_time": 0}), 404
    result = run_code(
        payload.get("language", "python"),
        payload.get("source_code", ""),
        question["example_input"],
        function_signature=question.get("function_signature"),
    )
    return jsonify(result)


@app.route("/api/submit", methods=["POST"])
@login_required
def api_submit():
    payload = request.get_json(force=True)
    question = get_question(payload.get("question_id"))
    if not question:
        return jsonify({"verdict": "Error", "errors": "Question not found.", "output": "", "execution_time": 0}), 404

    test_input = question.get("hidden_input") or question["example_input"]
    expected = question.get("hidden_output") or question["example_output"]
    result = run_code(
        payload.get("language", "python"),
        payload.get("source_code", ""),
        test_input,
        expected,
        function_signature=question.get("function_signature"),
    )
    record_submission(
        session["user_id"],
        question["id"],
        payload.get("language", "python"),
        payload.get("source_code", ""),
        result["verdict"],
        result["execution_time"],
    )
    stats = user_stats(session["user_id"])
    result["stats"] = {
        "current_streak": stats["current_streak"],
        "longest_streak": stats["longest_streak"],
        "today_solved": stats["today_solved"],
        "questions_solved": stats["questions_solved"],
        "accuracy": stats["accuracy"],
    }
    return jsonify(result)


def mobile_token_serializer():
    return URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="codedaily-mobile-auth")


def mobile_auth_response(user):
    return jsonify(
        {
            "token": mobile_token_serializer().dumps({"user_id": user["id"]}),
            "user": {
                "id": user["id"],
                "fullname": user["fullname"],
                "email": user["email"],
            },
        }
    )


def mobile_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return jsonify({"error": "Please log in to continue."}), 401

        try:
            claims = mobile_token_serializer().loads(
                authorization.removeprefix("Bearer "),
                max_age=60 * 60 * 24 * 30,
            )
        except (BadSignature, SignatureExpired):
            return jsonify({"error": "Your session expired. Please log in again."}), 401

        user_id = claims.get("user_id")
        if not isinstance(user_id, int) or not get_user(user_id):
            return jsonify({"error": "Please log in to continue."}), 401

        g.mobile_user_id = user_id
        return view(*args, **kwargs)

    return wrapped


def mobile_public_question(question):
    if not question:
        return None
    fields = (
        "id",
        "title",
        "difficulty",
        "description",
        "example_input",
        "example_output",
        "constraints",
        "function_signature",
        "question_date",
    )
    return {key: question[key] for key in fields if key in question}


def mobile_stats(user_id):
    stats = user_stats(user_id)
    stats["recent_activity"] = [dict(item) for item in stats["recent_activity"]]
    return stats


@app.route("/api/mobile/register", methods=["POST"])
def mobile_register():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "A JSON request body is required."}), 400

    fullname = str(payload.get("fullname", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    if not fullname or "@" not in email:
        return jsonify({"error": "Enter your name and a valid email address."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    try:
        with get_db() as conn:
            cursor = conn.execute(
                "INSERT INTO users (fullname, email, password) VALUES (?, ?, ?)",
                (fullname, email, generate_password_hash(password)),
            )
            user = conn.execute(
                "SELECT id, fullname, email FROM users WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
    except sqlite3.IntegrityError:
        return jsonify({"error": "That email is already registered."}), 409

    return mobile_auth_response(user), 201


@app.route("/api/mobile/login", methods=["POST"])
def mobile_login():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "A JSON request body is required."}), 400

    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not user or not check_password_hash(user["password"], password):
        return jsonify({"error": "Invalid email or password."}), 401
    return mobile_auth_response(user)


@app.route("/api/mobile/dashboard")
@mobile_login_required
def mobile_dashboard():
    user = get_user(g.mobile_user_id)
    return jsonify(
        {
            "user": {"fullname": user["fullname"]},
            "stats": mobile_stats(g.mobile_user_id),
        }
    )


@app.route("/api/mobile/questions")
@mobile_login_required
def mobile_questions():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT question_id FROM submissions WHERE user_id = ? AND verdict = 'Accepted'",
            (g.mobile_user_id,),
        ).fetchall()
    return jsonify(
        {
            "library": [mobile_public_question(q) for q in get_all_questions()],
            "archive": [
                mobile_public_question(q) for q in get_daily_question_archive()
            ],
            "solved_ids": [row["question_id"] for row in rows],
        }
    )


@app.route("/api/mobile/questions/daily")
@mobile_login_required
def mobile_daily_question():
    question, error = get_or_create_daily_question(get_question_from_ai)
    if not question:
        return jsonify({"error": error or "Today's question is not available yet."}), 503
    return jsonify(
        {
            "question": mobile_public_question(question),
            "stats": mobile_stats(g.mobile_user_id),
            "is_daily": True,
        }
    )


@app.route("/api/mobile/questions/<int:question_id>")
@mobile_login_required
def mobile_question(question_id):
    question = get_question(question_id)
    if not question:
        return jsonify({"error": "Question not found."}), 404
    return jsonify(
        {
            "question": mobile_public_question(question),
            "is_daily": False,
        }
    )


@app.route("/api/mobile/profile")
@mobile_login_required
def mobile_profile():
    user = get_user(g.mobile_user_id)
    return jsonify(
        {
            "user": {
                "fullname": user["fullname"],
                "email": user["email"],
                "joined_at": user["joined_at"],
            },
            "stats": mobile_stats(g.mobile_user_id),
        }
    )


@app.route("/api/mobile/run", methods=["POST"])
@mobile_login_required
def mobile_run():
    return mobile_execute_code(submit=False)


@app.route("/api/mobile/submit", methods=["POST"])
@mobile_login_required
def mobile_submit():
    return mobile_execute_code(submit=True)


def mobile_execute_code(submit):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "A JSON request body is required."}), 400
    try:
        question_id = int(payload.get("question_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "A valid question ID is required."}), 400

    question = get_question(question_id)
    if not question:
        return jsonify({"error": "Question not found."}), 404

    language = str(payload.get("language", "python")).lower()
    source_code = payload.get("source_code", "")
    if language not in {"python", "c", "cpp", "java"} or not isinstance(source_code, str):
        return jsonify({"error": "Choose a supported language and provide source code."}), 400

    test_input = question["example_input"]
    expected = None
    if submit:
        test_input = question.get("hidden_input") or question["example_input"]
        expected = question.get("hidden_output") or question["example_output"]

    result = run_code(
        language,
        source_code,
        test_input,
        expected,
        function_signature=question.get("function_signature"),
    )
    if submit:
        record_submission(
            g.mobile_user_id,
            question["id"],
            language,
            source_code,
            result["verdict"],
            result["execution_time"],
        )
        result["stats"] = mobile_stats(g.mobile_user_id)
    return jsonify(result)


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG") == "1",
    )
