from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:
    print("ActionAgent commenter requires Python 3.11+ for tomllib.")
    sys.exit(1)

CONFIG_PATH = Path(".action-agent/run.toml")
DEFAULT_RESULT_MARKER = "<!-- action-agent-result:v1 -->"
DEFAULT_CONTROL_MARKER = "<!-- action-agent-issue:v1 -->"


class GitHubApiError(RuntimeError):
    def __init__(self, method: str, url: str, status: int, message: str) -> None:
        super().__init__(f"GitHub API {method} {url} failed: {status} {message}")
        self.method = method
        self.url = url
        self.status = status
        self.message = message


def warn(message: str) -> None:
    print(f"ActionAgent commenter warning: {message}")


def load_toml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))


def deep_get(data: dict[str, Any], key: str, default: Any = None) -> Any:
    current: Any = data
    for part in key.split("."):
        if not isinstance(current, dict):
            return default
        current = current.get(part)
    return default if current is None else current


def as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def byte_len(text: str) -> int:
    return len(text.encode("utf-8"))


def truncate_utf8(text: str, max_bytes: int, suffix: str) -> str:
    if max_bytes <= 0 or byte_len(text) <= max_bytes:
        return text

    suffix_bytes = byte_len(suffix)
    budget = max(0, max_bytes - suffix_bytes)
    data = text.encode("utf-8")[:budget]
    return data.decode("utf-8", errors="ignore") + suffix


def github_request(method: str, url: str, *, token: str, body: dict[str, Any] | None = None) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url=url, data=data, method=method)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data is not None:
        request.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        raise GitHubApiError(method, url, exc.code, message) from exc


def list_issue_comments(api_url: str, repo: str, issue: int, *, token: str) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    page = 1
    while True:
        url = f"{api_url}/repos/{repo}/issues/{issue}/comments?per_page=100&page={page}"
        batch = github_request("GET", url, token=token)
        if not batch:
            break
        comments.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return comments


def list_repo_issues(api_url: str, repo: str, *, token: str, state: str = "open") -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    page = 1
    while True:
        url = f"{api_url}/repos/{repo}/issues?state={state}&per_page=100&page={page}"
        batch = github_request("GET", url, token=token)
        if not batch:
            break
        issues.extend(item for item in batch if not item.get("pull_request"))
        if len(batch) < 100:
            break
        page += 1
    return issues


def get_issue(api_url: str, repo: str, issue: int, *, token: str) -> dict[str, Any] | None:
    url = f"{api_url}/repos/{repo}/issues/{issue}"
    try:
        data = github_request("GET", url, token=token)
    except GitHubApiError as exc:
        if exc.status == 404:
            return None
        raise
    if isinstance(data, dict) and not data.get("pull_request"):
        return data
    return None


def create_control_issue(api_url: str, repo: str, *, token: str, config: dict[str, Any]) -> dict[str, Any] | None:
    title = str(deep_get(config, "comment.auto_issue_title", "ActionAgent"))[:256] or "ActionAgent"
    marker = str(deep_get(config, "comment.auto_issue_marker", DEFAULT_CONTROL_MARKER))
    body = str(deep_get(config, "comment.auto_issue_body", "ActionAgent run results and summaries."))
    if marker and marker not in body:
        body = f"{marker}\n\n{body}".strip() + "\n"

    labels_value = deep_get(config, "comment.auto_issue_labels", [])
    labels = labels_value if isinstance(labels_value, list) else []
    payload: dict[str, Any] = {"title": title, "body": body}
    if labels:
        payload["labels"] = [str(label) for label in labels]

    url = f"{api_url}/repos/{repo}/issues"
    created = github_request("POST", url, token=token, body=payload)
    if isinstance(created, dict) and created.get("number"):
        print(f"ActionAgent commenter: created control issue #{created['number']} ({title}).")
        return created
    warn("GitHub returned no issue number after creating the control issue.")
    return None


def find_control_issue(api_url: str, repo: str, *, token: str, config: dict[str, Any]) -> dict[str, Any] | None:
    title = str(deep_get(config, "comment.auto_issue_title", "ActionAgent"))
    marker = str(deep_get(config, "comment.auto_issue_marker", DEFAULT_CONTROL_MARKER))
    state = str(deep_get(config, "comment.auto_issue_state", "open")).lower()
    if state not in {"open", "closed", "all"}:
        warn(f"invalid comment.auto_issue_state={state!r}; using open.")
        state = "open"

    issues = list_repo_issues(api_url, repo, token=token, state=state)
    title_matches = [item for item in issues if str(item.get("title") or "") == title]
    marked = [item for item in title_matches if marker and marker in str(item.get("body") or "")]
    candidates = marked or title_matches
    candidates.sort(key=lambda item: str(item.get("created_at") or ""))

    if len(candidates) > 1:
        warn(
            f"found {len(candidates)} candidate control issues titled {title!r}; "
            f"using the oldest open match #{candidates[0].get('number')}."
        )
    if candidates:
        issue = candidates[0]
        print(f"ActionAgent commenter: using control issue #{issue.get('number')} ({title}).")
        return issue
    return None


def resolve_issue_number(api_url: str, repo: str, *, token: str, config: dict[str, Any]) -> int | None:
    raw_issue = deep_get(config, "comment.issue", "auto")
    auto_create = as_bool(deep_get(config, "comment.auto_create_issue", True), True)

    if isinstance(raw_issue, int) or (isinstance(raw_issue, str) and raw_issue.strip().isdigit()):
        number = as_int(raw_issue, 0)
        if number <= 0:
            warn(f"invalid numeric comment.issue={raw_issue!r}; falling back to auto resolution.")
        else:
            existing = get_issue(api_url, repo, number, token=token)
            if existing:
                state = existing.get("state", "unknown")
                if state != "open":
                    warn(f"configured issue #{number} is {state}; comments can still be posted, but auto mode is safer.")
                print(f"ActionAgent commenter: using configured issue #{number}.")
                return number
            warn(f"configured issue #{number} does not exist or is a pull request.")
            if not auto_create:
                warn("comment.auto_create_issue is false; skipping issue comments.")
                return None

    elif isinstance(raw_issue, str) and raw_issue.strip().lower() != "auto":
        warn(f"unsupported comment.issue={raw_issue!r}; expected an issue number or 'auto'.")
        if not auto_create:
            return None

    issue = find_control_issue(api_url, repo, token=token, config=config)
    if issue and issue.get("number"):
        return int(issue["number"])

    if not auto_create:
        warn("no ActionAgent control issue found and auto_create_issue=false; skipping issue comments.")
        return None

    created = create_control_issue(api_url, repo, token=token, config=config)
    if created and created.get("number"):
        return int(created["number"])
    return None


def build_task_section(task: dict[str, Any], *, mode: str) -> str:
    lines = [
        f"- Status: `{task.get('status', 'unknown')}`",
        f"- Exit code: `{task.get('exit_code', 'unknown')}`",
    ]

    output_path = task.get("output_path")
    if output_path:
        lines.append(f"- Output path: `{output_path}`")
    output_size = task.get("output_size_bytes")
    if output_size is not None:
        lines.append(f"- Output size: `{output_size}` bytes")
    if task.get("output_artifact"):
        lines.append("- Full output: included in the workflow artifact")
    elif task.get("output_committed") and output_path:
        lines.append("- Full output: committed to the repository output path")

    comment_truncated = bool(task.get("comment_excerpt_truncated"))
    comment_limit = task.get("comment_excerpt_bytes")
    if comment_limit is not None:
        trunc = ", truncated" if comment_truncated else ""
        lines.append(f"- Comment excerpt limit: `{comment_limit}` bytes{trunc}")

    excerpt = str(task.get("comment_excerpt") or "")
    if mode in ("excerpt", "full") and excerpt:
        lines.extend([
            "",
            "<details open>",
            "<summary>Output excerpt</summary>",
            "",
            "```text",
            excerpt.rstrip(),
            "```",
            "</details>",
        ])

    return "\n".join(lines).rstrip()


def build_comment(result: dict[str, Any], config: dict[str, Any], *, issue_number: int) -> str:
    marker = str(deep_get(config, "comment.marker", DEFAULT_RESULT_MARKER))
    mode = str(deep_get(config, "comment.mode", "excerpt")).lower()
    if mode not in ("summary", "excerpt", "full"):
        warn(f"invalid comment.mode={mode!r}; using excerpt.")
        mode = "excerpt"

    status = result.get("status", "unknown")
    icon = "✅" if status == "success" else "❌" if status == "failed" else "⚠️"
    run_url = result.get("workflow_run_url")
    artifact_name = str(deep_get(config, "comment.artifact_name", "action-agent-output"))

    lines = [
        marker,
        "",
        f"{icon} **ActionAgent finished**",
        "",
        f"- Issue: `#{issue_number}`",
        f"- Status: `{status}`",
        f"- Started: `{result.get('started_at', '')}`",
        f"- Finished: `{result.get('finished_at', '')}`",
    ]
    if result.get("message"):
        lines.append(f"- Message: {result.get('message')}")
    if run_url:
        lines.append(f"- Workflow run: {run_url}")
    lines.append(f"- Artifact: `{artifact_name}`")

    tasks = result.get("tasks") or []
    if tasks:
        lines.extend(["", "## Tasks"])
        for index, task in enumerate(tasks, start=1):
            lines.extend(["", f"#### {index}. {task.get('name') or task.get('path') or 'Task'}"])
            lines.append(build_task_section(task, mode=mode))
    else:
        lines.extend(["", "No task results were recorded in `result.json`."])

    return "\n".join(lines).rstrip() + "\n"


def trim_comment_body(body: str, max_comment_bytes: int) -> str:
    suffix = "\n\n[comment truncated by ActionAgent comment.max_comment_bytes]\n"
    return truncate_utf8(body, max_comment_bytes, suffix)


def cleanup_comments(
    *,
    api_url: str,
    repo: str,
    issue: int,
    token: str,
    marker: str,
    max_count: int,
    max_total_bytes: int,
    target_total_bytes: int,
    min_keep: int,
) -> None:
    if not marker.strip():
        warn("comment marker is empty; cleanup disabled to avoid deleting human comments.")
        return

    comments = list_issue_comments(api_url, repo, issue, token=token)
    managed = [comment for comment in comments if marker in str(comment.get("body") or "")]
    managed.sort(key=lambda item: str(item.get("created_at") or ""))

    to_delete: list[dict[str, Any]] = []

    while len(managed) > max_count:
        to_delete.append(managed.pop(0))

    def total_bytes(items: list[dict[str, Any]]) -> int:
        return sum(byte_len(str(item.get("body") or "")) for item in items)

    if total_bytes(managed) > max_total_bytes:
        while len(managed) > min_keep and total_bytes(managed) > target_total_bytes:
            to_delete.append(managed.pop(0))

    if not to_delete:
        print("ActionAgent commenter: no old result comments to delete.")
        return

    for comment in to_delete:
        comment_id = int(comment["id"])
        print(f"ActionAgent commenter: deleting old result comment {comment_id}.")
        url = f"{api_url}/repos/{repo}/issues/comments/{comment_id}"
        github_request("DELETE", url, token=token)
        time.sleep(0.2)


def normalized_cleanup_config(config: dict[str, Any]) -> tuple[int, int, int, int]:
    max_count = max(1, as_int(deep_get(config, "comment.cleanup.max_count", 10), 10))
    max_total_bytes = max(1, as_int(deep_get(config, "comment.cleanup.max_total_bytes", 60000), 60000))
    target_total_bytes = max(1, as_int(deep_get(config, "comment.cleanup.target_total_bytes", 55000), 55000))
    min_keep = max(1, as_int(deep_get(config, "comment.cleanup.min_keep", 3), 3))

    if min_keep > max_count:
        warn(f"comment.cleanup.min_keep={min_keep} exceeds max_count={max_count}; clamping min_keep to max_count.")
        min_keep = max_count
    if target_total_bytes > max_total_bytes:
        warn(
            f"comment.cleanup.target_total_bytes={target_total_bytes} exceeds "
            f"max_total_bytes={max_total_bytes}; clamping target to max_total_bytes."
        )
        target_total_bytes = max_total_bytes
    return max_count, max_total_bytes, target_total_bytes, min_keep


def run_commenter() -> int:
    config = load_toml_file(CONFIG_PATH)
    if not as_bool(deep_get(config, "comment.enabled", False), False):
        print("ActionAgent commenter: comment.enabled is false; skipping.")
        return 0

    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com").strip().rstrip("/")
    if not token:
        warn("missing GITHUB_TOKEN; skipping issue comment.")
        return 0
    if not repo:
        warn("missing GITHUB_REPOSITORY; skipping issue comment.")
        return 0

    result_path = Path(str(config.get("result_file", ".action-agent/result.json")))
    if not result_path.exists():
        warn(f"result file not found: {result_path}; skipping issue comment.")
        return 0

    result = json.loads(result_path.read_text(encoding="utf-8"))
    run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
    result_run_url = str(result.get("workflow_run_url") or "")
    if run_id and f"/actions/runs/{run_id}" not in result_run_url:
        print(
            "ActionAgent commenter: result.json does not belong to this workflow run; "
            "skipping stale result comment."
        )
        return 0

    issue = resolve_issue_number(api_url, repo, token=token, config=config)
    if not issue:
        warn("could not resolve an issue for comments; result.json and artifacts remain available.")
        return 0

    marker = str(deep_get(config, "comment.marker", DEFAULT_RESULT_MARKER))
    if not marker.strip():
        warn("comment.marker is empty; using the default result marker.")
        marker = DEFAULT_RESULT_MARKER
        config.setdefault("comment", {})["marker"] = marker

    max_comment_bytes = max(1000, as_int(deep_get(config, "comment.max_comment_bytes", 10000), 10000))
    body = trim_comment_body(build_comment(result, config, issue_number=issue), max_comment_bytes)
    create_url = f"{api_url}/repos/{repo}/issues/{issue}/comments"
    created = github_request("POST", create_url, token=token, body={"body": body})
    print(f"ActionAgent commenter: posted result comment {created.get('id') if isinstance(created, dict) else 'unknown'}.")

    if as_bool(deep_get(config, "comment.cleanup.enabled", True), True):
        max_count, max_total_bytes, target_total_bytes, min_keep = normalized_cleanup_config(config)
        cleanup_comments(
            api_url=api_url,
            repo=repo,
            issue=issue,
            token=token,
            marker=marker,
            max_count=max_count,
            max_total_bytes=max_total_bytes,
            target_total_bytes=target_total_bytes,
            min_keep=min_keep,
        )

    return 0


def main() -> int:
    try:
        return run_commenter()
    except GitHubApiError as exc:
        warn(
            f"GitHub API call failed with HTTP {exc.status}. "
            "Issue comments are optional; result.json and artifacts remain available. "
            "Check workflow permissions such as issues: write if comments should be posted."
        )
        print(exc.message[:2000])
        return 0
    except Exception as exc:  # noqa: BLE001 - comment publishing must not fail the ActionAgent run.
        warn(f"unexpected commenter error: {exc!r}; result.json and artifacts remain available.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
