package com.codedaily.app;

import android.app.Activity;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final int GREEN = Color.rgb(22, 138, 74);
    private static final int TEXT = Color.rgb(23, 32, 51);
    private static final int MUTED = Color.rgb(101, 113, 134);
    private static final int PANEL = Color.WHITE;

    private final ExecutorService network = Executors.newSingleThreadExecutor();
    private final Handler mainThread = new Handler(Looper.getMainLooper());
    private String token;
    private String currentScreen = "login";
    private String previousScreen = "dashboard";
    private LinearLayout pageBody;

    private interface ApiCallback {
        void onResult(JSONObject result, int statusCode);
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        token = getPreferences(MODE_PRIVATE).getString("auth_token", null);
        if (token == null) {
            showLogin(null);
        } else {
            showDashboard();
            callApi("GET", "/api/mobile/dashboard", null, (result, status) -> {
                if (status == 200) {
                    renderDashboard(result);
                } else {
                    showLogin(result.optString("error", "Could not connect to CodeDaily."));
                }
            });
        }
    }

    private void callApi(String method, String path, JSONObject payload, ApiCallback callback) {
        network.execute(() -> {
            HttpURLConnection connection = null;
            JSONObject result;
            int status = 0;
            try {
                String baseUrl = BuildConfig.CODEDAILY_URL.replaceAll("/+$", "");
                connection = (HttpURLConnection) new URL(baseUrl + path).openConnection();
                connection.setRequestMethod(method);
                connection.setConnectTimeout(20000);
                connection.setReadTimeout(60000);
                connection.setRequestProperty("Accept", "application/json");
                if (token != null && !token.isEmpty()) {
                    connection.setRequestProperty("Authorization", "Bearer " + token);
                }
                if (payload != null) {
                    connection.setDoOutput(true);
                    connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                    byte[] body = payload.toString().getBytes(StandardCharsets.UTF_8);
                    try (OutputStream output = connection.getOutputStream()) {
                        output.write(body);
                    }
                }

                status = connection.getResponseCode();
                InputStream stream = status >= 400
                        ? connection.getErrorStream()
                        : connection.getInputStream();
                result = new JSONObject(readStream(stream));
            } catch (IOException | JSONException exception) {
                result = new JSONObject();
                try {
                    result.put("error", "Could not reach CodeDaily. Check your internet connection.");
                } catch (JSONException ignored) {
                    result = new JSONObject();
                }
            } finally {
                if (connection != null) {
                    connection.disconnect();
                }
            }

            JSONObject response = result;
            int responseStatus = status;
            mainThread.post(() -> {
                if (responseStatus == 401 && !path.endsWith("/login") && !path.endsWith("/register")) {
                    clearToken();
                    showLogin(response.optString("error", "Please log in again."));
                    return;
                }
                callback.onResult(response, responseStatus);
            });
        });
    }

    private String readStream(InputStream stream) throws IOException {
        if (stream == null) {
            return "{}";
        }
        try (InputStream input = stream; ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096];
            int count;
            while ((count = input.read(buffer)) != -1) {
                output.write(buffer, 0, count);
            }
            return output.toString(StandardCharsets.UTF_8.name());
        }
    }

    private JSONObject json(Object... values) {
        JSONObject result = new JSONObject();
        try {
            for (int index = 0; index < values.length; index += 2) {
                result.put((String) values[index], values[index + 1]);
            }
        } catch (JSONException exception) {
            throw new IllegalStateException("Could not create request data.", exception);
        }
        return result;
    }

    private void showLogin(String message) {
        currentScreen = "login";
        LinearLayout content = newPage("CodeDaily", false);
        addText(content, "Welcome back", 28, true, TEXT);
        addText(content, "Log in to continue your daily coding streak.", 16, false, MUTED);
        EditText email = addInput(content, "Email", InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS);
        EditText password = addInput(content, "Password", InputType.TYPE_TEXT_VARIATION_PASSWORD);
        password.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        if (message != null && !message.isEmpty()) {
            addText(content, message, 14, false, Color.rgb(185, 28, 28));
        }

        Button loginButton = addButton(content, "Log in");
        loginButton.setOnClickListener(view -> {
            loginButton.setEnabled(false);
            callApi("POST", "/api/mobile/login",
                    json("email", email.getText().toString().trim(),
                            "password", password.getText().toString()),
                    (result, status) -> {
                        loginButton.setEnabled(true);
                        if (status == 200) {
                            saveToken(result.optString("token", ""));
                            showDashboard();
                            loadDashboard();
                        } else {
                            showLogin(result.optString("error", "Could not log in."));
                        }
                    });
        });

        Button registerButton = addTextButton(content, "Create an account");
        registerButton.setOnClickListener(view -> showRegister());
    }

    private void showRegister() {
        showRegister(null);
    }

    private void showRegister(String message) {
        currentScreen = "register";
        LinearLayout content = newPage("Create account", false);
        addText(content, "Start your coding streak", 26, true, TEXT);
        EditText fullname = addInput(content, "Full name", InputType.TYPE_TEXT_VARIATION_PERSON_NAME);
        EditText email = addInput(content, "Email", InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS);
        EditText password = addInput(content, "Password (at least 6 characters)",
                InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        if (message != null && !message.isEmpty()) {
            addText(content, message, 14, false, Color.rgb(185, 28, 28));
        }
        Button registerButton = addButton(content, "Create account");
        registerButton.setOnClickListener(view -> {
            registerButton.setEnabled(false);
            callApi("POST", "/api/mobile/register",
                    json("fullname", fullname.getText().toString().trim(),
                            "email", email.getText().toString().trim(),
                            "password", password.getText().toString()),
                    (result, status) -> {
                        registerButton.setEnabled(true);
                        if (status == 201) {
                            saveToken(result.optString("token", ""));
                            showDashboard();
                            loadDashboard();
                        } else {
                            showRegisterError(result.optString("error", "Could not create account."));
                        }
                    });
        });
        Button backButton = addTextButton(content, "Back to log in");
        backButton.setOnClickListener(view -> showLogin(null));
    }

    private void showRegisterError(String message) {
        showRegister(message);
    }

    private void showDashboard() {
        currentScreen = "dashboard";
        LinearLayout content = newPage("Dashboard", true);
        addText(content, "Loading your progress…", 16, false, MUTED);
    }

    private void loadDashboard() {
        callApi("GET", "/api/mobile/dashboard", null, (result, status) -> {
            if (status == 200) {
                renderDashboard(result);
            } else {
                addText(pageBody, result.optString("error", "Could not load your dashboard."),
                        14, false, Color.rgb(185, 28, 28));
            }
        });
    }

    private void renderDashboard(JSONObject result) {
        if (!"dashboard".equals(currentScreen)) {
            return;
        }
        pageBody.removeAllViews();
        JSONObject user = result.optJSONObject("user");
        JSONObject stats = result.optJSONObject("stats");
        String fullname = user == null ? "there" : user.optString("fullname", "there");
        String firstName = fullname.split(" ")[0];
        addText(pageBody, "Welcome, " + firstName, 27, true, TEXT);
        addText(pageBody, "Build momentum one problem at a time.", 16, false, MUTED);

        addStatCard(pageBody, "Current streak", stats == null ? "0 days" :
                stats.optInt("current_streak", 0) + " days");
        addStatCard(pageBody, "Questions solved", stats == null ? "0" :
                String.valueOf(stats.optInt("questions_solved", 0)));
        addStatCard(pageBody, "Accuracy", stats == null ? "0%" :
                stats.optDouble("accuracy", 0) + "%");
        addStatCard(pageBody, "Total submissions", stats == null ? "0" :
                String.valueOf(stats.optInt("total_submissions", 0)));

        Button daily = addButton(pageBody, stats != null && stats.optBoolean("today_solved")
                ? "Review today's question" : "Solve today's question");
        daily.setOnClickListener(view -> openDailyQuestion());
        Button problems = addButton(pageBody, "Browse practice problems");
        problems.setOnClickListener(view -> showProblems());
    }

    private void showProblems() {
        currentScreen = "problems";
        LinearLayout content = newPage("Problems", true);
        addText(content, "Practice library", 24, true, TEXT);
        addText(content, "Loading problems…", 15, false, MUTED);
        callApi("GET", "/api/mobile/questions", null, (result, status) -> {
            if (status != 200 || !"problems".equals(currentScreen)) {
                if (status != 200) {
                    addText(pageBody, result.optString("error", "Could not load problems."),
                            14, false, Color.rgb(185, 28, 28));
                }
                return;
            }
            renderProblems(result);
        });
    }

    private void renderProblems(JSONObject result) {
        pageBody.removeAllViews();
        EditText search = addInput(pageBody, "Search problems", InputType.TYPE_CLASS_TEXT);
        JSONArray library = result.optJSONArray("library");
        JSONArray archive = result.optJSONArray("archive");
        JSONArray solved = result.optJSONArray("solved_ids");
        List<JSONObject> allQuestions = new ArrayList<>();
        appendQuestions(allQuestions, library);
        appendQuestions(allQuestions, archive);

        LinearLayout rows = new LinearLayout(this);
        rows.setOrientation(LinearLayout.VERTICAL);
        pageBody.addView(rows);
        Runnable refresh = () -> {
            rows.removeAllViews();
            String query = search.getText().toString().trim().toLowerCase();
            for (JSONObject question : allQuestions) {
                String title = question.optString("title");
                String difficulty = question.optString("difficulty");
                String date = question.optString("question_date");
                if (!query.isEmpty()
                        && !(title + " " + difficulty + " " + date).toLowerCase().contains(query)) {
                    continue;
                }
                boolean isSolved = containsId(solved, question.optInt("id"));
                Button row = addTextButton(rows, title + "  ·  " + difficulty
                        + (isSolved ? "  ·  Solved" : "")
                        + (date.isEmpty() ? "" : "  ·  " + date));
                row.setOnClickListener(view -> openQuestion(question.optInt("id"), "problems"));
            }
            if (rows.getChildCount() == 0) {
                addText(rows, "No matching problems found.", 15, false, MUTED);
            }
        };
        search.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence value, int start, int count, int after) {}

            @Override
            public void onTextChanged(CharSequence value, int start, int before, int count) {
                refresh.run();
            }

            @Override
            public void afterTextChanged(Editable value) {}
        });
        refresh.run();
    }

    private void appendQuestions(List<JSONObject> target, JSONArray questions) {
        if (questions == null) {
            return;
        }
        for (int index = 0; index < questions.length(); index++) {
            JSONObject question = questions.optJSONObject(index);
            if (question != null) {
                target.add(question);
            }
        }
    }

    private boolean containsId(JSONArray ids, int target) {
        if (ids == null) {
            return false;
        }
        for (int index = 0; index < ids.length(); index++) {
            if (ids.optInt(index) == target) {
                return true;
            }
        }
        return false;
    }

    private void openDailyQuestion() {
        currentScreen = "question";
        previousScreen = "dashboard";
        LinearLayout content = newPage("Today's Question", true);
        addText(content, "Loading today's challenge…", 16, false, MUTED);
        callApi("GET", "/api/mobile/questions/daily", null, (result, status) -> {
            JSONObject question = result.optJSONObject("question");
            if (status == 200 && question != null && "question".equals(currentScreen)) {
                renderQuestion(question, true);
            } else if (status != 200) {
                showMessage(result.optString("error", "Today's question is unavailable."));
            }
        });
    }

    private void openQuestion(int questionId, String fromScreen) {
        currentScreen = "question";
        previousScreen = fromScreen;
        LinearLayout content = newPage("Practice Problem", true);
        addText(content, "Loading problem…", 16, false, MUTED);
        callApi("GET", "/api/mobile/questions/" + questionId, null, (result, status) -> {
            JSONObject question = result.optJSONObject("question");
            if (status == 200 && question != null && "question".equals(currentScreen)) {
                renderQuestion(question, false);
            } else if (status != 200) {
                showMessage(result.optString("error", "Could not load this problem."));
            }
        });
    }

    private void renderQuestion(JSONObject question, boolean daily) {
        pageBody.removeAllViews();
        addText(pageBody, question.optString("title"), 25, true, TEXT);
        addText(pageBody, question.optString("difficulty"), 14, true, GREEN);
        addText(pageBody, question.optString("description"), 16, false, TEXT);
        String signature = question.optString("function_signature");
        if (!signature.isEmpty()) {
            addText(pageBody, "Function signature", 16, true, TEXT);
            addCodeText(pageBody, signature);
        }
        addText(pageBody, "Example input", 16, true, TEXT);
        addCodeText(pageBody, question.optString("example_input"));
        addText(pageBody, "Example output", 16, true, TEXT);
        addCodeText(pageBody, question.optString("example_output"));

        JSONArray constraints = question.optJSONArray("constraints");
        if (constraints != null && constraints.length() > 0) {
            addText(pageBody, "Constraints", 16, true, TEXT);
            for (int index = 0; index < constraints.length(); index++) {
                addText(pageBody, "• " + constraints.optString(index), 14, false, MUTED);
            }
        }

        addText(pageBody, "Your solution", 20, true, TEXT);
        Spinner language = new Spinner(this);
        List<String> languages = Arrays.asList("Python", "C", "C++", "Java");
        ArrayAdapter<String> adapter = new ArrayAdapter<>(
                this, android.R.layout.simple_spinner_item, languages);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        language.setAdapter(adapter);
        pageBody.addView(language);

        EditText source = addInput(pageBody, "Write your solution here", InputType.TYPE_CLASS_TEXT
                | InputType.TYPE_TEXT_FLAG_MULTI_LINE | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        source.setTypeface(Typeface.MONOSPACE);
        source.setGravity(Gravity.TOP | Gravity.START);
        source.setMinLines(10);
        source.setText(starterCode(signature));
        language.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(android.widget.AdapterView<?> parent, View view,
                                       int position, long id) {
                if (position == 0) {
                    source.setText(starterCode(signature));
                } else {
                    source.setText("");
                }
            }

            @Override
            public void onNothingSelected(android.widget.AdapterView<?> parent) {}
        });

        TextView result = addText(pageBody, "Run your code against the example input.",
                14, false, MUTED);
        Button run = addButton(pageBody, "Run sample");
        run.setOnClickListener(view -> executeCode(run, result, question, language, source, false));
        Button submit = addButton(pageBody, "Submit solution");
        submit.setOnClickListener(view ->
                executeCode(submit, result, question, language, source, true));
        if (daily) {
            addText(pageBody, "Submitting an accepted solution completes today's goal.",
                    14, false, MUTED);
        }
    }

    private String starterCode(String signature) {
        if (signature == null || signature.isEmpty()) {
            return "print(\"Write your solution here\")";
        }
        String trimmed = signature.trim();
        if (trimmed.endsWith(":")) {
            return trimmed + "\n    return None\n";
        }
        return trimmed + ":\n    return None\n";
    }

    private void executeCode(
            Button button,
            TextView resultView,
            JSONObject question,
            Spinner language,
            EditText source,
            boolean submit
    ) {
        button.setEnabled(false);
        resultView.setText("Executing…");
        String endpoint = submit ? "/api/mobile/submit" : "/api/mobile/run";
        String languageValue = language.getSelectedItem().toString().toLowerCase();
        if ("c++".equals(languageValue)) {
            languageValue = "cpp";
        }
        callApi("POST", endpoint,
                json("question_id", question.optInt("id"),
                        "language", languageValue,
                        "source_code", source.getText().toString()),
                (response, status) -> {
                    button.setEnabled(true);
                    if (status >= 400) {
                        resultView.setText(response.optString("error", "Could not run your code."));
                        return;
                    }
                    StringBuilder text = new StringBuilder();
                    text.append(response.optString("verdict", "Error"));
                    text.append(" · ").append(response.optDouble("execution_time", 0)).append("s");
                    String output = response.optString("output", "");
                    String errors = response.optString("errors", "");
                    if (!output.isEmpty()) {
                        text.append("\n\nOutput:\n").append(output);
                    }
                    if (!errors.isEmpty()) {
                        text.append("\n\nDetails:\n").append(errors);
                    }
                    JSONObject stats = response.optJSONObject("stats");
                    if (submit && stats != null && "Accepted".equals(response.optString("verdict"))) {
                        text.append("\n\nGreat job! Current streak: ")
                                .append(stats.optInt("current_streak")).append(" days.");
                    }
                    resultView.setText(text.toString());
                });
    }

    private void showProfile() {
        currentScreen = "profile";
        LinearLayout content = newPage("Profile", true);
        addText(content, "Loading your profile…", 16, false, MUTED);
        callApi("GET", "/api/mobile/profile", null, (result, status) -> {
            if (status != 200 || !"profile".equals(currentScreen)) {
                if (status != 200) {
                    addText(pageBody, result.optString("error", "Could not load your profile."),
                            14, false, Color.rgb(185, 28, 28));
                }
                return;
            }
            renderProfile(result);
        });
    }

    private void renderProfile(JSONObject result) {
        pageBody.removeAllViews();
        JSONObject user = result.optJSONObject("user");
        JSONObject stats = result.optJSONObject("stats");
        if (user != null) {
            addText(pageBody, user.optString("fullname"), 25, true, TEXT);
            addText(pageBody, user.optString("email"), 15, false, MUTED);
            addText(pageBody, "Joined " + user.optString("joined_at"), 14, false, MUTED);
        }
        if (stats != null) {
            addStatCard(pageBody, "Current streak", String.valueOf(stats.optInt("current_streak")));
            addStatCard(pageBody, "Longest streak", String.valueOf(stats.optInt("longest_streak")));
            addStatCard(pageBody, "Questions solved", String.valueOf(stats.optInt("questions_solved")));
            addStatCard(pageBody, "Global rank", "#" + stats.optInt("global_rank"));
            addStatCard(pageBody, "Total submissions", String.valueOf(stats.optInt("total_submissions")));
            addStatCard(pageBody, "Acceptance rate", stats.optDouble("accuracy", 0) + "%");
            addText(pageBody, "Recent submissions", 20, true, TEXT);
            JSONArray recent = stats.optJSONArray("recent_activity");
            if (recent == null || recent.length() == 0) {
                addText(pageBody, "No submissions yet.", 15, false, MUTED);
            } else {
                for (int index = 0; index < recent.length(); index++) {
                    JSONObject item = recent.optJSONObject(index);
                    if (item != null) {
                        addStatCard(pageBody,
                                item.optString("title") + " · " + item.optString("verdict"),
                                item.optString("language").toUpperCase());
                    }
                }
            }
        }
    }

    private void showMessage(String message) {
        LinearLayout content = newPage("CodeDaily", true);
        addText(content, message, 16, false, Color.rgb(185, 28, 28));
        Button back = addButton(content, "Back");
        back.setOnClickListener(view -> {
            if ("problems".equals(previousScreen)) {
                showProblems();
            } else {
                showDashboard();
                loadDashboard();
            }
        });
    }

    private LinearLayout newPage(String title, boolean authenticated) {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(246, 247, 251));

        LinearLayout toolbar = new LinearLayout(this);
        toolbar.setGravity(Gravity.CENTER_VERTICAL);
        toolbar.setPadding(dp(16), dp(12), dp(16), dp(12));
        toolbar.setBackgroundColor(PANEL);
        TextView brand = new TextView(this);
        brand.setText(title);
        brand.setTextColor(GREEN);
        brand.setTextSize(20);
        brand.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        toolbar.addView(brand, new LinearLayout.LayoutParams(0, -2, 1));
        if (authenticated) {
            Button logout = addTextButton(toolbar, "Log out");
            logout.setOnClickListener(view -> {
                clearToken();
                showLogin(null);
            });
        }
        root.addView(toolbar);

        ScrollView scroll = new ScrollView(this);
        pageBody = new LinearLayout(this);
        pageBody.setOrientation(LinearLayout.VERTICAL);
        pageBody.setPadding(dp(18), dp(22), dp(18), dp(24));
        scroll.addView(pageBody);
        root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        if (authenticated) {
            root.addView(makeNavigation());
        }
        setContentView(root);
        return pageBody;
    }

    private View makeNavigation() {
        LinearLayout navigation = new LinearLayout(this);
        navigation.setGravity(Gravity.CENTER);
        navigation.setBackgroundColor(PANEL);
        String[] labels = {"Home", "Problems", "Profile"};
        for (String label : labels) {
            Button item = addTextButton(navigation, label);
            item.setTextColor(GREEN);
            item.setLayoutParams(new LinearLayout.LayoutParams(0, dp(52), 1));
            item.setOnClickListener(view -> {
                if ("Home".equals(label)) {
                    showDashboard();
                    loadDashboard();
                } else if ("Problems".equals(label)) {
                    showProblems();
                } else {
                    showProfile();
                }
            });
        }
        return navigation;
    }

    private TextView addText(
            LinearLayout parent,
            String value,
            int size,
            boolean bold,
            int color
    ) {
        TextView text = new TextView(this);
        text.setText(value);
        text.setTextSize(size);
        text.setTextColor(color);
        if (bold) {
            text.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        }
        text.setPadding(0, dp(8), 0, dp(8));
        parent.addView(text);
        return text;
    }

    private void addCodeText(LinearLayout parent, String value) {
        TextView text = addText(parent, value, 14, false, TEXT);
        text.setTypeface(Typeface.MONOSPACE);
        text.setPadding(dp(12), dp(12), dp(12), dp(12));
        text.setBackground(panelBackground());
    }

    private EditText addInput(LinearLayout parent, String hint, int inputType) {
        EditText input = new EditText(this);
        input.setHint(hint);
        input.setInputType(InputType.TYPE_CLASS_TEXT | inputType);
        input.setSingleLine((inputType & InputType.TYPE_TEXT_FLAG_MULTI_LINE) == 0);
        input.setTextColor(TEXT);
        input.setHintTextColor(MUTED);
        input.setPadding(dp(12), dp(10), dp(12), dp(10));
        input.setBackground(panelBackground());
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.setMargins(0, dp(8), 0, dp(8));
        parent.addView(input, params);
        return input;
    }

    private Button addButton(LinearLayout parent, String label) {
        Button button = new Button(this);
        button.setText(label);
        button.setTextColor(Color.WHITE);
        button.setAllCaps(false);
        button.setBackgroundColor(GREEN);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.setMargins(0, dp(8), 0, dp(8));
        parent.addView(button, params);
        return button;
    }

    private Button addTextButton(LinearLayout parent, String label) {
        Button button = new Button(this);
        button.setText(label);
        button.setTextColor(GREEN);
        button.setAllCaps(false);
        button.setBackgroundColor(Color.TRANSPARENT);
        parent.addView(button);
        return button;
    }

    private void addStatCard(LinearLayout parent, String label, String value) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(14), dp(8), dp(14), dp(8));
        card.setBackground(panelBackground());
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.setMargins(0, dp(6), 0, dp(6));
        parent.addView(card, params);
        addText(card, label, 14, false, MUTED);
        addText(card, value, 22, true, TEXT);
    }

    private GradientDrawable panelBackground() {
        GradientDrawable background = new GradientDrawable();
        background.setColor(PANEL);
        background.setCornerRadius(dp(10));
        background.setStroke(dp(1), Color.rgb(216, 222, 232));
        return background;
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    private void saveToken(String value) {
        token = value;
        getPreferences(MODE_PRIVATE).edit().putString("auth_token", value).apply();
    }

    private void clearToken() {
        token = null;
        getPreferences(MODE_PRIVATE).edit().remove("auth_token").apply();
    }

    @Override
    public void onBackPressed() {
        if ("register".equals(currentScreen)) {
            showLogin(null);
        } else if ("question".equals(currentScreen) && "problems".equals(previousScreen)) {
            showProblems();
        } else if (token != null && !"dashboard".equals(currentScreen)) {
            showDashboard();
            loadDashboard();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        network.shutdown();
        super.onDestroy();
    }
}
