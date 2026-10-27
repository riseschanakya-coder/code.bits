import json
import os
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "users.db")))
DATABASE.parent.mkdir(parents=True, exist_ok=True)


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fullname TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                current_streak INTEGER NOT NULL DEFAULT 0,
                longest_streak INTEGER NOT NULL DEFAULT 0,
                last_solved_date TEXT,
                joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                difficulty TEXT NOT NULL,
                description TEXT NOT NULL,
                example_input TEXT NOT NULL,
                example_output TEXT NOT NULL,
                constraints_json TEXT NOT NULL DEFAULT '[]',
                function_signature TEXT,
                hidden_input TEXT,
                hidden_output TEXT,
                source TEXT NOT NULL DEFAULT 'seed',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS daily_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                question_date TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (question_id) REFERENCES questions(id)
            );

            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                language TEXT NOT NULL,
                source_code TEXT NOT NULL,
                verdict TEXT NOT NULL,
                execution_time REAL NOT NULL DEFAULT 0,
                submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (question_id) REFERENCES questions(id)
            );
            """
        )
        seed_questions(conn)
        ensure_seed_question_bank(conn)
        backfill_seed_hidden_tests(conn)


def backfill_seed_hidden_tests(conn):
    hidden_cases = {
        "Two Sum": (
            "nums = [3,2,4]\ntarget = 6",
            "[1,2]",
        ),
        "Valid Parentheses": (
            's = "([{}])"',
            "true",
        ),
        "Longest Substring Without Repeating Characters": (
            's = "bbbbb"',
            "1",
        ),
        "Merge Intervals": (
            "intervals = [[1,4],[4,5]]",
            "[[1,5]]",
        ),
        "Median of Two Sorted Arrays": (
            "nums1 = [1,2]\nnums2 = [3,4]",
            "2.5",
        ),
    }
    for title, (hidden_input, hidden_output) in hidden_cases.items():
        conn.execute(
            """
            UPDATE questions
            SET hidden_input = ?, hidden_output = ?
            WHERE title = ? AND source = 'seed' AND (hidden_input IS NULL OR hidden_input = '')
            """,
            (hidden_input, hidden_output, title),
        )


def seed_questions(conn):
    existing = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    if existing:
        return

    questions = [
        (
            "Two Sum",
            "Easy",
            "Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.",
            "nums = [2,7,11,15]\ntarget = 9",
            "[0,1]",
            "nums = [3,2,4]\ntarget = 6",
            "[1,2]",
            ["2 <= nums.length <= 10^4", "-10^9 <= nums[i] <= 10^9", "Exactly one valid answer exists."],
            "def two_sum(nums, target):",
        ),
        (
            "Valid Parentheses",
            "Easy",
            "Given a string containing only brackets, determine if the input string is valid.",
            's = "()[]{}"',
            "true",
            's = "([{}])"',
            "true",
            ["1 <= s.length <= 10^4", "s consists only of '(', ')', '{', '}', '[' and ']'."],
            "def is_valid(s):",
        ),
        (
            "Longest Substring Without Repeating Characters",
            "Medium",
            "Given a string s, find the length of the longest substring without repeating characters.",
            's = "abcabcbb"',
            "3",
            's = "bbbbb"',
            "1",
            ["0 <= s.length <= 5 * 10^4", "s may contain letters, digits, symbols, and spaces."],
            "def length_of_longest_substring(s):",
        ),
        (
            "Merge Intervals",
            "Medium",
            "Given an array of intervals, merge all overlapping intervals and return the non-overlapping intervals.",
            "intervals = [[1,3],[2,6],[8,10],[15,18]]",
            "[[1,6],[8,10],[15,18]]",
            "intervals = [[1,4],[4,5]]",
            "[[1,5]]",
            ["1 <= intervals.length <= 10^4", "intervals[i].length == 2"],
            "def merge(intervals):",
        ),
        (
            "Median of Two Sorted Arrays",
            "Hard",
            "Given two sorted arrays nums1 and nums2, return the median of the two sorted arrays.",
            "nums1 = [1,3]\nnums2 = [2]",
            "2.0",
            "nums1 = [1,2]\nnums2 = [3,4]",
            "2.5",
            ["0 <= nums1.length, nums2.length <= 1000", "The overall runtime complexity should be O(log(m+n))."],
            "def find_median_sorted_arrays(nums1, nums2):",
        ),
    ]

    conn.executemany(
        """
        INSERT INTO questions
        (title, difficulty, description, example_input, example_output, hidden_input, hidden_output,
         constraints_json, function_signature)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (q[0], q[1], q[2], q[3], q[4], q[5], q[6], json.dumps(q[7]), q[8])
            for q in questions
        ],
    )


def ensure_seed_question_bank(conn):
    questions = [
        (
            "Count Vowels",
            "Easy",
            "Given a string s, return the number of vowels in it. Treat both uppercase and lowercase vowels as vowels.",
            's = "CodeDaily"',
            "4",
            's = "rhythm"',
            "0",
            ["0 <= s.length <= 10^4", "Vowels are a, e, i, o, and u."],
            "def count_vowels(s):",
        ),
        (
            "Reverse Words",
            "Easy",
            "Given a sentence, return a new sentence with the order of words reversed. Keep single spaces between words.",
            'sentence = "learn python daily"',
            '"daily python learn"',
            'sentence = "code every day"',
            '"day every code"',
            ["1 <= sentence.length <= 10^4", "Words are separated by spaces."],
            "def reverse_words(sentence):",
        ),
        (
            "Find Maximum Number",
            "Easy",
            "Given a list of integers, return the largest number in the list.",
            "nums = [4, 9, 1, 12, 7]",
            "12",
            "nums = [-8, -3, -20]",
            "-3",
            ["1 <= nums.length <= 10^4"],
            "def find_maximum(nums):",
        ),
        (
            "Running Sum",
            "Easy",
            "Given a list of integers, return a list where each position contains the sum of all numbers up to that position.",
            "nums = [1, 2, 3, 4]",
            "[1, 3, 6, 10]",
            "nums = [5, -2, 7]",
            "[5, 3, 10]",
            ["1 <= nums.length <= 10^4"],
            "def running_sum(nums):",
        ),
        (
            "Is Palindrome",
            "Easy",
            "Given a string s, return True if it reads the same forward and backward. Ignore letter case.",
            's = "Madam"',
            "True",
            's = "Code"',
            "False",
            ["0 <= s.length <= 10^4"],
            "def is_palindrome(s):",
        ),
        (
            "Remove Duplicates",
            "Easy",
            "Given a list of integers, return a list with duplicate values removed while keeping the first occurrence order.",
            "nums = [1, 2, 2, 3, 1, 4]",
            "[1, 2, 3, 4]",
            "nums = [5, 5, 5]",
            "[5]",
            ["1 <= nums.length <= 10^4"],
            "def remove_duplicates(nums):",
        ),
        (
            "Second Largest",
            "Easy",
            "Given a list of unique integers, return the second largest number.",
            "nums = [10, 4, 8, 15, 2]",
            "10",
            "nums = [3, 1]",
            "1",
            ["2 <= nums.length <= 10^4", "All numbers are unique."],
            "def second_largest(nums):",
        ),
        (
            "FizzBuzz List",
            "Easy",
            "Given an integer n, return a list of strings from 1 to n. Use Fizz for multiples of 3, Buzz for multiples of 5, and FizzBuzz for both.",
            "n = 5",
            '["1", "2", "Fizz", "4", "Buzz"]',
            "n = 15",
            '["1", "2", "Fizz", "4", "Buzz", "Fizz", "7", "8", "Fizz", "Buzz", "11", "Fizz", "13", "14", "FizzBuzz"]',
            ["1 <= n <= 1000"],
            "def fizz_buzz(n):",
        ),
        (
            "Pair Sum Count",
            "Medium",
            "Given a list of integers and a target, return how many unique index pairs have values that add up to the target.",
            "nums = [1, 2, 3, 4, 5]\ntarget = 6",
            "2",
            "nums = [1, 1, 1, 1]\ntarget = 2",
            "6",
            ["1 <= nums.length <= 2000"],
            "def count_pairs(nums, target):",
        ),
        (
            "Most Frequent Number",
            "Medium",
            "Given a list of integers, return the number that appears most often. If there is a tie, return the smallest tied number.",
            "nums = [4, 2, 4, 3, 2, 4]",
            "4",
            "nums = [5, 1, 5, 1]",
            "1",
            ["1 <= nums.length <= 10^4"],
            "def most_frequent(nums):",
        ),
        (
            "Balanced Score",
            "Medium",
            "Given a list of daily scores, return the length of the longest streak where every score is at least target.",
            "scores = [7, 8, 4, 9, 10, 3]\ntarget = 7",
            "2",
            "scores = [5, 6, 7, 8]\ntarget = 5",
            "4",
            ["1 <= scores.length <= 10^4"],
            "def longest_good_streak(scores, target):",
        ),
        (
            "Compress String",
            "Medium",
            "Given a string, return a compressed version using character counts for consecutive repeated characters.",
            's = "aaabbc"',
            '"a3b2c1"',
            's = "abcd"',
            '"a1b1c1d1"',
            ["0 <= s.length <= 10^4"],
            "def compress_string(s):",
        ),
        (
            "Rotate List",
            "Medium",
            "Given a list and an integer k, rotate the list to the right by k positions.",
            "nums = [1, 2, 3, 4, 5]\nk = 2",
            "[4, 5, 1, 2, 3]",
            "nums = [10, 20, 30]\nk = 4",
            "[30, 10, 20]",
            ["0 <= nums.length <= 10^4", "0 <= k <= 10^5"],
            "def rotate_list(nums, k):",
        ),
        (
            "Missing Number",
            "Medium",
            "Given a list containing n distinct numbers from 0 to n, return the missing number.",
            "nums = [3, 0, 1]",
            "2",
            "nums = [0, 1]",
            "2",
            ["1 <= nums.length <= 10^4"],
            "def missing_number(nums):",
        ),
        (
            "Group Anagrams",
            "Medium",
            "Given a list of lowercase words, group words that are anagrams. Return the groups with words in their original order.",
            'words = ["eat", "tea", "tan", "ate", "nat", "bat"]',
            '[["eat", "tea", "ate"], ["tan", "nat"], ["bat"]]',
            'words = ["abc", "bca", "cab", "dog"]',
            '[["abc", "bca", "cab"], ["dog"]]',
            ["1 <= words.length <= 1000"],
            "def group_anagrams(words):",
        ),
    ]

    existing_titles = {
        row["title"]
        for row in conn.execute("SELECT title FROM questions WHERE source = 'seed'").fetchall()
    }
    missing = [q for q in questions if q[0] not in existing_titles]
    if not missing:
        return

    conn.executemany(
        """
        INSERT INTO questions
        (title, difficulty, description, example_input, example_output, hidden_input, hidden_output,
         constraints_json, function_signature, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'seed')
        """,
        [
            (q[0], q[1], q[2], q[3], q[4], q[5], q[6], json.dumps(q[7]), q[8])
            for q in missing
        ],
    )


def row_to_question(row):
    if row is None:
        return None
    item = dict(row)
    item["constraints"] = json.loads(item.pop("constraints_json") or "[]")
    return item


def get_user(user_id):
    with get_db() as conn:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_all_questions():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM questions ORDER BY difficulty, title").fetchall()
    return [row_to_question(row) for row in rows]


def get_daily_question_archive():
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT q.*, d.question_date
            FROM daily_questions d
            JOIN questions q ON q.id = d.question_id
            ORDER BY d.question_date DESC
            """
        ).fetchall()
    return [row_to_question(row) for row in rows]


def get_question(question_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM questions WHERE id = ?", (question_id,)).fetchone()
    return row_to_question(row)


def create_question(question_data, source="ai"):
    constraints = question_data.get("constraints") or []
    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO questions
            (title, difficulty, description, example_input, example_output, constraints_json,
             function_signature, hidden_input, hidden_output, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                question_data.get("title", "Untitled Challenge"),
                question_data.get("difficulty", "Medium"),
                question_data.get("description", ""),
                question_data.get("example_input", ""),
                question_data.get("example_output", ""),
                json.dumps(constraints),
                question_data.get("function_signature", ""),
                question_data.get("hidden_input"),
                question_data.get("hidden_output"),
                source,
            ),
        )
        return cursor.lastrowid


def get_fallback_seed_question():
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT q.*, MAX(d.question_date) AS last_daily_date
            FROM questions q
            LEFT JOIN daily_questions d ON d.question_id = q.id
            WHERE q.source = 'seed'
            GROUP BY q.id
            ORDER BY COALESCE(last_daily_date, ''), q.id
            """
        ).fetchall()
    if not rows:
        return None
    return row_to_question(rows[0])


def assign_daily_question(question_id):
    today = date.today().isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO daily_questions (question_id, question_date) VALUES (?, ?)",
            (question_id, today),
        )


def get_or_create_daily_question(question_data_factory):
    today = date.today().isoformat()
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT q.* FROM daily_questions d
            JOIN questions q ON q.id = d.question_id
            WHERE d.question_date = ?
            """,
            (today,),
        ).fetchone()
        if row:
            return row_to_question(row), None

    question_data, error = question_data_factory()
    if error:
        fallback = get_fallback_seed_question()
        if fallback:
            assign_daily_question(fallback["id"])
            return fallback, None
        return None, error

    question_id = create_question(question_data, source="ai")
    assign_daily_question(question_id)
    return get_question(question_id), None


def user_stats(user_id):
    today = date.today().isoformat()
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        totals = conn.execute(
            """
            SELECT
                COUNT(*) AS total_submissions,
                SUM(CASE WHEN verdict = 'Accepted' THEN 1 ELSE 0 END) AS accepted_submissions
            FROM submissions WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        solved = conn.execute(
            """
            SELECT q.difficulty, COUNT(DISTINCT s.question_id) AS count
            FROM submissions s
            JOIN questions q ON q.id = s.question_id
            WHERE s.user_id = ? AND s.verdict = 'Accepted'
            GROUP BY q.difficulty
            """,
            (user_id,),
        ).fetchall()
        today_status = conn.execute(
            """
            SELECT 1 FROM submissions s
            JOIN daily_questions d ON d.question_id = s.question_id
            WHERE s.user_id = ? AND s.verdict = 'Accepted' AND d.question_date = ?
            LIMIT 1
            """,
            (user_id, today),
        ).fetchone()
        recent = conn.execute(
            """
            SELECT s.*, q.title, q.difficulty
            FROM submissions s
            JOIN questions q ON q.id = s.question_id
            WHERE s.user_id = ?
            ORDER BY s.submitted_at DESC
            LIMIT 8
            """,
            (user_id,),
        ).fetchall()
        rank_row = conn.execute(
            """
            SELECT COUNT(*) + 1 AS rank FROM (
                SELECT user_id, COUNT(DISTINCT question_id) solved
                FROM submissions
                WHERE verdict = 'Accepted'
                GROUP BY user_id
                HAVING solved > (
                    SELECT COUNT(DISTINCT question_id)
                    FROM submissions
                    WHERE user_id = ? AND verdict = 'Accepted'
                )
            )
            """,
            (user_id,),
        ).fetchone()

    difficulty_counts = {"Easy": 0, "Medium": 0, "Hard": 0}
    for row in solved:
        difficulty_counts[row["difficulty"]] = row["count"]

    total_submissions = totals["total_submissions"] or 0
    accepted = totals["accepted_submissions"] or 0
    accuracy = round((accepted / total_submissions) * 100, 1) if total_submissions else 0

    current_streak = user["current_streak"] if user else 0
    last_solved = user["last_solved_date"] if user else None
    if last_solved:
        last_date = datetime.strptime(last_solved, "%Y-%m-%d").date()
        if last_date < date.today() - timedelta(days=1):
            current_streak = 0

    return {
        "questions_solved": sum(difficulty_counts.values()),
        "easy_solved": difficulty_counts["Easy"],
        "medium_solved": difficulty_counts["Medium"],
        "hard_solved": difficulty_counts["Hard"],
        "total_submissions": total_submissions,
        "accuracy": accuracy,
        "current_streak": current_streak,
        "longest_streak": user["longest_streak"] if user else 0,
        "today_solved": bool(today_status),
        "global_rank": rank_row["rank"] if rank_row else 1,
        "recent_activity": recent,
    }


def mark_daily_solved_if_needed(user_id, question_id, verdict):
    if verdict != "Accepted":
        return
    today = date.today().isoformat()
    with get_db() as conn:
        is_daily = conn.execute(
            "SELECT 1 FROM daily_questions WHERE question_id = ? AND question_date = ?",
            (question_id, today),
        ).fetchone()
        if not is_daily:
            return
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user["last_solved_date"] == today:
            return
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        streak = user["current_streak"] + 1 if user["last_solved_date"] == yesterday else 1
        conn.execute(
            """
            UPDATE users
            SET current_streak = ?, longest_streak = MAX(longest_streak, ?), last_solved_date = ?
            WHERE id = ?
            """,
            (streak, streak, today, user_id),
        )


def record_submission(user_id, question_id, language, source_code, verdict, execution_time):
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO submissions (user_id, question_id, language, source_code, verdict, execution_time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, question_id, language, source_code, verdict, execution_time),
        )
    mark_daily_solved_if_needed(user_id, question_id, verdict)
