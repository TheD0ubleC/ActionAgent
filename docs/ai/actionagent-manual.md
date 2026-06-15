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

Read `.action-agent/result.json` after ActionAgent runs. It records:

- overall `status`
- whether any task `failed`
- task path and name
- task `exit_code`
- task `output_path`
- whether output exists, is committed, or is artifact-only
- output size and excerpt size
- `output_excerpt`
- whether the task run flag was reset

Use `output_excerpt` first. Read `output_path` only when `output_committed = true`. When `output_committed = false` and `output_artifact = true`, the full log is in the GitHub Actions artifact.

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
