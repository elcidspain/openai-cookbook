# Checkpoint — V1-first Booking Fully flexible + Weekly

| Field | Content |
| --- | --- |
| Objective | Open Booking Fully flexible + Weekly for property 324882 rooms 674465/674466 hotel 14953869 using existing Production V1 keys first; keep V2 channels path; do not ask Ilia to paste API keys. |
| Status | in progress |
| Scope | `beds24_v1_booking_rates.py`; extend `beds24_open_booking_channel_rates.py` + workflow (V1 Production secrets first); MAP + continuity mobile Marketplace invite nav. Authorized Beds24 writes: V1 rates/daily/roomDates and V2 channel settings when scoped. Exclusions: passwords, browser login, COOKBOOK registry, Gmail. |
| Evidence | Inspected origin/main `77ca3343`, PRs #163 merged / #164 #162 closed, archived rack-rate `setPropertyContent`, public V1 JSON (`getRates`/`setRates`/`setDailyPriceSetup`/`setRoomDates`/`setProperty` bookingComEnable*), V1 content audit rate `66887702` + `dailyPriceCount=1`. |
| Changes | V1-first opener; workflow Production `BEDS24_API_KEY`+`BEDS24_PROP_KEY`; `[open-channel-rates]` live marker; invite wrong-page warning. |
| Tests | `python -m unittest aumara-control-tower/scripts/tests/test_beds24_open_booking_channel_rates.py -v` |
| Stop condition | Live evidence of V1 and/or V2 open, or documented V1 limitation + exact Marketplace invite nav (not API Key 1/2). |
| Recovery point | Branch `cursor/beds24-v1-channel-rates-84a2`. Next: merge; main push/dispatch `[open-channel-rates]`. |
