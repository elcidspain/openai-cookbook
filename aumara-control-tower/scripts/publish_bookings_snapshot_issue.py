#!/usr/bin/env python3
"""Publish the bookings snapshot on one pinned GitHub issue.

The Beds24 script stays read-only. This publisher only talks to GitHub: it
creates or reuses the issue titled "AUMARA bookings snapshot", updates one
marked comment, and pins the issue.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


ISSUE_TITLE = "AUMARA bookings snapshot"
MARKER = "<!-- aumara-bookings-snapshot -->"
GitHubRequest = Callable[[str, str, dict[str, Any] | None], tuple[int, Any]]


@dataclass(frozen=True)
class PublishResult:
    issue_number: int
    issue_url: str
    comment_id: int
    pin_status: str
    pin_error: str


def comment_body(report: str) -> str:
    return MARKER + "\n\n" + report.strip() + "\n"


def _error_text(body: Any) -> str:
    if isinstance(body, dict):
        message = body.get("message") or body.get("error") or body
        return json.dumps(message, ensure_ascii=False)[:500]
    return str(body)[:500]


def _items(body: Any) -> list[dict[str, Any]]:
    if isinstance(body, list):
        return [item for item in body if isinstance(item, dict)]
    if isinstance(body, dict) and isinstance(body.get("items"), list):
        return [item for item in body["items"] if isinstance(item, dict)]
    return []


def find_issue(request: GitHubRequest, repo: str) -> dict[str, Any] | None:
    query = f'repo:{repo} is:issue in:title "{ISSUE_TITLE}"'
    status, body = request(
        "GET",
        "/search/issues?" + urllib.parse.urlencode({"q": query, "per_page": "20"}),
        None,
    )
    candidates = _items(body) if status == 200 else []
    if not candidates:
        status, body = request(
            "GET",
            f"/repos/{repo}/issues?state=all&per_page=100",
            None,
        )
        if status != 200:
            raise RuntimeError(f"GitHub issue lookup failed HTTP {status}: {_error_text(body)}")
        candidates = [
            item
            for item in _items(body)
            if "pull_request" not in item and item.get("title") == ISSUE_TITLE
        ]
    exact = [item for item in candidates if item.get("title") == ISSUE_TITLE]
    if not exact:
        return None
    opened = [item for item in exact if item.get("state") == "open"]
    return (opened or exact)[0]


def list_comments(request: GitHubRequest, repo: str, number: int) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for page in range(1, 11):
        status, body = request(
            "GET",
            f"/repos/{repo}/issues/{number}/comments?per_page=100&page={page}",
            None,
        )
        if status != 200:
            raise RuntimeError(f"GitHub comment lookup failed HTTP {status}: {_error_text(body)}")
        rows = _items(body)
        found.extend(rows)
        if len(rows) < 100:
            break
    return found


def upsert_snapshot_issue(
    request: GitHubRequest,
    repo: str,
    report: str,
    *,
    server: str = "https://github.com",
) -> PublishResult:
    body = comment_body(report)
    existing = find_issue(request, repo)
    if existing is None:
        status, created = request(
            "POST",
            f"/repos/{repo}/issues",
            {"title": ISSUE_TITLE, "body": body},
        )
        if status not in (200, 201) or not isinstance(created, dict) or not created.get("number"):
            raise RuntimeError(f"GitHub issue create failed HTTP {status}: {_error_text(created)}")
        number = int(created["number"])
    else:
        number = int(existing["number"])
        status, updated = request(
            "PATCH",
            f"/repos/{repo}/issues/{number}",
            {"title": ISSUE_TITLE, "body": body, "state": "open"},
        )
        if status not in (200, 201):
            raise RuntimeError(f"GitHub issue update failed HTTP {status}: {_error_text(updated)}")

    comments = list_comments(request, repo, number)
    current = next(
        (
            item
            for item in comments
            if str(item.get("body") or "").lstrip().startswith(MARKER)
        ),
        None,
    )
    if current is None:
        status, comment = request(
            "POST",
            f"/repos/{repo}/issues/{number}/comments",
            {"body": body},
        )
        if status not in (200, 201) or not isinstance(comment, dict) or not comment.get("id"):
            raise RuntimeError(f"GitHub comment create failed HTTP {status}: {_error_text(comment)}")
        comment_id = int(comment["id"])
    else:
        comment_id = int(current["id"])
        status, comment = request(
            "PATCH",
            f"/repos/{repo}/issues/comments/{comment_id}",
            {"body": body},
        )
        if status not in (200, 201):
            raise RuntimeError(f"GitHub comment update failed HTTP {status}: {_error_text(comment)}")

    status, pin_body = request("PUT", f"/repos/{repo}/issues/{number}/pin", None)
    pin_text = _error_text(pin_body).casefold()
    if 200 <= status < 300 or ("already" in pin_text and "pin" in pin_text):
        pin_status = "ok"
        pin_error = ""
    else:
        pin_status = "failed"
        pin_error = f"pin HTTP {status}: {_error_text(pin_body)}"

    return PublishResult(
        issue_number=number,
        issue_url=f"{server.rstrip('/')}/{repo}/issues/{number}",
        comment_id=comment_id,
        pin_status=pin_status,
        pin_error=pin_error,
    )


def github_request(token: str) -> GitHubRequest:
    def request(method: str, path: str, payload: dict[str, Any] | None) -> tuple[int, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "AUMARA-BookingsSnapshot",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(
            "https://api.github.com" + path,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                raw = response.read()
                status = int(response.status)
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            status = int(exc.code)
        text = raw.decode("utf-8", "replace")
        try:
            parsed: Any = json.loads(text) if text else {}
        except json.JSONDecodeError:
            parsed = {"message": text[:500]}
        return status, parsed

    return request


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: publish_bookings_snapshot_issue.py REPORT.md", file=sys.stderr)
        return 2
    token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    repo = (os.environ.get("GITHUB_REPOSITORY") or "").strip()
    if not token or not repo:
        print("GITHUB_TOKEN and GITHUB_REPOSITORY are required", file=sys.stderr)
        return 1
    report = open(args[0], encoding="utf-8").read()
    server = os.environ.get("GITHUB_SERVER_URL") or "https://github.com"
    try:
        result = upsert_snapshot_issue(
            github_request(token),
            repo,
            report,
            server=server,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"issue_url={result.issue_url}")
    print(f"comment_id={result.comment_id}")
    print(f"pin_status={result.pin_status}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(f"\n\nIssue: {result.issue_url}\n")
            if result.pin_error:
                handle.write(f"Pin: {result.pin_error}\n")
    if result.pin_error:
        print(result.pin_error, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
