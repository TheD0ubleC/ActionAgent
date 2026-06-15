from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import time
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:
    print("ActionAgent requires Python 3.11+ for tomllib.")
    sys.exit(1)


CONFIG_PATH = Path(".action-agent/run.toml")

DOCSTRING_RE = re.compile(
    r"\A"
    r"(?:\ufeff)?"
    r"(?:#![^\n]*(?:\n|$))?"
    r"(?:#.*coding[:=][^\n]*(?:\n|$))?"
    r"\s*"
    r"(?P<prefix>[rRuUbBfF]{0,2})"
    r"(?P<quote>\"\"\"|\'{3})"
    r"(?P<doc>.*?)"
    r"(?P=quote)",
    re.DOTALL,
)


@dataclass
class Task:
    path: Path
    meta: dict[str, Any]
    doc_start: int
    doc_end: int


def load_toml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"ActionAgent config not found: {path}")
    return tomllib.loads(path.read_text(encoding="utf-8"))


def extract_docstring(source: str) -> tuple[str, int, int] | None:
    match = DOCSTRING_RE.search(source)
    if not match:
        return None
    return match.group("doc"), match.start("doc"), match.end("doc")


def load_task(path: Path) -> Task | None:
    if not path.exists():
        return None

    source = path.read_text(encoding="utf-8")
    extracted = extract_docstring(source)

    if extracted is None:
        print(f"ActionAgent: skip task without top TOML docstring: {path}")
        return None

    doc, doc_start, doc_end = extracted

    try:
        meta = tomllib.loads(doc)
    except tomllib.TOMLDecodeError as e:
        print(f"ActionAgent: invalid TOML metadata in {path}")
        print(e)
        return None

    return Task(path=path, meta=meta, doc_start=doc_start, doc_end=doc_end)


def deep_get(data: dict[str, Any], key: str, default: Any = None) -> Any:
    current: Any = data
    for part in key.split("."):
        if not isinstance(current, dict):
            return default
        current = current.get(part)
    return default if current is None else current


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    raise TypeError(f"Expected string or list of strings, got {type(value).__name__}")


def discover_tasks(config: dict[str, Any]) -> list[Task]:
    discovered: list[Task] = []

    include_scratch = bool(config.get("include_scratch", True))
    scratch_file = Path(config.get("scratch_file", ".action-agent/scratch.py"))
    task_dir = Path(config.get("task_dir", ".action-agent/tasks"))

    if include_scratch and scratch_file.exists():
        scratch = load_task(scratch_file)
        if scratch is not None:
            discovered.append(scratch)

    if task_dir.exists():
        for path in sorted(task_dir.glob("*.py")):
            if path.resolve() == scratch_file.resolve():
                continue
            task = load_task(path)
            if task is not None:
                discovered.append(task)

    enabled = [task for task in discovered if task.meta.get("run", False) is True]
    enabled.sort(key=lambda task: int(task.meta.get("priority", 100)))
    return enabled


def shell_command(shell_name: str, command: str) -> list[str]:
    shell_name = shell_name.lower()

    if shell_name in ("bash", ""):
        return ["bash", "-lc", command]
    if shell_name == "sh":
        return ["sh", "-lc", command]
    if shell_name in ("pwsh", "powershell"):
        return ["pwsh", "-NoLogo", "-NoProfile", "-Command", command]
    if shell_name == "cmd":
        return ["cmd", "/d", "/s", "/c", command]

    return [shell_name, "-lc", command]


def choose_output_path(config: dict[str, Any], task: Task) -> Path:
    output_path = deep_get(task.meta, "output.path", "")
    if output_path:
        return Path(output_path)

    output_dir = Path(config.get("output_dir", ".action-agent/output"))
    return output_dir / f"{task.path.stem}.log"


def write_output_line(output_file, line: str) -> None:
    if output_file is not None:
        output_file.write(line)
        output_file.flush()


def run_single_command(
    command: str,
    *,
    shell_name: str,
    cwd: Path,
    env: dict[str, str],
    timeout: int,
    output_mode: str,
    output_file,
) -> int:
    start = time.monotonic()
    header = f"\n$ {command}\n"

    if output_mode in ("log", "both"):
        print(header, end="")
    write_output_line(output_file, header)

    try:
        result = subprocess.run(
            shell_command(shell_name, command),
            cwd=str(cwd),
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        output = e.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")

        timeout_message = f"\nActionAgent: command timed out after {timeout}s\n"
        combined = output + timeout_message

        if output_mode in ("log", "both"):
            print(combined, end="")
        write_output_line(output_file, combined)
        return 124

    if result.stdout:
        if output_mode in ("log", "both"):
            print(result.stdout, end="")
        write_output_line(output_file, result.stdout)

    elapsed = time.monotonic() - start
    footer = f"\nActionAgent: command exited with {result.returncode} in {elapsed:.2f}s\n"

    if output_mode in ("log", "both"):
        print(footer, end="")
    write_output_line(output_file, footer)

    return int(result.returncode)


def run_command_group(
    commands: list[str],
    *,
    group_name: str,
    shell_name: str,
    cwd: Path,
    env: dict[str, str],
    timeout_left: callable,
    output_mode: str,
    output_file,
) -> int:
    if not commands:
        return 0

    group_header = f"\n--- {group_name} ---\n"
    if output_mode in ("log", "both"):
        print(group_header, end="")
    write_output_line(output_file, group_header)

    for command in commands:
        remaining = timeout_left()
        if remaining <= 0:
            message = "ActionAgent: task timeout reached before command started\n"
            if output_mode in ("log", "both"):
                print(message, end="")
            write_output_line(output_file, message)
            return 124

        code = run_single_command(
            command,
            shell_name=shell_name,
            cwd=cwd,
            env=env,
            timeout=remaining,
            output_mode=output_mode,
            output_file=output_file,
        )

        if code != 0:
            return code

    return 0


def run_task(config: dict[str, Any], task: Task) -> tuple[int, Path | None]:
    name = str(task.meta.get("name", task.path.stem))
    reason = str(task.meta.get("reason", ""))

    timeout = int(task.meta.get("timeout", config.get("default_timeout", 600)))
    cwd = Path(deep_get(task.meta, "execution.cwd", deep_get(config, "execution.default_cwd", ".")))
    shell_name = str(deep_get(task.meta, "execution.shell", deep_get(config, "execution.default_shell", "bash")))

    output_mode = str(deep_get(task.meta, "output.mode", deep_get(config, "output.mode", "both"))).lower()
    if output_mode not in ("log", "file", "both", "none"):
        output_mode = "both"

    output_path: Path | None = None
    output_file = None

    if output_mode in ("file", "both"):
        output_path = choose_output_path(config, task)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_file = output_path.open("w", encoding="utf-8")

    before_commands = as_list(deep_get(task.meta, "commands.before", []))
    run_commands = as_list(deep_get(task.meta, "commands.run", []))
    after_commands = as_list(deep_get(task.meta, "commands.after", []))

    if not run_commands:
        run_commands = as_list(deep_get(config, "commands.default_run", []))

    if not run_commands:
        message = f"ActionAgent: task {task.path} has no [commands].run entries.\n"
        if output_mode in ("log", "both"):
            print(message, end="")
        write_output_line(output_file, message)
        if output_file is not None:
            output_file.close()
        return 2, output_path

    env = os.environ.copy()
    env["ACTION_AGENT_TASK"] = str(task.path)
    env["ACTION_AGENT_TASK_NAME"] = name
    if output_path is not None:
        env["ACTION_AGENT_OUTPUT"] = str(output_path)

    for key, value in dict(task.meta.get("env", {})).items():
        env[str(key)] = str(value)

    start_time = time.monotonic()

    def timeout_left() -> int:
        elapsed = time.monotonic() - start_time
        return max(0, int(timeout - elapsed))

    banner = (
        "=" * 80
        + f"\nActionAgent: running task: {name}\n"
        + f"File: {task.path}\n"
        + f"Reason: {reason}\n"
        + f"Timeout: {timeout}s\n"
        + f"CWD: {cwd}\n"
        + f"Shell: {shell_name}\n"
        + "=" * 80
        + "\n"
    )

    if output_mode in ("log", "both"):
        print(banner, end="")
    write_output_line(output_file, banner)

    code = 0

    try:
        code = run_command_group(
            before_commands,
            group_name="before",
            shell_name=shell_name,
            cwd=cwd,
            env=env,
            timeout_left=timeout_left,
            output_mode=output_mode,
            output_file=output_file,
        )

        if code == 0:
            code = run_command_group(
                run_commands,
                group_name="run",
                shell_name=shell_name,
                cwd=cwd,
                env=env,
                timeout_left=timeout_left,
                output_mode=output_mode,
                output_file=output_file,
            )

        after_policy = str(deep_get(task.meta, "execution.after", "always")).lower()
        should_run_after = after_policy == "always" or (after_policy == "success" and code == 0) or (after_policy == "failure" and code != 0)

        if should_run_after:
            after_code = run_command_group(
                after_commands,
                group_name="after",
                shell_name=shell_name,
                cwd=cwd,
                env=env,
                timeout_left=timeout_left,
                output_mode=output_mode,
                output_file=output_file,
            )
            if code == 0 and after_code != 0:
                code = after_code

    finally:
        elapsed = time.monotonic() - start_time
        footer = "=" * 80 + f"\nActionAgent: task exited with {code} in {elapsed:.2f}s\n" + "=" * 80 + "\n"
        if output_mode in ("log", "both"):
            print(footer, end="")
        write_output_line(output_file, footer)

        if output_file is not None:
            output_file.close()

    return code, output_path


def reset_task_run_flag(task: Task) -> bool:
    source = task.path.read_text(encoding="utf-8")
    doc = source[task.doc_start:task.doc_end]

    new_doc, count = re.subn(
        r"(?m)^(\s*run\s*=\s*)true(\s*(?:#.*)?$)",
        r"\1false\2",
        doc,
        count=1,
    )

    if count == 0:
        return False

    new_source = source[:task.doc_start] + new_doc + source[task.doc_end:]
    task.path.write_text(new_source, encoding="utf-8")
    return True


def git_commit(paths: list[Path], message: str) -> None:
    paths = [path for path in paths if path.exists()]
    if not paths:
        return

    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
    subprocess.run(
        ["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"],
        check=True,
    )

    for path in paths:
        subprocess.run(["git", "add", "-f", str(path)], check=True)

    status = subprocess.run(
        ["git", "status", "--porcelain", "--"] + [str(path) for path in paths],
        stdout=subprocess.PIPE,
        text=True,
        check=True,
    )

    if not status.stdout.strip():
        print("ActionAgent: no selected changes to commit.")
        return

    result = subprocess.run(
        ["git", "commit", "-m", message],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    print(result.stdout)

    if result.returncode == 0:
        subprocess.run(["git", "push"], check=True)


def write_result_file(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_output_excerpt(path: Path, max_bytes: int) -> str:
    if max_bytes <= 0 or not path.exists() or not path.is_file():
        return ""

    with path.open("rb") as file:
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(max(0, size - max_bytes))
        data = file.read()

    text = data.decode("utf-8", errors="replace")
    if len(data) == max_bytes:
        return "[output truncated to last bytes]\n" + text
    return text


def output_size(path: Path | None) -> int | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    return path.stat().st_size


def workflow_run_url() -> str | None:
    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com").strip().rstrip("/")
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    run_id = os.environ.get("GITHUB_RUN_ID", "").strip()

    if not repository or not run_id:
        return None

    return f"{server_url}/{repository}/actions/runs/{run_id}"


def main() -> int:
    config = load_toml_file(CONFIG_PATH)
    run_started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    max_tasks = int(config.get("max_tasks", 8))
    tasks = discover_tasks(config)
    result_path = Path(config.get("result_file", ".action-agent/result.json"))
    commit_result = bool(config.get("commit_result", True))
    fail_workflow_on_task_failure = bool(deep_get(config, "execution.fail_workflow_on_task_failure", False))
    result: dict[str, Any] = {
        "version": 1,
        "started_at": run_started,
        "finished_at": None,
        "workflow_run_url": workflow_run_url(),
        "status": "running",
        "failed": False,
        "message": "",
        "tasks": [],
    }

    if not tasks:
        print("ActionAgent: no run=true tasks found.")
        return 1 if bool(deep_get(config, "execution.fail_if_no_task", False)) else 0

    if len(tasks) > max_tasks:
        print(f"ActionAgent: too many enabled tasks: {len(tasks)} > max_tasks={max_tasks}")
        result["status"] = "error"
        result["failed"] = True
        result["message"] = f"Too many enabled tasks: {len(tasks)} > max_tasks={max_tasks}"
        result["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        write_result_file(result_path, result)
        if commit_result:
            git_commit([result_path], "action-agent: update result [action-agent skip]")
        return 1 if fail_workflow_on_task_failure else 0

    reset_after_run = bool(config.get("reset_after_run", True))
    commit_reset = bool(config.get("commit_reset", True))
    commit_outputs_global = bool(config.get("commit_outputs", False))
    global_continue_on_error = bool(deep_get(config, "execution.continue_on_error", False))
    default_reset_on = str(deep_get(config, "execution.default_reset_on", "always")).lower()
    output_excerpt_bytes = int(deep_get(config, "output.excerpt_bytes", 20000))
    failed_output_excerpt_bytes = int(deep_get(config, "output.failed_excerpt_bytes", output_excerpt_bytes))

    failed = False
    reset_paths: list[Path] = []
    output_commit_paths: list[Path] = []

    for task in tasks:
        code, output_path = run_task(config, task)
        output_commit = False
        output_artifact = False
        output_exists = output_path.exists() if output_path is not None else False
        task_excerpt_bytes = failed_output_excerpt_bytes if code != 0 else output_excerpt_bytes

        if output_path is not None:
            output_commit = bool(deep_get(task.meta, "output.commit", deep_get(config, "output.commit", commit_outputs_global)))
            output_artifact = bool(deep_get(task.meta, "output.artifact", deep_get(config, "output.artifact", True)))
            task_excerpt_bytes = int(
                deep_get(
                    task.meta,
                    "output.failed_excerpt_bytes" if code != 0 else "output.excerpt_bytes",
                    task_excerpt_bytes,
                )
            )

        task_result: dict[str, Any] = {
            "path": str(task.path),
            "name": str(task.meta.get("name", task.path.stem)),
            "exit_code": code,
            "status": "success" if code == 0 else "failed",
            "output_path": str(output_path) if output_path is not None else None,
            "output_exists": output_exists,
            "output_size_bytes": output_size(output_path),
            "output_committed": output_commit,
            "output_artifact": output_artifact,
            "output_excerpt_bytes": task_excerpt_bytes,
            "output_excerpt": read_output_excerpt(output_path, task_excerpt_bytes) if output_path is not None else "",
            "reset": False,
        }

        if output_path is not None and output_commit:
            output_commit_paths.append(output_path)

        reset_on = str(deep_get(task.meta, "execution.reset_on", default_reset_on)).lower()
        should_reset = reset_after_run and (
            reset_on == "always" or (reset_on == "success" and code == 0)
        )

        if should_reset and reset_task_run_flag(task):
            reset_paths.append(task.path)
            task_result["reset"] = True

        result["tasks"].append(task_result)

        continue_on_error = bool(deep_get(task.meta, "execution.continue_on_error", global_continue_on_error))

        if code != 0:
            failed = True
            if not continue_on_error:
                print("ActionAgent: stopping because task failed.")
                break

    commit_paths: list[Path] = []
    if commit_reset:
        commit_paths.extend(reset_paths)
    if commit_outputs_global or output_commit_paths:
        commit_paths.extend(output_commit_paths)
    result["failed"] = failed
    result["status"] = "failed" if failed else "success"
    result["message"] = "One or more tasks failed." if failed else "All enabled tasks completed successfully."
    result["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write_result_file(result_path, result)
    if commit_result:
        commit_paths.append(result_path)

    if commit_paths:
        unique_paths = []
        seen = set()
        for path in commit_paths:
            key = str(path)
            if key not in seen:
                seen.add(key)
                unique_paths.append(path)

        git_commit(unique_paths, "action-agent: update runtime state [action-agent skip]")

    return 1 if failed and fail_workflow_on_task_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
