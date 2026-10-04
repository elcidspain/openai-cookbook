# Checkpoint — AUMARA daily Beds24 bookings snapshot

| Field | Content |
| --- | --- |
| Objective | Read-only daily Beds24 v2 bookings snapshot for property 324882 and the rest of the account, plus manual stays and unanswered guest messages. |
| Status | in progress — pause path included; live `workflow_dispatch` follows the merge |
| Scope | `aumara-control-tower/scripts/beds24_bookings_snapshot.py`, `publish_bookings_snapshot_issue.py`, their tests, `.github/workflows/beds24-bookings-snapshot.yml`, `bookings/manual.json`. GET only. No Beds24 writes, no guest-message sends, no Gmail, no credential changes. |
| Evidence | Auth reuses `BEDS24_REFRESH_CREDENTIAL` via GET `/authentication/token` (`beds24_minstay_fix.py`, `beds24_auth_check.py`). Bookings GET matches `beds24_finance_snapshot.py`. Messages GET matches `beds24_guest_message_ingest.py` (`source`, `maxAge`, scope `bookings-personal`). AUMARA rooms 674465 and 674466; EL CID 324903. |
| Changes | Russian markdown report, manual Serodes stay merged into arrivals and occupancy, unanswered 72h guest messages, daily 06:07 UTC workflow, one pinned issue comment. A blocked Beds24 read exits 0 and prints `⚠️ Beds24 аккаунт на паузе / API: <verbatim HTTP status and body>` plus the manual section. Token fields in those bodies are `[REDACTED]`. |
| Tests | `python3 -m unittest aumara-control-tower/scripts/tests/test_beds24_bookings_snapshot.py aumara-control-tower/scripts/tests/test_publish_bookings_snapshot_issue.py -v` — 12 passed. |
| Stop condition | PR merged, one `workflow_dispatch` run finished, issue URL and the first report text captured. |
| Recovery point | Branch `cursor/aumara-bookings-snapshot-9e09`. Next safe action: merge, dispatch `AUMARA bookings snapshot`, read the issue comment. |

No secrets in this file.
