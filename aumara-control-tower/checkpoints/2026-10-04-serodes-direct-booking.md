# Checkpoint — Serodes direct booking

| Field | Content |
| --- | --- |
| Objective | Enter direct booking Serodes on a free Superior unit at Beds24 property 324882 for 2026-10-10 to 2026-10-11, without guest messages, then remove it from `bookings/manual.json` only after a booking id is confirmed. |
| Status | in progress — main run 37227081240 authenticated and read properties, then stopped before any POST. `GET /inventory/rooms/unitBookings` HTTP 400 because `endDate` equalled `startDate`. No booking id. `bookings/manual.json` unchanged. |
| Scope | Allowed: `aumara-control-tower/scripts/beds24_serodes_direct_booking.py`, its unit test, `.github/workflows/aumara-serodes-direct-booking.yml`, `.github/aumara-serodes-direct-booking.trigger`, this checkpoint. One POST `/bookings` only when at least two Superior units are configured and one is free on 2026-10-10. Preferred unit is the second. `notifyGuest` false, `notifyHost` false, `allowAutoAction` disable, no guest-message API. Excluded: Gmail, guest messages, credential changes, price changes, cancelling other bookings, removing `bookings/manual.json` before a booking id. |
| Evidence | Reused `origin/main` bookings snapshot (`beds24_bookings_snapshot.py`, workflow cron `7 6 * * *`, secret `BEDS24_REFRESH_CREDENTIAL`) and checkpoint `aumara-control-tower/checkpoints/2026-10-04-bookings-snapshot.md`. `bookings/manual.json` still contains Serodes. Superior room id 674466, qty 2, comes from `aumara/evidence/execution-checkpoint.json` and must be confirmed live before the write. Beds24 OpenAPI `apiV2.yaml` fields used: `unitId`, `price`, `deposit`, `notes`, `allowAutoAction=disable`, `actions.notifyGuest=false`, `actions.notifyHost=false`, `actions.checkAvailability=true`. |
| Tests | `python3 -m unittest aumara-control-tower/scripts/tests/test_beds24_serodes_direct_booking.py -v` — 12 passed locally. Live result is the Actions artifact `serodes-direct-booking-result` after the main push. |
| Stop condition | Not met. Stop when the main-push job reports a booking id and unit, or the exact not-created reason and the unit list. Then a follow-up commit deletes this workflow and, only if a booking id was confirmed, removes Serodes from `bookings/manual.json`. |
| Recovery point | Branch `cursor/serodes-direct-booking-4186`. Do not create the booking from a laptop. Do not dispatch `workflow_dispatch`. |

No secrets in this file.
