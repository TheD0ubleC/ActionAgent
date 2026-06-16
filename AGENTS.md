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

After setting `run = true` and committing it, poll instead of assuming completion.

Preferred ChatGPT-style loop:

```bash
sleep 10
```

Then re-read the enabled task file. If `run = true`, wait another single `sleep 10` and check again. Once `run = false`, read results.

Do not use `sleep 30`, `sleep 50`, `sleep 60`, chained sleeps, or long local Python sleep loops. One short wait per polling step is safer and lets the agent observe state between waits.

Good completion signals:

```text
run=true reset to run=false
fresh issue comment containing <!-- action-agent-result:v1 -->
fresh .action-agent/result.json
completed workflow run with expected artifact
```

If the visible result appears stale, wait one more `sleep 10` and retry. Stop after the user-requested maximum wait time or a reasonable bounded number of attempts.

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
