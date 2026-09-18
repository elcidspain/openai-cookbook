# Beds24 → Booking.com rates/availability MAP (AUMARA)

One-page inventory of how this repository opens AUMARA (property **324882**) without browser logins. Canonical secret: **`BEDS24_REFRESH_CREDENTIAL`** (repo + Production). Do not introduce a second secret name.

## Auth path

1. Read `BEDS24_REFRESH_CREDENTIAL` (refresh token).
2. `GET /authentication/token` with header `refreshToken` → short-lived access token.
3. All API calls use header `token: <access>`.
4. Optional diagnosis: `GET /authentication/details` **after** exchange → scopes (never print token).

Documented **one-invite** scopes (from `aumara-control-tower/systems/beds24-continuity.md`):

| Scope family | Present on current token (run 35380827175) |
|---|---|
| bookings (+ personal/financial) read/write | yes |
| properties read/write | yes |
| inventory read/write | yes |
| **channels** read/write | **NO** |

Exact UI path for the missing channels scope is in continuity.md: **(SETTINGS) MARKETPLACE > API** / https://beds24.com/control3.php?pagetype=apiv2 — one invite with bookings(+personal/financial), properties, inventory, **and channels**, all READ+WRITE.

## Inventory / prices / channels — what writes what

| Secret | Workflow / script | API calls | Writes | How Booking.com gets it |
|---|---|---|---|---|
| `BEDS24_REFRESH_CREDENTIAL` | `beds24-open-booking-availability.yml` → `beds24_open_booking_availability.py` | `POST /inventory/rooms/calendar` (`numAvail`, `price1`) through **2028-12-31**; GET calendar/availability/offers; GET `/properties` (hotel linkage); GET `/inventory/fixedPrices`; GET/POST `/channels/settings` **only when** `read:channels`+`write:channels` exist | Daily availability + daily price1 for 674465/674466. When scoped: enable **Fully flexible** + **Weekly** | Beds24 channel manager pushes Rates & Availability. Rate-plan open/close needs channels scope. |
| same | `beds24-auth-check.yml` → `beds24_auth_check.py` | token exchange + optional inventory open | calendar helper | same |
| (invite one-shot) | `exchange-beds24-invite.yml` | `GET /authentication/setup` | produces refresh token artifact for secret update | bootstrap only |
| UI secrets (`BEDS24_USERNAME`/`PASSWORD`) | photo UI handshake workflows | browser automation | photos only — **out of scope**; do not use for rates | N/A |

## Rooms

| Room | Beds24 roomId | target numAvail | price1 (EUR) | Notes |
|---|---|---|---|---|
| CHALET | 674465 | **3** (capped; not 4) | 259 | Room max units = 3 |
| Superior Chalet | 674466 | 2 | 329 | Live offers probe bookable after price1 write |

## Hotel linkage (16137893 vs 14953869)

- Continuity working hotel: **16137893**
- Continuity legacy/duplicate + V1 `bookingComPropertyCode` (2026-08-25): **14953869**
- Script field `booking_hotel_id` still defaults to 14953869 until live `GET /properties` says otherwise.
- Next open-availability run records `hotel_linkage.classification` without printing secrets.

## Why `/channels/settings` returns 401

Same refresh credential that succeeds on inventory/properties returns:

`GET /channels/settings?propertyId=324882` → **HTTP 401** `{"error":"Token not valid"}`

Root cause: token scopes are the ten booking/property/inventory read+write methods and **not** `read:channels` / `write:channels`. OpenAPI lists `channels` as an invite-code scope. Public `/channels/settings` schema is still Alpha (airbnb/vrbo/iCal); the opener still GET/POSTs `channel=booking` once scoped and records the response.

**Opening Fully flexible / Weekly via the channels API is skipped until the one invite in continuity.md is exchanged into `BEDS24_REFRESH_CREDENTIAL`.** Inventory+price1 writes still run.

## Preferred open path

`beds24_open_booking_availability.py`:

1. Always refresh→token exchange.
2. Write `numAvail` + `price1` for both rooms for `[today .. max(2028-12-31, today+90)]`.
3. Probe `GET /properties?id=324882` for hotel IDs 16137893 vs 14953869.
4. If token has channels scopes: GET then POST `/channels/settings` to enable Fully flexible + Weekly. If 401 / no channels scope: skip write, record `SKIPPED_MISSING_CHANNELS_SCOPE`.
5. Trigger: `workflow_dispatch` **or** push to `main` with **`[open-availability]`**.

## Residual blockers

- **channels scope missing** → cannot API-toggle Booking Fully flexible / Weekly until the one invite is done.
- After price+avail or channel writes, allow Beds24→Booking sync lag. Re-check Booking Calendar / extranet; do not use browser login from agents.
