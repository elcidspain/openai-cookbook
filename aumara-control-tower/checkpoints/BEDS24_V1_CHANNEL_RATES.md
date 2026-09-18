# Checkpoint — V1-first Booking Fully flexible + Weekly

| Field | Content |
| --- | --- |
| Objective | Open Booking Fully flexible + Weekly for property 324882 rooms 674465/674466 hotel 14953869 using existing Production V1 keys first; keep V2 channels path; do not ask Ilia to paste API keys. |
| Status | complete — PR #165 ready; live Production job waits on merge (`[open-channel-rates]`) |
| Scope | `beds24_v1_booking_rates.py`; extend `beds24_open_booking_channel_rates.py` + workflow (V1 Production secrets first); MAP + continuity mobile Marketplace invite nav. Authorized Beds24 writes: V1 rates/daily/roomDates and V2 channel settings when scoped. Exclusions: passwords, browser login, COOKBOOK registry, Gmail. |
| Evidence | Inspected origin/main `77ca3343`, PRs #163 merged / #164 #162 closed, archived rack-rate `setPropertyContent`, public V1 JSON (`getRates`/`setRates`/`setDailyPriceSetup`/`setRoomDates`/`setProperty` bookingComEnable*), V1 content audit rate `66887702` + `dailyPriceCount=1`. Local + GHA unit tests 15 OK (run 35383735249). Live `open-channel-rates` skipped on PR (dispatch/main-marker only). Unrelated Vercel `aumara-www-probe` / `elcid-evento-6agosto` blocked. |
| Changes | V1-first opener; workflow Production `BEDS24_API_KEY`+`BEDS24_PROP_KEY`; `[open-channel-rates]` live marker; invite wrong-page warning. |
| Tests | `python3 -m unittest aumara-control-tower/scripts/tests/test_beds24_open_booking_channel_rates.py -v` — 15 OK. GHA test job success; live job skipped until merge. |
| Stop condition | Requested workflow+docs+tests produced. Live Beds24 write starts when this PR merges with `[open-channel-rates]`. This agent cannot merge. |
| Recovery point | PR https://github.com/elcidspain/openai-cookbook/pull/165 branch `cursor/beds24-v1-channel-rates-84a2` commit `bd8a2d81`. Next: merge (keep marker in commit) → approve Production if prompted → read artifact `beds24-open-booking-channel-rates-evidence`. If V1 PARTIAL, Ilia uses SETTINGS > MARKETPLACE > API Generate invite (not API Key 1/2). |
