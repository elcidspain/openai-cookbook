# Beds24 → Booking.com rates/availability MAP (AUMARA)

One-page inventory of how openai-cookbook opens AUMARA (property **324882**, Booking hotel **14953869**) without browser logins. Canonical secret: **`BEDS24_REFRESH_CREDENTIAL`** (repo + Production). COOKBOOK has zero Beds24 secrets — ignore it.

## Auth path (do not ask for a new invite unless scopes proven missing)

1. Read `BEDS24_REFRESH_CREDENTIAL` (refresh token).
2. `GET /authentication/token` with header `refreshToken` → short-lived access token.
3. All API calls use header `token: <access>`.
4. Optional diagnosis: `GET /authentication/details` **after** exchange → scopes (never print token).

Documented invite scopes (from `aumara-control-tower/systems/beds24-continuity.md` + live Airbnb photo evidence):

| Scope family | Present on current token |
|---|---|
| bookings (+ personal/financial) read/write | yes |
| properties read/write | yes |
| inventory read/write | yes |
| **channels** read/write | **NO** |

## Inventory / prices / channels — what writes what

| Secret | Workflow / script | API calls | Writes | How Booking.com gets it |
|---|---|---|---|---|
| `BEDS24_REFRESH_CREDENTIAL` | `beds24-open-booking-availability.yml` → `beds24_open_booking_availability.py` | `POST /inventory/rooms/calendar` (`numAvail`, `price1`); GET calendar/availability/offers; GET `/channels/settings` (probe) | Daily availability + daily price1 for rooms 674465/674466 through **2028-12-31** | Beds24 channel manager pushes Rates & Availability to Booking when inventory+prices change. No browser. |
| `BEDS24_API_KEY` + `BEDS24_PROP_KEY` (Production) | same workflow job `rack-rates` | V1 `json/setPropertyContent` + `getPropertyContent` with body `{apiKey, propKey}` | Room `rackRate` 674465=259.00, 674466=329.00 | Historical Booking price path. See `BEDS24_BOOKING_MAP.md`. |
| same V2 secret | `beds24-auth-check.yml` → `beds24_auth_check.py` | token exchange + optional inventory open | same calendar pattern (legacy helper) | same |
| same | note/booking/finance/photo workflows | bookings, properties, messages, photos | content/notes/bookings — **not** Booking rate open/close | N/A for rate open |
| (invite one-shot) | `exchange-beds24-invite.yml` | `GET /authentication/setup` | produces refresh token artifact for secret update | bootstrap only |
| UI secrets (username/password) | photo UI handshake workflows | browser automation | photos only — **out of scope**; do not use for rates | N/A |

## Rooms

| Room | Beds24 roomId | target numAvail | price1 (EUR) | Notes |
|---|---|---|---|---|
| CHALET | 674465 | **3** (capped; not 4) | 259 | Room max units = 3 |
| Superior Chalet | 674466 | 2 | 329 | Sparse calendar (~3 days) historically = **missing daily prices**, not missing room linkage |

## Why `/channels/settings` returns 401

Same refresh credential that succeeds on inventory returns:

`GET /channels/settings?propertyId=324882` → **HTTP 401** `{"error":"Token not valid"}`

Root cause: token scopes include inventory/properties/bookings but **not channels**. Continuity invite list never included channels. Channels scope is required to read/write channel mappings / rate-plan open flags via `/channels/*`.

**Opening Fully flexible / Weekly via `/channels/settings` is blocked without channels scope.** Do not request a new invite. Prefer V2 `price1` + V1 `rackRate` (`BEDS24_BOOKING_MAP.md`). If V1 returns `HOTEL_ACCESS_DENIED` for hotel 14953869, record it and stop.

## Preferred open path (current scopes)

Extend `beds24_open_booking_availability.py` (this repo):

1. Always refresh→token exchange.
2. Write V1 `rackRate` first (primary Booking prices), then `numAvail` + `price1` for both rooms for `[today .. max(2028-12-31, today+90)]` in ~365-day chunks.
3. Record sanitized scopes + channels 401 diagnosis in evidence artifact.
4. Trigger: `workflow_dispatch` **or** push to `main` with commit marker **`[open-availability]`**.

Booking “Fully flexible” / “Weekly” closed in Calendar AI while matrix looked open is explained by: inventory open without daily prices (Superior sparse days) and/or channel rate flags not toggleable without channels scope.

## Residual blockers

- **channels scope missing** → cannot API-toggle Booking rate-plan open/close or read channel mappings.
- After price+avail write, allow Beds24→Booking sync lag (minutes to hours). Re-check Booking Calendar AI / extranet; do not use browser login from agents.
