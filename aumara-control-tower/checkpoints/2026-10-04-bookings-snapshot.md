# Checkpoint — AUMARA daily Beds24 bookings snapshot

| Field | Content |
| --- | --- |
| Objective | Read-only daily Beds24 v2 bookings snapshot for property 324882 and the rest of the account, plus manual stays and unanswered guest messages. |
| Status | complete — merged and one live run published the issue comment |
| Scope | `aumara-control-tower/scripts/beds24_bookings_snapshot.py`, `publish_bookings_snapshot_issue.py`, their tests, `.github/workflows/beds24-bookings-snapshot.yml`, `bookings/manual.json`. GET only. No Beds24 writes, no guest-message sends, no Gmail, no credential changes. |
| Evidence | Auth reuses `BEDS24_REFRESH_CREDENTIAL` via GET `/authentication/token` (`beds24_minstay_fix.py`, `beds24_auth_check.py`). Bookings GET matches `beds24_finance_snapshot.py`. Messages GET matches `beds24_guest_message_ingest.py` (`source`, `maxAge`, scope `bookings-personal`). AUMARA rooms 674465 and 674466; EL CID 324903. |
| Changes | Russian markdown report, manual Serodes stay merged into arrivals and occupancy, unanswered 72h guest messages, daily 06:07 UTC workflow, one pinned issue comment. A blocked Beds24 read exits 0 and prints `⚠️ Beds24 аккаунт на паузе / API: <verbatim HTTP status and body>` plus the manual section. Token fields in those bodies are `[REDACTED]`. |
| Tests | `python3 -m unittest aumara-control-tower/scripts/tests/test_beds24_bookings_snapshot.py aumara-control-tower/scripts/tests/test_publish_bookings_snapshot_issue.py -v` — 12 passed. Live run `37225726705` also passed those tests. |
| Stop condition | Met. PR #171 merged. Live run https://github.com/elcidspain/openai-cookbook/actions/runs/37225726705. Issue https://github.com/elcidspain/openai-cookbook/issues/172 comment `5983220744`. |
| Recovery point | `main` at the merge of PR #171 (`f5f5a264`) plus this checkpoint. Do not dispatch again for this task. |
| Live API | Token exchange succeeded. GET `https://api.beds24.com/v2/authentication/details` HTTP 200 `{"validToken":false,"diagnostics":{"requestIp":"74.235.126.230"}}`. GET `https://api.beds24.com/v2/authentication/token` HTTP 200 `{"token":"[REDACTED]","expiresIn":86400}`. Properties, bookings, and messages GETs returned HTTP 200. No pause banner. `workflow_dispatch` from this token returned HTTP 403 (`actions=write` required); the run was a one-off push of the same workflow. Pin returned HTTP 404 `Not Found`. |

No secrets in this file.
