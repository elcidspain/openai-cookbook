# Checkpoint — Beds24 listing descriptions 2026-10-04

| Field | Content |
| --- | --- |
| Objective | Write description texts only for Beds24 property 324882 and rooms 674465 and 674466 from the content file at commit 7637d743. |
| Status | in progress |
| Scope | V2 `POST /properties` texts for that property and those two rooms. Allowed paths: the one-off workflow, `beds24_listing_descriptions_20261004.py`, its unit test, the trigger file, the backup, the verification JSON, and this checkpoint. Excluded: prices, photos, availability, min stay, rates, feature codes, channel settings, V1 keys. |
| Evidence | Source file `aumara-control-tower/content/beds24-standard-content-20261004.json` at `7637d743` sha256 `7af95f0e4acfb9679c2a19bb8c0db4f20cf46469da5a5970d013d0e1c4868b25`. Guard found no `aumara.me`, `directa`, URL, `CV H01453`, pool/piscina, tenis, or playa. `camping` appears only as `No es un camping`. Auth matches `.github/workflows/beds24-bookings-snapshot.yml` (`BEDS24_REFRESH_CREDENTIAL`, cron `7 6 * * *`). V2 text fields come from `https://beds24.com/api/v2/apiV2.yaml`. |
| Changes | Push-triggered one-off workflow. Backup is committed before the write. The workflow deletes itself only after a matching re-read. |
| Tests | `python -m unittest aumara-control-tower/scripts/tests/test_beds24_listing_descriptions_20261004.py -v` |
| Stop condition | Merged workflow run backs up texts, writes them, re-reads a match, and removes the workflow. A V2 scope error stops with the exact API error and no V1 attempt. |
| Recovery point | Branch `cursor/beds24-listing-descriptions-4d16`. Next safe action: merge after the unit-test check, then read the Actions run. |

No secrets in this file.
