# AGENTS.md

This repository uses **ActionAgent**.

ActionAgent is a GitHub Actions based execution layer for AI-generated tasks. The agent writes task intent; the fixed runtime discovers enabled task files, executes configured commands, captures output, resets run flags, writes result state, and commits runtime state when configured.

For detailed examples and templates, read:

```text
docs/ai/actionagent-manual.md
```

## Core model

Do not treat this as a normal CI setup.

```text
AI writes task intent
GitHub Actions starts a temporary runner
ActionAgent discovers run=true task files
ActionAgent executes command lifecycle
ActionAgent captures stdout/stderr
ActionAgent writes .action-agent/result.json when a task ran
ActionAgent resets run flags according to policy
```

ActionAgent does not automatically execute Python code below the TOML metadata block. Python code runs only when `[commands].run` invokes the task file.

## Editable files

Normal task work should edit only:

```text
.action-agent/scratch.py
.action-agent/tasks/*.py
```

Normally avoid editing runtime infrastructure:

```text
.github/workflows/action-agent.yml
.github/action_agent_runner.py
.action-agent/run.toml
```

Runtime infrastructure may be edited only when the user explicitly asks for a runtime-level change, when the task cannot be expressed correctly with task files alone, or when GitHub Secret injection is required.

## Secret injection exception

This section overrides the normal preference to avoid editing `.github/workflows/action-agent.yml`.

GitHub repository secrets do not automatically appear in task environments. They must be mapped in `.github/workflows/action-agent.yml`.

If a user request mentions GitHub Secrets, SSH credentials stored in Secrets, tokens stored in Secrets, or any secret-backed environment variable, the agent MUST do this before writing the task file:

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

Never write secret values into workflow files, task files, docs, logs, or `[env]` metadata. Map only user-provided secret names, preserving spelling and case. Do not invent secret names and do not try to discover secret values.

If the user says a secret named `SSH` contains `name@host:port`, and another secret named `SSH_PRIVATE_KEY` contains the key, map exactly `SSH` and `SSH_PRIVATE_KEY` unless the user asks for different environment variable names.

## Task placement

Use `.action-agent/scratch.py` for one-shot tasks:

- reproducing an error once
- testing a generated patch
- checking a network endpoint once
- inspecting the runner environment
- running temporary debug commands
- building an external repository once
- producing a one-time artifact

Use `.action-agent/tasks/*.py` only for reusable tasks likely to be run again, such as build, test, network check, or release check tasks.

Do not create many one-off task files.

## Task metadata

Every task file is a Python file with a top triple-quoted TOML metadata block.

Minimum task:

```python
"""
run = true
name = "Task name"
reason = "Why this task should run"
timeout = 300
priority = 10

[commands]
before = []
run = ["echo hello"]
after = []

[output]
mode = "both"
path = ".action-agent/output/task.log"
artifact = true
commit = false

[execution]
cwd = "."
shell = "bash"
continue_on_error = false
reset_on = "always"
"""
```

Use `reset_on = "always"` by default so failed one-shot tasks do not keep re-running forever.

If task logic is written in Python, `[commands].run` must explicitly invoke the file, for example:

```toml
[commands]
run = ["python .action-agent/scratch.py"]
```

If Python code runs subprocesses, propagate the subprocess exit code when that subprocess determines task success. Use `raise SystemExit(completed.returncode)` or `subprocess.run(..., check=True)`.


## Polling after triggering ActionAgent

After setting a task `run = true` and committing it, do not assume the GitHub Actions run has finished immediately. Poll in short, explicit steps.

Preferred polling loop for ChatGPT-style agents:

1. Wait once with a single short shell command:

   ```bash
   sleep 10
   ```

2. Re-read the task file that was enabled and check whether `run` has been reset to `false`.
3. If `run = true`, treat the task as still running or not yet reset. Wait another single `sleep 10` and check again.
4. Once `run = false`, read results in the normal order: latest marked issue comment, then `.action-agent/result.json`, then artifact or committed output.
5. If the visible result appears stale, wait one more `sleep 10` and retry the result read.
6. Stop after the user-requested maximum wait time, or after a reasonable bounded number of polling attempts, and report that the run may still be pending or failed to update.

Do not use long sleeps such as `sleep 30`, `sleep 50`, or `sleep 60` in one tool call. Do not chain many sleeps in one shell command, such as `sleep 10 && sleep 10 && sleep 10`. Do not place long local polling loops in one Python process. Short single-step polling is more reliable and lets the agent observe state between waits.

Use GitHub state, not elapsed time alone, as the completion signal. Good completion signals are:

```text
run=true changed back to run=false in the task metadata
a fresh issue comment containing <!-- action-agent-result:v1 -->
a fresh .action-agent/result.json written by the latest run
a completed workflow run with the expected artifact
```

If these signals disagree, prefer the freshest marked issue comment for human-readable status, then use `.action-agent/result.json` for structured fallback, and use artifacts for complete logs.

## Output protocol

Do not rely on live GitHub Actions log streams as the primary result channel.

ActionAgent treats captured output as one source with three projections:

```text
full task log -> result excerpt in .action-agent/result.json
full task log -> comment excerpt in the issue result comment
full task log -> artifact or committed output file when enabled
```

The issue comment is the preferred human-readable result channel when `[comment].enabled = true`. Read the latest marked ActionAgent result comment first, then fall back to `.action-agent/result.json`, then use the artifact or committed output path when complete logs are needed.

Marked ActionAgent result comments contain:

```text
<!-- action-agent-result:v1 -->
```

When reading an issue, ignore unmarked human discussion unless the user asks for conversation context. From newest to oldest, find the latest comment containing the marker above and use it as the current run summary.

After a task run, the stable machine-readable fallback is:

```text
.action-agent/result.json
```

ActionAgent updates this file only when at least one task is selected for execution. If there are no `run = true` tasks, the runner exits without changing repository state.

Use `comment_excerpt` from the latest issue comment for quick human-facing summaries. Use `output_excerpt` in `.action-agent/result.json` when more diagnostic detail is needed. Both excerpts are generated directly from the complete task log, not by truncating one excerpt from another.

Read the referenced `output_path` only when `output_committed = true`. If `output_committed = false` and `output_artifact = true`, the full log is available as a GitHub Actions artifact, not as a repository file.

AI agents may opt in to full log commits by setting task-level `[output].commit = true` or global `commit_outputs = true`, but only when the full log is genuinely needed, safe, and reasonably small. By default, ActionAgent captures all stdout/stderr but commits only bounded excerpts through `.action-agent/result.json` and posts bounded issue comments.

## Issue comment behavior

Issue comments are a lightweight UI, not the complete log store. The complete log remains in the artifact or in the committed `output_path` only when configured.

The comment system is configured in `.action-agent/run.toml`:

```toml
[comment]
enabled = true
issue = 1
marker = "<!-- action-agent-result:v1 -->"
mode = "excerpt" # summary / excerpt / full
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

The cleanup rule is intentionally conservative:

1. Only comments containing the configured marker may be deleted.
2. Human comments must never be deleted by ActionAgent cleanup.
3. If marked result comments exceed `max_count`, delete the oldest marked comments first.
4. If marked result comments do not exceed `max_count` but their total UTF-8 size exceeds `max_total_bytes`, delete the oldest marked comments until total size is near `target_total_bytes`.
5. Never delete comments from the middle of the retained history; keep the newest marked comments as one continuous window.
6. Keep at least `min_keep` marked result comments when possible.

When reporting results to the user, prefer this order:

```text
latest marked issue comment
.action-agent/result.json
GitHub Actions artifact
committed output_path, only when output_committed=true
```

## Safety

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

For security testing, scanning, probing, or penetration testing, only create ActionAgent tasks for systems the user owns or has explicit authorization to test. If authorization is unclear, do not run network probes, exploit tools, credential attacks, or intrusive scanners.

For SSH tasks, prefer key-based authentication through GitHub Actions secrets or preconfigured runtime credentials. Do not write plaintext passwords, private keys, or tokens into task files or logs.

Prefer non-interactive commands. Avoid commands requiring TTY input, password prompts, manual confirmation, or long-running sessions.

## Decision rule

When the user asks to verify, test, inspect, benchmark, build, request, reproduce, or execute something:

1. Decide whether the task is one-shot or reusable.
2. If the task needs GitHub Secrets or secret-backed environment variables, complete the Secret injection exception workflow before editing the task file.
3. Use `.action-agent/scratch.py` for one-shot tasks.
4. Use `.action-agent/tasks/*.py` only for reusable tasks.
5. Set `run = true` when the task should execute now.
6. Use `[commands].before` for setup and dependency installation.
7. Use `[commands].run` for the executable entry point.
8. If task logic is in Python, make `[commands].run` invoke the task file explicitly.
9. Save useful output under `.action-agent/output/`.
10. After the workflow finishes, read the latest marked issue comment first when comments are enabled.
11. Fall back to `.action-agent/result.json` when the comment is absent, stale, truncated, or insufficient.
12. Use the artifact or committed `output_path` only for complete logs or downloadable files.
13. Keep the task explicit, bounded, and safe.

## More detail

Read `docs/ai/actionagent-manual.md` for:

- full task templates
- command lifecycle details
- result file schema details
- platform/runtime guidance
- build artifact guidance
- failure diagnostic guidance
- runtime directory conventions
