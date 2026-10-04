from __future__ import annotations

import pathlib
import sys
import unittest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import publish_bookings_snapshot_issue as publisher  # noqa: E402


REPORT = "# Снимок\n\nSerodes\n"


class FakeGitHub:
    def __init__(self, existing: bool = False, pin_status: int = 200) -> None:
        self.existing = existing
        self.pin_status = pin_status
        self.calls: list[tuple[str, str, object]] = []
        self.comment = (
            {"id": 99, "body": publisher.comment_body("old")} if existing else None
        )

    def __call__(self, method: str, path: str, payload: dict | None) -> tuple[int, object]:
        self.calls.append((method, path, payload))
        if "beds24" in path:
            raise AssertionError(path)
        if method == "GET" and path.startswith("/search/issues"):
            if not self.existing:
                return 200, {"items": []}
            return 200, {
                "items": [
                    {
                        "number": 7,
                        "title": publisher.ISSUE_TITLE,
                        "state": "open",
                    }
                ]
            }
        if method == "GET" and "/comments" in path:
            return 200, [] if self.comment is None else [self.comment]
        if method == "GET" and "/issues?" in path:
            return 200, []
        if method == "POST" and path.endswith("/issues"):
            return 201, {"number": 7}
        if method == "POST" and path.endswith("/comments"):
            self.comment = {"id": 99, "body": payload["body"] if payload else ""}
            return 201, {"id": 99}
        if method == "PATCH":
            return 200, {"id": 99, "number": 7}
        if method == "PUT" and path.endswith("/pin"):
            if self.pin_status >= 400:
                return self.pin_status, {"message": "Resource not accessible by integration"}
            return 200, {}
        raise AssertionError((method, path))


class PublishTests(unittest.TestCase):
    def test_comment_marker(self) -> None:
        body = publisher.comment_body(REPORT)
        self.assertTrue(body.startswith(publisher.MARKER))
        self.assertIn("Serodes", body)

    def test_creates_issue_comment_and_pin(self) -> None:
        github = FakeGitHub()
        result = publisher.upsert_snapshot_issue(github, "acme/book", REPORT)
        methods = [call[0] for call in github.calls]
        self.assertEqual(result.issue_number, 7)
        self.assertEqual(result.issue_url, "https://github.com/acme/book/issues/7")
        self.assertEqual(result.comment_id, 99)
        self.assertEqual(result.pin_status, "ok")
        self.assertIn("POST", methods)
        self.assertIn("PUT", methods)
        self.assertTrue(any(path.endswith("/pin") for _, path, _ in github.calls))

    def test_updates_existing_comment(self) -> None:
        github = FakeGitHub(existing=True)
        result = publisher.upsert_snapshot_issue(github, "acme/book", REPORT)
        posts = [path for method, path, _ in github.calls if method == "POST"]
        self.assertEqual(posts, [])
        self.assertEqual(result.comment_id, 99)
        self.assertTrue(any(method == "PATCH" and "/comments/" in path for method, path, _ in github.calls))

    def test_pin_failure_still_returns_the_issue(self) -> None:
        github = FakeGitHub(pin_status=403)
        result = publisher.upsert_snapshot_issue(github, "acme/book", REPORT)
        self.assertEqual(result.pin_status, "failed")
        self.assertIn("403", result.pin_error)
        self.assertEqual(result.issue_url, "https://github.com/acme/book/issues/7")


if __name__ == "__main__":
    unittest.main()
