# AGENTS.md

This repository uses **ActionAgent**.

ActionAgent is a GitHub Actions based execution layer for AI-generated tasks. The agent should not modify the GitHub Actions workflow or the ActionAgent runner unless the user explicitly asks.

The agent should only express **what should be executed**. The fixed ActionAgent runtime discovers tasks, executes configured commands, captures output, resets run flags, and commits runtime state when configured.

## Mental model

Do not treat this as a normal CI setup.

Think of ActionAgent as:

```text
AI writes task intent
GitHub Actions starts a temporary runner
ActionAgent discovers enabled task files
ActionAgent parses the top TOML metadata block
ActionAgent executes the configured command lifecycle
ActionAgent saves logs and artifacts
ActionAgent resets one-shot run flags
ActionAgent writes a stable result file
```

The agent does **not** need to learn GitHub Actions YAML or edit workflow files for normal tasks.

## Result reading protocol

Do not rely on live GitHub Actions log streams as the primary result channel.

After an ActionAgent run, read:

```text
.action-agent/result.json
```

ActionAgent updates this file only when at least one task is selected for execution. If there are no `run = true` tasks, the runner exits without changing repository state.

This file is the stable machine-readable result contract. It records:

- overall `status`
- whether any task `failed`
- each task file path and name
- each task `exit_code`
- each task `output_path`
- whether the output log exists, is committed, or is artifact-only
- output log size and configured excerpt size
- an `output_excerpt` with the tail of the captured log
- whether the task run flag was reset

Use `output_excerpt` first. Then read the referenced `output_path` file under `.action-agent/output/` only when `output_committed = true`. If `output_committed = false` and `output_artifact = true`, the full log is available as a GitHub Actions artifact, not as a repository file.

AI agents may opt in to committing full logs by setting task-level `[output].commit = true` or global `commit_outputs = true`. Do this only when the full log is genuinely needed and expected to be safe and reasonably small. When not configured, ActionAgent still captures all stdout/stderr but commits only bounded excerpts through `.action-agent/result.json`.

The workflow may still upload `.action-agent/output/` as an artifact, but artifacts and live workflow logs are secondary. The preferred AI loop is:

```text
write task file -> ActionAgent executes -> ActionAgent writes result.json/log files -> AI reads result.json -> AI reads referenced logs
```

By default, task failure is represented in `result.json` instead of making the workflow fail. This keeps the result channel readable even when the executed command exits non-zero.

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
7. Executes `[commands].before`, `[commands].run`, and `[commands].after` according to the task metadata.
8. Resets `run = true` to `run = false` when the configured reset policy allows it.
9. Writes `.action-agent/result.json` with task status, exit codes, output paths, and reset state if any task ran.
10. Commits runtime state when configured to do so.

ActionAgent does **not** automatically execute the Python code below the TOML block merely because a task file was discovered.

## Editable files

The agent may edit:

```text
.action-agent/scratch.py
.action-agent/tasks/*.py
```

The agent should normally avoid editing:

```text
.github/workflows/action-agent.yml
.github/action_agent_runner.py
.action-agent/run.toml
```

Those files are ActionAgent runtime infrastructure.

`normally avoid` does not mean `never edit`. Runtime infrastructure may be edited only when the user explicitly asks for a runtime-level change or when the task cannot be expressed correctly with task files alone. Examples include changing the runner platform, changing global runtime defaults, or modifying the ActionAgent implementation itself.

Secret injection is a workflow-level concern. GitHub repository secrets do not automatically appear in task environments; they must be explicitly mapped in `.github/workflows/action-agent.yml`.

Before writing or updating a task that reads a secret-backed environment variable, inspect `.github/workflows/action-agent.yml` and confirm the `Run ActionAgent` step maps that environment variable. If it is missing and the user has provided the exact GitHub Secret name, edit only that step's secret injection area. Add references such as:

```yaml
env:
  MY_SECRET: ${{ secrets.MY_SECRET }}
```

Do not leave an empty `env:` block in workflow YAML. If no secrets are currently mapped, the workflow should contain only comments and the `run:` command.

Never write secret values into workflow files, task files, docs, logs, or `[env]` metadata. Do not broaden workflow permissions or change runner logic just to expose a secret.

Ask the user for the exact GitHub Secret names they created when the names are not already clear. Map only those names, preserving spelling and case. Do not invent secret names and do not try to discover secret values.

When possible, prefer solving the user's request by editing task files rather than runtime infrastructure.

## One-shot task vs reusable task

Use this rule:

### One-shot task

If the task is temporary, experimental, only useful once, or created just to verify the current change, write it to:

```text
.action-agent/scratch.py
```

Overwrite the previous contents of `scratch.py`.

Use `scratch.py` for:

- reproducing an error once
- testing a generated patch
- checking a network endpoint once
- inspecting the current runtime environment
- running a temporary debug command
- trying a dependency or platform check
- cloning and building an external repository once
- producing a one-time artifact for the user

### Reusable task

If the task is likely to be useful again, create or update a named file in:

```text
.action-agent/tasks/
```

Examples:

```text
.action-agent/tasks/build.py
.action-agent/tasks/test.py
.action-agent/tasks/network_check.py
.action-agent/tasks/release_check.py
```

Only create a new task file when reuse is likely. Do not create many one-off task files.

## Task file format

Every task file is a Python file with a triple-quoted TOML metadata block at the top.

A task can execute any command through `[commands]`. The file body may contain Python code when useful, but Python code runs only when it is explicitly invoked by a configured command.

Example:

```python
"""
run = true
name = "Run tests"
reason = "Verify the latest code changes"
priority = 10
timeout = 300

[commands]
before = []
run = ["python -m pytest"]
after = []

[output]
mode = "both"
path = ".action-agent/output/tests.log"
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

ActionAgent first parses the TOML metadata and then executes configured commands. It does **not** automatically run the Python code below the TOML block.

If the task logic is written in Python, the task must explicitly invoke the file from `[commands].run`:

```python
"""
run = true
name = "Python scratch task"
reason = "Run Python logic in this task file"
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

print("This Python code runs because commands.run invokes this file.")
```

If `[commands].run` does not invoke the task file, the Python body below the TOML block will not run.

Use this mental model:

```text
Runner parses TOML docstring
Runner executes [commands].before
Runner executes [commands].run
Python body runs only if a command invokes the Python file
Runner executes [commands].after according to policy
Runner resets run flag according to policy
```

## Required metadata

At minimum, use:

```toml
run = true
name = "Task name"
reason = "Why this task should run"
timeout = 300

[commands]
run = ["echo hello"]
```

Meaning:

- `run = true`: execute this task.
- `run = false`: keep this task disabled.
- `name`: short human-readable task name.
- `reason`: why this task exists.
- `timeout`: maximum runtime in seconds.
- `[commands].run`: commands to execute.

After execution, ActionAgent may reset `run = true` to `run = false`.

If `[commands].run` is empty or missing and no global default command is configured, the task fails because there is no executable entry point.

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

Commands run in order. If a `before` command fails, `run` is skipped. If a `run` command fails, later `run` commands are skipped unless the task is split differently.

By default, `after` commands are intended for cleanup or summaries. They should be safe to run even when the main task fails.

Prefer placing dependency installation in `before`, not inside custom Python code.

Good:

```toml
[commands]
before = ["python -m pip install requests"]
run = ["python .action-agent/scratch.py"]
```

Avoid hiding setup inside script code unless necessary.

## Choosing commands vs Python code

Use `[commands]` directly for simple, linear tasks:

```toml
[commands]
run = ["make test"]
```

Use Python code when the task needs real control flow, such as:

- parsing files or logs
- conditional build logic
- retry logic
- structured reports
- API calls
- copying and packaging selected outputs
- coordinating multiple tools

When using Python code, keep the entry point explicit:

```toml
[commands]
run = ["python .action-agent/scratch.py"]
```

A good pattern is:

```text
[commands].before = environment setup
[commands].run = invoke the task implementation
Python body = task-specific logic
[commands].after = cleanup or final summary
```

If Python code runs subprocesses, propagate the subprocess exit code when that subprocess determines task success. For example, call `raise SystemExit(completed.returncode)` or use `subprocess.run(..., check=True)`. Otherwise the Python script may exit with 0 even when the command it ran failed.

## Execution environment

ActionAgent runs inside a GitHub Actions job.

Treat it as a broad, command-capable sandbox suitable for local tests, builds, script execution, network checks, and environment inspection.

However, it is not persistent and not truly unlimited. It is constrained by:

- the configured GitHub Actions runner platform
- installed system tools
- workflow permissions
- available secrets
- network behavior
- job timeout
- repository checkout state

The environment is normally disposable. Anything installed during one run may disappear before the next run.

Before relying on a specific platform, shell, or tool, check:

```text
.action-agent/run.toml
```

If unsure, inspect tools safely:

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

Platform selection is a runtime concern, not a normal task concern.

Use task files for commands and task logic. Modify `.action-agent/run.toml` or workflow runtime configuration only when the user explicitly requires a different execution platform or when the current platform cannot satisfy the task.

Examples that may justify a runtime/platform change:

- Windows-only builds requiring MSVC, PowerShell, `.exe`, COM, or Windows SDK tools
- macOS-only builds requiring Xcode, `xcodebuild`, signing tools, or Apple SDKs
- ARM-specific checks
- platform-specific packaging or installer generation

Do not pretend the chat environment has changed platforms. The configured GitHub Actions runner changes platforms.

## Output behavior

ActionAgent writes a machine-readable result file by default:

```text
.action-agent/result.json
```

Treat this as the primary status channel. It is intended for AI agents to read after the runner finishes.

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

The workflow uploads `.action-agent/output/` as the ActionAgent artifact. Therefore, useful logs, reports, packages, and build products should be copied or written under `.action-agent/output/`.

The result file points to the relevant log files in `.action-agent/output/`.

The result file also includes `output_excerpt`, a bounded tail of the captured log. This is the preferred first place to read command output because full log files may be artifact-only when `output.commit = false`.

Excerpt size is controlled by `[output].excerpt_bytes`; failed tasks can use a larger `[output].failed_excerpt_bytes`. The global defaults live in `.action-agent/run.toml`, and individual tasks may override them under their own `[output]` table.

Full log commit is controlled separately by `commit_outputs = true` globally or `[output].commit = true` per task. Prefer excerpts by default; opt in to full log commits only when the user needs repository-visible complete logs.

Do not rely on `artifact = true` to upload arbitrary paths outside `.action-agent/output/` unless the runtime explicitly supports that behavior. Treat `artifact = true` as task intent metadata and place actual artifact files in the output directory.

Do not commit large logs or generated files unless the user explicitly asks.

## Build artifacts and external repositories

For external repository builds:

1. Clone into `.action-agent/tmp/` or another temporary directory.
2. Build in the temporary checkout.
3. Copy only final artifacts, reports, and useful logs into `.action-agent/output/`.
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

Prefer the project's documented build instructions over guessing.

## Failure diagnostics

When a task fails, preserve enough information to debug it.

A useful failure report should include:

- the failing command
- exit code
- relevant log excerpt
- current working directory
- platform or tool version when relevant
- likely next action

Do not hide failures with broad `|| true` unless the command is genuinely optional and the reason is clear.

## Reset behavior

Use:

```toml
[execution]
reset_on = "always"
```

Allowed values:

- `always`: reset after the task finishes, even if it fails. Recommended default so failed one-shot tasks do not keep re-running forever.
- `success`: reset `run = true` only after the task succeeds.
- `never`: do not reset automatically.

Prefer `always` for normal one-shot and reusable tasks. Use `success` only when the task should intentionally remain enabled after failure for immediate retry/debugging.

## Environment variables

Task metadata may define environment variables under `[env]` when useful:

```toml
[env]
BUILD_MODE = "release"
```

The runner also exposes useful environment variables to commands:

```text
ACTION_AGENT_TASK
ACTION_AGENT_TASK_NAME
ACTION_AGENT_OUTPUT
```

Use `ACTION_AGENT_OUTPUT` in scripts when the output path should follow the configured task metadata.

Do not place secrets in `[env]`. Use GitHub Actions secrets or preconfigured runtime credentials instead.

GitHub Secrets must be exposed to ActionAgent through the workflow `env:` mapping before tasks can read them from `os.environ`. Task files can use environment variable names such as `SSH_HOST` or `SSH_PRIVATE_KEY`, but they cannot access the GitHub Secrets store directly.

## Safety rules

Do not write tasks that:

- print secrets, tokens, cookies, private keys, passwords, or full environment dumps
- hardcode credentials in task files
- intentionally destroy repository contents
- run infinite loops
- install and execute unknown remote scripts blindly
- push commits unless the user explicitly asks
- perform destructive network operations
- spam external services
- hide failures that should be visible

Network requests are allowed for testing, but keep them scoped and explain the purpose in `reason`.

For security testing, scanning, probing, or penetration testing, only create ActionAgent tasks for systems the user owns or has explicit authorization to test. If authorization is unclear, do not run network probes, exploit tools, credential attacks, or intrusive scanners.

For SSH tasks, prefer key-based authentication through GitHub Actions secrets or preconfigured runtime credentials. Do not write plaintext passwords, private keys, or tokens into task files or logs.

Prefer non-interactive commands. Avoid commands that require TTY input, password prompts, manual confirmation, or long-running sessions.

## Default one-shot task template

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

## Agent decision rule

When the user asks to verify, test, inspect, benchmark, build, request, reproduce, or execute something:

1. Decide whether the task is one-shot or reusable.
2. Use `.action-agent/scratch.py` for one-shot tasks.
3. Use `.action-agent/tasks/*.py` only for reusable tasks.
4. Set `run = true` when the task should execute now.
5. Use `[commands].before` for setup and dependency installation.
6. Use `[commands].run` for the executable entry point.
7. If task logic is in Python, make `[commands].run` invoke the task file explicitly.
8. Save useful output to `.action-agent/output/`.
9. Keep the task simple, explicit, bounded, and safe.

## Runtime directories

Do not add `.gitkeep` files just to preserve ActionAgent runtime directories.

Directories such as these are runtime state and may be created automatically when needed:

```text
.action-agent/output/
.action-agent/cache/
.action-agent/tmp/
.action-agent/.venv/
```

They are normally ignored by Git.

## Platform and external execution

ActionAgent is intended to give the agent access to a broader GitHub Actions execution environment than a local chat sandbox.

It may be used for Windows, macOS, Linux, ARM Linux, package installation, project builds, network checks, and runtime inspection when the workflow is configured for those platforms.

The agent should still keep tasks explicit and bounded. Treat the runner as temporary: installed packages and generated files do not persist unless saved through cache, artifact, repository commits, or an external service.
