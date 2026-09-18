# Beds24 → Booking.com sync map (AUMARA 324882)

Short path from secrets to Booking-visible availability and rates. No browser login. No new invite.

Companion V2-only note: `aumara-control-tower/docs/BEDS24_BOOKING_RATES_AVAIL_MAP.md`.

## Secrets (elcidspain/openai-cookbook only)

| Secret | Where | Used for |
| --- | --- | --- |
| `BEDS24_REFRESH_CREDENTIAL` | repo Actions + Production | V2 `refreshToken` → short-lived `token` |
| `BEDS24_API_KEY` + `BEDS24_PROP_KEY` | Production environment | V1 JSON body `{apiKey, propKey}` |
| password / username secrets | present historically | **Do not use.** Not a fallback. |

Never print or commit values. Do not treat the refresh credential as a KEK, vault key, or control-panel password.

## Scripts and live jobs

1. `.github/workflows/beds24-open-booking-availability.yml`
   - `open-availability`: V2 inventory + `price1` (repo secret). Trigger: `workflow_dispatch` or main push with `[open-availability]`.
   - `rack-rates`: same script after inventory, `environment: Production`, `BEDS24_REQUIRE_RACK_RATES=1`.
2. `aumara-control-tower/scripts/beds24_open_booking_availability.py`
   - Always `GET /authentication/token` then `GET /authentication/details` (scopes only).
   - `POST /inventory/rooms/calendar` for rooms `674465` (CHALET, 3 units / €259) and `674466` (Superior, 2 / €329) from today through **`2028-12-31`** (year-sized chunks).
   - **Primary Booking prices:** `POST https://api.beds24.com/json/setPropertyContent` rackRate readback via `getPropertyContent`.
3. Archived V1 source: `ops/archive/github-actions/2026-08/beds24-rack-rate-fix-20260825.yml`.

## V2 inventory vs V1 rack vs channels

| Layer | Endpoint | What Booking needs | Status |
| --- | --- | --- | --- |
| V2 inventory | `/inventory/rooms/calendar` | `numAvail` open + daily `price1` through **2028-12-31** | Supporting. Year-chunked writes. |
| V1 rackRate | `/json/setPropertyContent` | **Primary** Booking nightly price | Historical SUCCESS 2026-08-25 (259.00 / 329.00). Not `/channels/settings`. |
| V2 channels | `/channels/settings` | Channel-specific rate open/close | 401 with the same V2 token. Missing scope is **`channels`** (`read:channels` / `write:channels`). |

Canonical invite scopes in `aumara-control-tower/systems/beds24-continuity.md`: `bookings`, `bookings-personal`, `bookings-financial`, `properties`, `inventory`. That list omits `channels`. Do not request a new invite; V1 rackRate does not need channels scope.

## Booking.com hotel IDs

- Working property in continuity: `16137893`.
- Legacy/duplicate from Rates pack: `14953869` — historical `HOTEL_ACCESS_DENIED` / forbidden hotel id. If V1 write returns that string, record it and stop; do not browser-login to clear it.

## Evidence

- V2: `aumara-control-tower/evidence/beds24-open-booking-availability-*.json`
- V1: `aumara-control-tower/evidence/beds24-rack-rate-live.json` (plus archived `beds24-rack-rate-fix-20260825.json`)
- Binding names only: `aumara-control-tower/checkpoints/BEDS24_BINDING_INVENTORY.json`

## Checkpoint

| Field | Content |
| --- | --- |
| Objective | Open Booking-visible AUMARA rates/prices via V1 rackRate (primary) and V2 inventory through 2028-12-31 |
| Status | in progress until live V1 readback SUCCESS (or documented HOTEL_ACCESS_DENIED) |
| Recovery point | `cursor/beds24-v1-rack-rates-8cf4` (#162); rerun with `[open-availability]` |
| Next safe action | If Production job waits, approve environment; if V1 HOTEL_ACCESS_DENIED, stop and keep evidence |
