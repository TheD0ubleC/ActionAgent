# ActionAgent AI Manual

This manual contains detailed guidance for AI agents working in the ActionAgent repository. The short, high-priority rules live in `AGENTS.md`; follow those first.

## Runtime execution model

ActionAgent is driven by `.github/action_agent_runner.py` inside a GitHub Actions job.

The workflow normally does this:

```text
Checkout repository
Set up Python
Restore ActionAgent cache
Run: python .github/action_agent_runner.py
Upload .action-agent/output/ as the ActionAgent artifact
```

The runner then:

1. Reads `.action-agent/run.toml`.
2. Discovers `.action-agent/scratch.py` and `.action-agent/tasks/*.py`.
3. Extracts the top triple-quoted TOML docstring from each task file.
4. Parses the TOML metadata.
5. Selects tasks whose metadata contains `run = true`.
6. Sorts enabled tasks by `priority`.
7. Executes `[commands].before`, `[commands].run`, and `[commands].after`.
8. Resets `run = true` to `run = false` when policy allows it.
9. Writes `.action-agent/result.json` if any task ran.
10. Commits runtime state when configured.

## Result reading protocol

Do not rely on live GitHub Actions log streams as the primary result channel.

ActionAgent treats captured output as one source with three projections:

```text
full task log -> result excerpt in .action-agent/result.json
full task log -> comment excerpt in the issue result comment
full task log -> artifact or committed output file when enabled
```

Prefer this reading order:

1. Latest marked issue comment containing `<!-- action-agent-result:v1 -->`.
2. `.action-agent/result.json`.
3. GitHub Actions artifact.
4. Committed `output_path`, only when `output_committed = true`.

`result.json` records:

- overall `status`
- whether any task `failed`
- task path and name
- task `exit_code`
- task `output_path`
- whether output exists, is committed, or is artifact-only
- output size and excerpt metadata
- `output_excerpt` for diagnostic fallback
- `comment_excerpt` for issue comment rendering
- whether each excerpt was truncated
- whether the task run flag was reset

`comment_excerpt` and `output_excerpt` are both generated directly from the complete task log. The comment excerpt is not produced by truncating the result excerpt.

Read `output_path` only when `output_committed = true`. When `output_committed = false` and `output_artifact = true`, the full log is in the GitHub Actions artifact.

## One-shot task template

Use this for temporary checks:

```python
"""
run = true
name = "Scratch task"
reason = "Temporary ActionAgent task"
timeout = 300
priority = 10

[commands]
before = []
run = ["python .action-agent/scratch.py"]
after = []

[output]
mode = "both"
path = ".action-agent/output/scratch.log"
artifact = true
commit = false

[execution]
cwd = "."
shell = "bash"
continue_on_error = false
reset_on = "always"
"""

print("ActionAgent scratch task started")
```

Use `.action-agent/scratch.py` for:

- reproducing an error once
- testing a generated patch
- checking a network endpoint once
- inspecting the current runtime environment
- running a temporary debug command
- trying a dependency or platform check
- cloning and building an external repository once
- producing a one-time artifact

## Reusable task template

Use this only when the task is likely to be useful again:

```python
"""
run = false
name = "Reusable task"
reason = "Reusable ActionAgent task"
priority = 50
timeout = 300

[commands]
before = []
run = ["echo reusable task"]
after = []

[output]
mode = "both"
path = ".action-agent/output/reusable-task.log"
artifact = true
commit = false

[execution]
cwd = "."
shell = "bash"
continue_on_error = false
reset_on = "always"
"""
```

## Python body execution semantics

The top triple-quoted block is TOML metadata for ActionAgent. It is also a normal Python module docstring when the file itself is executed by Python.

ActionAgent first parses the TOML metadata and then executes configured commands. It does not automatically run Python code below the TOML block.

If task logic is written in Python, the task must explicitly invoke the file from `[commands].run`:

```toml
[commands]
run = ["python .action-agent/scratch.py"]
```

If `[commands].run` does not invoke the task file, the Python body below the TOML block will not run.

If Python code runs subprocesses, propagate the subprocess exit code when that subprocess determines task success:

```python
completed = subprocess.run(cmd)
raise SystemExit(completed.returncode)
```

Or use:

```python
subprocess.run(cmd, check=True)
```

## Command lifecycle

Use three command phases:

```toml
[commands]
before = []
run = []
after = []
```

- `before`: install dependencies or prepare the environment.
- `run`: execute the actual task.
- `after`: cleanup or summarize results.

If a `before` command fails, `run` is skipped. If a `run` command fails, later `run` commands are skipped unless the task is split differently.

Prefer dependency installation in `before`, not hidden in custom Python code.

## Output behavior

Recommended default:

```toml
[output]
mode = "both"
path = ".action-agent/output/task.log"
artifact = true
commit = false
```

Output modes:

- `log`: print output only in GitHub Actions logs.
- `file`: save output only to a file.
- `both`: print output and save it.
- `none`: discard output.

Prefer `artifact = true` and `commit = false`.

The workflow uploads `.action-agent/output/` as the ActionAgent artifact. Useful logs, reports, packages, and build products should be copied or written under `.action-agent/output/`.

`output_excerpt` is included in `.action-agent/result.json`. Excerpt size is controlled by `[output].excerpt_bytes`; failed tasks can use `[output].failed_excerpt_bytes`. Defaults live in `.action-agent/run.toml`, and tasks may override them.

Full log commit is controlled by global `commit_outputs = true` or task-level `[output].commit = true`. Prefer excerpts by default.

## Reset behavior

Use:

```toml
[execution]
reset_on = "always"
```

Allowed values:

- `always`: reset after the task finishes, even if it fails. Recommended default.
- `success`: reset only after success.
- `never`: do not reset automatically.

Use `success` only when the task should intentionally remain enabled after failure for immediate retry/debugging.

## Environment variables

Task metadata may define non-secret environment variables:

```toml
[env]
BUILD_MODE = "release"
```

The runner exposes:

```text
ACTION_AGENT_TASK
ACTION_AGENT_TASK_NAME
ACTION_AGENT_OUTPUT
```

Use `ACTION_AGENT_OUTPUT` when task code should write to the configured output path.

Do not place secrets in `[env]`. GitHub Secrets must be exposed through workflow `env:` mapping before tasks can read them from `os.environ`.

## Execution environment

ActionAgent runs inside a GitHub Actions job. Treat it as a broad, command-capable sandbox suitable for tests, builds, scripts, network checks, and environment inspection.

It is constrained by:

- configured GitHub Actions runner platform
- installed system tools
- workflow permissions
- available secrets
- network behavior
- job timeout
- repository checkout state

The environment is disposable. Anything installed during one run may disappear before the next run.

Before relying on a specific platform, shell, or tool, check `.action-agent/run.toml`.

Example environment inspection task:

```python
"""
run = true
name = "Inspect tools"
reason = "Check available tools in the ActionAgent runner"
timeout = 120

[commands]
run = [
  "python --version",
  "git --version",
  "node --version || true",
  "npm --version || true",
  "dotnet --version || true",
  "cargo --version || true",
  "go version || true"
]
"""
```

## Platform selection

Platform selection is a runtime concern. Modify `.action-agent/run.toml` or workflow runtime configuration only when the user explicitly requires a different execution platform or when the current platform cannot satisfy the task.

Examples:

- Windows-only builds requiring MSVC, PowerShell, `.exe`, COM, or Windows SDK tools
- macOS-only builds requiring Xcode, `xcodebuild`, signing tools, or Apple SDKs
- ARM-specific checks
- platform-specific packaging

Do not pretend the chat environment has changed platforms. The configured GitHub Actions runner changes platforms.

## External repository builds

For external repository builds:

1. Clone into `.action-agent/tmp/` or another temporary directory.
2. Build in the temporary checkout.
3. Copy final artifacts, reports, and useful logs into `.action-agent/output/`.
4. Do not commit cloned repository contents.
5. Do not leave large temporary build trees in tracked repository paths.

Example:

```toml
[commands]
before = ["sudo apt-get update", "sudo apt-get install -y build-essential cmake"]
run = [
  "rm -rf .action-agent/tmp/project",
  "mkdir -p .action-agent/tmp .action-agent/output",
  "git clone <REPO_URL> .action-agent/tmp/project",
  "cmake -S .action-agent/tmp/project -B .action-agent/tmp/project/build",
  "cmake --build .action-agent/tmp/project/build --config Release",
  "tar -czf .action-agent/output/project-build.tar.gz -C .action-agent/tmp/project/build ."
]
```

Before building an unknown project, inspect files such as:

```text
README.md
Makefile
CMakeLists.txt
configure
meson.build
package.json
pyproject.toml
go.mod
Cargo.toml
```

Prefer documented build instructions over guessing.

## Failure diagnostics

A useful failure report should include:

- failing command
- exit code
- relevant log excerpt
- current working directory
- platform or tool version when relevant
- likely next action

Do not hide failures with broad `|| true` unless the command is genuinely optional and the reason is clear.

## Runtime directories

Do not add `.gitkeep` files just to preserve ActionAgent runtime directories.

Runtime directories may be created automatically:

```text
.action-agent/output/
.action-agent/cache/
.action-agent/tmp/
.action-agent/.venv/
```

They are normally ignored by Git.


## Secret injection details

GitHub repository secrets do not automatically appear in task environments. They must be mapped in `.github/workflows/action-agent.yml`, specifically in the `Run ActionAgent` step.

When a user request mentions GitHub Secrets, SSH credentials stored in Secrets, tokens stored in Secrets, or secret-backed environment variables, use this workflow:

1. Inspect `.github/workflows/action-agent.yml`.
2. Find the `Run ActionAgent` step.
3. Check whether each required environment variable is already mapped in that step.
4. If a mapping is missing and the user supplied the exact GitHub Secret name, edit only that step's secret injection area.
5. Only after the mapping is correct, create or update `.action-agent/scratch.py` or `.action-agent/tasks/*.py`.

Use mappings like:

```yaml
env:
  MY_SECRET: ${{ secrets.MY_SECRET }}
```

Do not leave an empty `env:` block. If no secrets are mapped, the workflow should contain only comments and the `run:` command.

Never write secret values into workflow files, task files, docs, logs, artifacts, issue comments, or `[env]` metadata. Map only user-provided secret names, preserving spelling and case. Do not invent secret names and do not try to discover secret values.

If the user says a secret named `SSH` contains `name@host:port`, and another secret named `SSH_PRIVATE_KEY` contains the key, map exactly `SSH` and `SSH_PRIVATE_KEY` unless the user asks for different environment variable names.

## Polling details for ChatGPT-style agents

After enabling a task with `run = true` and committing it, poll in short explicit steps. The safest waiting primitive is a single shell command:

```bash
sleep 10
```

Then inspect repository state again. Repeat only if needed.

Do not use long sleeps such as `sleep 30`, `sleep 50`, or `sleep 60` in one tool call. Do not chain many sleeps in one shell command, such as `sleep 10 && sleep 10 && sleep 10`. Do not place long local polling loops in one Python process. Short single-step polling is more reliable and lets the agent observe state between waits.

Good completion signals are:

```text
run=true changed back to run=false in the task metadata
a fresh issue comment containing <!-- action-agent-result:v1 -->
a fresh .action-agent/result.json written by the latest run
a completed workflow run with the expected artifact
```

If these signals disagree, prefer the freshest marked issue comment for human-readable status, then use `.action-agent/result.json` for structured fallback, and use artifacts for complete logs.

If the visible result appears stale, wait one more `sleep 10` and retry the result read. Stop after the user-requested maximum wait time, or after a reasonable bounded number of polling attempts, and report that the run may still be pending or failed to update.

## Issue comment output configuration

Issue comments are a lightweight UI, not the complete log store. The complete log remains in the artifact or in the committed `output_path` only when configured.

The comment system is configured in `.action-agent/run.toml`:

```toml
[comment]
enabled = true
issue = "auto" # issue number or "auto"
auto_create_issue = true
auto_issue_title = "ActionAgent"
auto_issue_marker = "<!-- action-agent-issue:v1 -->"
auto_issue_body = "ActionAgent run results and summaries. If issue comments are unavailable, read .action-agent/result.json and workflow artifacts instead."
auto_issue_state = "open" # open / closed / all
auto_issue_labels = []
marker = "<!-- action-agent-result:v1 -->"
mode = "excerpt" # summary / excerpt / full
artifact_name = "action-agent-output"
max_comment_bytes = 10000
success_excerpt_bytes = 6000
failed_excerpt_bytes = 12000

[comment.cleanup]
enabled = true
max_count = 10
max_total_bytes = 60000
target_total_bytes = 55000
min_keep = 3
delete_only_marked = true
```

`issue = "auto"` means ActionAgent will first look for a non-PR issue titled `auto_issue_title`, preferably one whose body contains `auto_issue_marker`. If none exists and `auto_create_issue = true`, it creates that control issue.

If issue creation or commenting fails, the workflow should still succeed. Agents must use `result.json` plus artifacts as the fallback result channel.

Marked ActionAgent result comments contain:

```text
<!-- action-agent-result:v1 -->
```

The automatically managed control issue contains:

```text
<!-- action-agent-issue:v1 -->
```

When reading comments, ignore unmarked human discussion unless the user asks for conversation context. From newest to oldest, find the latest comment containing the result marker above and use it as the current run summary.

## Issue comment cleanup details

The cleanup rule is intentionally conservative:

1. Only comments containing the configured result marker may be deleted.
2. Human comments must never be deleted by ActionAgent cleanup.
3. If marked result comments exceed `max_count`, delete the oldest marked comments first.
4. If marked result comments do not exceed `max_count` but their total UTF-8 size exceeds `max_total_bytes`, delete the oldest marked comments until total size is near `target_total_bytes`.
5. Never delete comments from the middle of the retained history; keep the newest marked comments as one continuous window.
6. Keep at least `min_keep` marked result comments when possible.
7. If cleanup configuration is invalid, clamp it conservatively instead of deleting aggressively.
8. If the marker is empty or missing, disable cleanup rather than risk deleting human comments.

This preserves recent context while preventing issue comment history from becoming an unbounded log database.

## Output excerpt details

ActionAgent captures complete stdout/stderr to the configured output log first. The result and comment excerpts are projections from that complete log:

```text
complete output log -> output_excerpt for result.json
complete output log -> comment_excerpt for issue UI
complete output log -> artifact or committed output path
```

The comment excerpt should not be generated by truncating `output_excerpt`. This prevents nested truncation from destroying useful diagnostic information.

Use these defaults unless the user asks otherwise:

```toml
[output]
mode = "both"
artifact = true
commit = false
excerpt_bytes = 20000
failed_excerpt_bytes = 100000

[comment]
mode = "excerpt"
success_excerpt_bytes = 6000
failed_excerpt_bytes = 12000
max_comment_bytes = 10000
```

`output_excerpt` is longer and intended for structured fallback and diagnostics. `comment_excerpt` is shorter and intended for issue UI. Full output belongs in the artifact unless the user explicitly asks to commit it and it is safe and reasonably small.
