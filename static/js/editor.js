const layout = document.querySelector(".coding-layout");
const language = document.querySelector("#language");
const sourceCode = document.querySelector("#source-code");
const runBtn = document.querySelector("#run-btn");
const submitBtn = document.querySelector("#submit-btn");
const output = document.querySelector("#output");
const verdict = document.querySelector("#verdict");
const streakCounts = document.querySelectorAll(".js-streak-count");
const todayStatus = document.querySelector(".js-today-status");

const starterCode = {
  python: 'def solve():\n    return "Hello CodeDaily"\n\nprint(solve())',
  c: '#include <stdio.h>\n\nint main() {\n    printf("Hello CodeDaily\\n");\n    return 0;\n}',
  cpp: '#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    cout << "Hello CodeDaily" << endl;\n    return 0;\n}',
  java: 'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello CodeDaily");\n    }\n}',
};

function pythonStarterFromSignature(signature) {
  if (!signature) return starterCode.python;
  const trimmed = signature.trim();
  if (!trimmed.endsWith(":")) {
    return `${trimmed}:\n    # write your logic here\n    return None\n`;
  }
  return `${trimmed}\n    # write your logic here\n    return None\n`;
}

if (layout && sourceCode) {
  const signature = layout.dataset.functionSignature;
  if (signature) {
    sourceCode.value = pythonStarterFromSignature(signature);
    if (language) {
      language.value = "python";
    }
  } else {
    sourceCode.value = starterCode.python;
  }
}

if (language && sourceCode) {
  language.addEventListener("change", () => {
    const signature = layout?.dataset.functionSignature;
    if (language.value === "python" && signature) {
      sourceCode.value = pythonStarterFromSignature(signature);
      return;
    }
    sourceCode.value = starterCode[language.value] || "";
  });
}

async function sendCode(endpoint) {
  if (!layout) return;
  const button = endpoint.includes("submit") ? submitBtn : runBtn;
  button.disabled = true;
  verdict.textContent = "Running";
  output.textContent = "Executing...";

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question_id: layout.dataset.questionId,
        language: language.value,
        source_code: sourceCode.value,
      }),
    });
    const result = await response.json();
    verdict.textContent = `${result.verdict} | ${result.execution_time}s`;
    output.textContent = [result.output, result.errors].filter(Boolean).join("\n") || "No output";
    if (endpoint.includes("submit") && result.stats) {
      streakCounts.forEach((item) => {
        item.textContent = result.stats.current_streak;
      });
      if (todayStatus) {
        todayStatus.textContent = result.stats.today_solved ? "Solved" : "Submit to solve";
      }
      if (result.verdict === "Accepted") {
        output.textContent = `${output.textContent}\n\nGreat job. Your streak is now ${result.stats.current_streak} day${result.stats.current_streak === 1 ? "" : "s"}.`;
      }
    }
  } catch (error) {
    verdict.textContent = "Error";
    output.textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

if (runBtn) runBtn.addEventListener("click", () => sendCode("/api/run"));
if (submitBtn) submitBtn.addEventListener("click", () => sendCode("/api/submit"));
