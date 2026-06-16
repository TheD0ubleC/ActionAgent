# AGENTS.md

This repository uses **ActionAgent**, a GitHub Actions based execution layer for AI-generated tasks.

Read this file first. Read `docs/ai/actionagent-manual.md` for detailed templates, configuration reference, comment cleanup rules, and troubleshooting.

## Core model

ActionAgent is not normal CI.

```text
AI edits a task file -> GitHub Actions runner starts -> ActionAgent runs run=true tasks -> output is captured -> result state/comment/artifact are written -> run flags are reset
```

Python code below the TOML metadata block is not run automatically. It runs only when `[commands].run` invokes it.

## Files to edit

Normal task work should edit only:

```text
.action-agent/scratch.py
.action-agent/tasks/*.py
```

Use `scratch.py` for one-shot tasks. Use `tasks/*.py` only for reusable tasks.

Avoid editing runtime files unless the user asks for a runtime change, task files cannot express the request, or GitHub Secret injection is required:

```text
.github/workflows/action-agent.yml
.github/action_agent_runner.py
.github/action_agent_commenter.py
.action-agent/run.toml
```

## Secrets

GitHub Secrets must be mapped in the `Run ActionAgent` step of `.github/workflows/action-agent.yml`; they do not appear automatically.

For any secret-backed task:

1. Inspect the workflow.
2. Check the `Run ActionAgent` step.
3. Add missing secret-name mappings only when the user supplied the exact secret names.
4. Then write the task file.

Example mapping:

```yaml
env:
  MY_SECRET: ${{ secrets.MY_SECRET }}
```

Never write secret values into workflow files, task files, docs, logs, issue comments, artifacts, or `[env]` metadata. Map names only. Do not invent secret names.

If the user says `SSH` contains `name@host:port` and `SSH_PRIVATE_KEY` contains the key, map exactly `SSH` and `SSH_PRIVATE_KEY` unless told otherwise.

## Task files

Every task file is Python with a top triple-quoted TOML metadata block. Copy from `.action-agent/templates/` when possible.

Minimum required shape:

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

Use `reset_on = "always"` for one-shot tasks. If task logic is Python, `[commands].run` must explicitly invoke the file, for example `python .action-agent/scratch.py`. Propagate subprocess exit codes when they determine success.

## Polling after triggering

After setting `run = true` and committing it, keep the conversation alive and wait for completion instead of stopping early.

**The wait is performed in the agent's own available execution environment, not inside GitHub and not by the GitHub connector.** If the agent has a local shell, Python, container, or code-execution tool, it must actually call that tool to wait. Do not merely show `sleep 10` in the reply, and do not write sleep commands into the repository just to poll.

Estimate the initial wait from the task before the first status check. For a task likely to take about 30 seconds, perform three separate local wait tool calls:

```bash
sleep 10
```

Then call another separate `sleep 10`, then another separate `sleep 10`. These are waiting calls only; do not query GitHub between them unless there is a specific reason. Only after the estimated wait, re-read the enabled task file and check whether `run` reset from `true` to `false`.

If `run = true`, the task is probably still running. Estimate another short wait batch, run one or more separate `sleep 10` waits in the agent's own environment, then check again. If `run = false`, continue to result reading.

If the task appears complete but the issue comment, `result.json`, artifact, or committed output is not fresh yet, wait with additional separate `sleep 10` calls and retry until the result is readable.

Do not use `sleep 30`, `sleep 50`, `sleep 60`, chained sleeps, or long local Python sleep loops. Each wait should be one short local execution call that returns before the next action.

Do not end the reply immediately after triggering a task just because results are not visible yet. Continue polling until completion, a fresh result is readable, or the user-specified / reasonable maximum wait is reached. If the agent truly has no way to perform local waits, it must say that limitation explicitly instead of pretending the task is complete or stopping early.

Good completion signals:

```text
run=true reset to run=false
fresh issue comment containing <!-- action-agent-result:v1 -->
fresh .action-agent/result.json
completed workflow run with expected artifact
```

## Result reading order

Do not use live Actions logs as the primary result channel.

Prefer this order:

```text
latest marked issue comment
.action-agent/result.json
GitHub Actions artifact
committed output_path, only when output_committed=true
```

Marked result comments contain:

```text
<!-- action-agent-result:v1 -->
```

By default `[comment].issue = "auto"`, so ActionAgent finds or creates an `ActionAgent` control issue containing:

```text
<!-- action-agent-issue:v1 -->
```

If no marked comment exists, do not assume task failure. Fall back to `.action-agent/result.json` and artifacts.

`comment_excerpt` is the short human-readable result. `output_excerpt` in `result.json` is the longer diagnostic fallback. Both are generated directly from the complete log; one is not truncated from the other. Full logs live in artifacts unless output commits are explicitly enabled.

## Artifact configuration and download

Artifacts are the default full-log channel. When a task should produce downloadable output, set the task output like this:

```toml
[output]
mode = "both"
path = ".action-agent/output/task-name.log"
artifact = true
commit = false
```

Defaults in `.action-agent/run.toml` already use `upload_artifact = true`, `[output].artifact = true`, and `[output].commit = false`. This keeps full logs out of git history while still making them downloadable.

The workflow uploads one artifact named:

```text
action-agent-output
```

That artifact includes:

```text
.action-agent/result.json
.action-agent/output/
```

If the artifact name is changed, keep these in sync:

```text
.github/workflows/action-agent.yml -> Upload ActionAgent output -> name
.action-agent/run.toml -> [comment].artifact_name
```

After completion, use `result.json` to locate the correct run and output:

```text
workflow_run_id or workflow_run_url
tasks[].output_artifact
tasks[].output_path
tasks[].output_size_bytes
```

If `output_artifact = true`, fetch the artifacts for that workflow run, choose the artifact named `action-agent-output` unless configured otherwise, download it, and give the user the downloadable file link. Inside the zip, the complete task log is under the task's `output_path`.

If the marked issue comment or `result.json` says an artifact exists but the artifact list/download is not fresh yet, wait with separate local `sleep 10` calls and retry. Do not stop after saying only that the artifact is not visible yet.

Use committed `output_path` only when `output_committed = true`. Otherwise the full output is expected in the artifact, not in repository files.

## Issue comment cleanup

Issue comments are UI, not the full log store. ActionAgent cleanup may delete only comments containing the configured result marker. Never delete human comments.

Default intent:

```text
keep newest marked comments as one continuous window
keep at most 10 marked result comments
keep total marked comment size near 60KB or less
delete from the oldest marked comment forward
never delete from the middle of retained history
```

See `docs/ai/actionagent-manual.md` for full `[comment]` and `[comment.cleanup]` configuration.

## Safety

Do not write tasks that print secrets or full environment dumps, hardcode credentials, destroy repository contents, run infinite loops, blindly execute unknown remote scripts, push commits without explicit user request, perform destructive network operations, spam services, or hide important failures.

For security testing, scanning, probing, or penetration testing, only create tasks for systems the user owns or is authorized to test.

For SSH tasks, prefer key-based authentication through GitHub Secrets or preconfigured runtime credentials. Do not write plaintext passwords, private keys, or tokens into task files or logs.

Prefer non-interactive commands. Avoid TTY input, password prompts, manual confirmation, or long-running sessions.

## Decision rule

For verify/test/inspect/benchmark/build/request/reproduce/execute tasks:

1. Choose `scratch.py` for one-shot work or `tasks/*.py` for reusable work.
2. Map required GitHub Secret names first.
3. Set `run = true` only when the task should execute now.
4. Put setup in `[commands].before` and the entry point in `[commands].run`.
5. Save useful output under `.action-agent/output/`.
6. Poll with one `sleep 10` per step until completion or a bounded limit.
7. Read latest marked issue comment, then `result.json`, then artifact/committed output.
8. Keep every task explicit, bounded, and safe.
