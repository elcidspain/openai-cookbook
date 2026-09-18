# Checkpoint — AUMARA Booking Fully flexible + Weekly (channels API)

| Field | Content |
| --- | --- |
| Objective | Merge-ready opener that writes inventory through 2028-12-31, documents one invite including channels, and opens Fully flexible + Weekly via `/channels/settings` when the token has channels scopes. Record hotel 16137893 vs 14953869 from `GET /properties`. |
| Status | in progress — unit tests green; live channel open blocked on invite; live hotel linkage pending next open-availability run |
| Scope | `aumara-control-tower/scripts/beds24_open_booking_availability.py` + tests; `.github/workflows/beds24-open-booking-availability.yml` (unchanged wiring); `aumara-control-tower/systems/beds24-continuity.md`; `aumara-control-tower/docs/BEDS24_BOOKING_RATES_AVAIL_MAP.md`. Authorized: inventory calendar writes and channels settings writes when scoped. Exclusions: passwords, browser login, COOKBOOK examples/registry, Gmail, new secret names. |
| Evidence | `origin/main` `3b6126a6`; live run 35380827175 (scopes: 10 booking/property/inventory R/W, `has_channels_scope=false`, channels GET 401, CHALET 3/259 Superior 2/329 offers bookable). OpenAPI `apiV2.yaml`: invite scopes include `channels`; `/channels/settings` Alpha enum is airbnb/vrbo/iCal; opener still uses `channel=booking`. V1 content audit mapped hotel 14953869. Continuity lists working 16137893. |
| Changes | See this PR. |
| Tests | `python3 -m unittest aumara-control-tower/scripts/tests/test_beds24_open_booking_availability.py -v` — 15 passed. Auth-check tests still 10 passed. |
| Stop condition | PR with workflow+script+docs. Channel POST skipped until `read:channels`+`write:channels`. |
| Recovery point | Branch `cursor/beds24-booking-channel-rates-d78b`. Next safe action: merge, Ilia generates one invite with channels, exchange into `BEDS24_REFRESH_CREDENTIAL`, then `[open-availability]`. |

No secrets in this file.
