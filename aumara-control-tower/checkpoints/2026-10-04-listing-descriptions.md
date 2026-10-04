# Checkpoint — Beds24 listing descriptions 2026-10-04

| Field | Content |
| --- | --- |
| Objective | Write description texts only for Beds24 property 324882 and rooms 674465 and 674466 from the content file at commit 7637d743. |
| Status | complete |
| Scope | V2 `POST /properties` texts for that property and those two rooms. Excluded: prices, photos, availability, min stay, rates, feature codes, channel settings, Airbnb texts, V1 keys. |
| Evidence | Source sha256 `7af95f0e4acfb9679c2a19bb8c0db4f20cf46469da5a5970d013d0e1c4868b25`. Guard found no `aumara.me`, `directa`, URL, `CV H01453`, pool/piscina, tenis, or playa. `camping` only as `No es un camping`. Run `37226930533` on main commit `b324e258`. Read-back at `2026-10-04T19:06:08Z` status `SUCCESS`, mismatches `[]`, API base `https://api.beds24.com/v2`. |
| Changes | Backup `beds24/backup-content-20261004.json` (commit `ce0fe87c`, taken before the write). Verification `beds24/listing-descriptions-verify-20261004.json` (commit `af40917d`). One-off workflow and trigger removed in `af40917d`. |
| Tests | Unit tests: 6 passed on PR run `37226761108`. Live write run `37226930533` succeeded, including backup, write, re-read, and workflow removal. |
| Stop condition | Reached. Descriptions match the pinned source. Workflow is gone from main. |
| Recovery point | Main `af40917d`. Rollback body is the `property_texts` and `rooms` arrays in `beds24/backup-content-20261004.json`. No further write is scheduled. |

No secrets in this file.
