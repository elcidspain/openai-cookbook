# Beds24 → Booking.com rates/availability MAP (AUMARA)

One-page inventory of how this repository opens AUMARA (property **324882**) without browser logins. Canonical secret: **`BEDS24_REFRESH_CREDENTIAL`** (repo + Production). Do not introduce a second secret name.

## Auth path (do not ask for passwords)

1. Read `BEDS24_REFRESH_CREDENTIAL` (refresh token).
2. `GET /authentication/token` with header `refreshToken` → short-lived access token.
3. All API calls use header `token: <access>`.
4. `GET /authentication/details` **after** exchange → scopes (never print token).

Documented **one-invite** scopes (from `aumara-control-tower/systems/beds24-continuity.md`). **Next invite MUST include channels** (historical invites did not):

| Scope family | Present on current token (run 35380827175) | Required for next invite |
|---|---|---|
| bookings (+ personal/financial) read/write | yes | yes |
| properties read/write | yes | yes |
| inventory read/write | yes | yes |
| **channels** (`read:channels` + `write:channels`) | **NO** | **yes** |

CoS gets the one-time invite code. Exact UI path: **(SETTINGS) MARKETPLACE > API** / https://beds24.com/control3.php?pagetype=apiv2 — one invite with bookings(+personal/financial), properties, inventory, **and channels**, all READ+WRITE. Exchange via `exchange-beds24-invite.yml`. Store the refresh as `BEDS24_REFRESH_CREDENTIAL`. Never ask Ilia to paste a password.

## Hotel targeting (14953869 vs 16137893)

| ID | Source | Linked to prop 324882? |
|---|---|---|
| **14953869** | V1 `getPropertyContent` `bookingComPropertyCode`; rooms `1495386901` / `1495386902`; rate `66887702`; first-guest stays | **Yes** — keep targeting this hotel |
| 16137893 | Continuity “working property” label | **Not verified** on 324882. Do not retarget unless live `/properties` or `/channels/settings` shows 16137893 linked and 14953869 absent |

`HOTEL_ACCESS_DENIED` for 14953869 is a historical Booking connectivity error, not proof that 16137893 is the mapped hotel. Live `GET /properties` records `hotel_linkage.classification` without printing secrets.

## Inventory / prices / channels — what writes what

| Secret | Workflow / script | API calls | Writes | How Booking.com gets it |
|---|---|---|---|---|
| `BEDS24_REFRESH_CREDENTIAL` | `beds24-open-booking-availability.yml` → `beds24_open_booking_availability.py` | `POST /inventory/rooms/calendar` (`numAvail`, `price1`) in ~365-day chunks through **2028-12-31**; GET calendar/availability/offers; GET `/properties` (hotel linkage); GET `/inventory/fixedPrices`; GET `/channels/settings` (probe). Opportunistic POST `/channels/settings` **only when** `read:channels`+`write:channels` exist (skip on 401) | Daily availability + daily price1 for 674465/674466. Do **not** duplicate V1 rackRate. | Beds24 channel manager pushes Rates & Availability (hotel 14953869). V2 price1 already SUCCESS on main (run 35380827175). |
| same | `beds24-open-booking-channel-rates.yml` → `beds24_open_booking_channel_rates.py` | After exchange: `GET /authentication/details` (fail `MISSING_CHANNELS_SCOPE` if no channels); `GET /channels/settings?propertyId=324882`; POST mutated Booking rate plans | Canonical fail-closed open of **Fully flexible** + **Weekly** for rooms 674465+674466 | Booking extranet rate-plan open flags. Live run is **workflow_dispatch only** after a channels-scoped refresh is stored. |
| same | `beds24-auth-check.yml` → `beds24_auth_check.py` | token exchange + optional inventory open | calendar helper | same |
| same | note/booking/finance/photo workflows | bookings, properties, messages, photos | content/notes/bookings — **not** Booking rate open/close | N/A for rate open |
| (invite one-shot) | `exchange-beds24-invite.yml` | `GET /authentication/setup` | produces refresh token artifact for secret update | bootstrap only; next step is channel-rates dispatch |
| UI secrets (`BEDS24_USERNAME`/`PASSWORD`) | photo UI handshake workflows | browser automation | photos only — **out of scope**; do not use for rates | N/A |

## Rooms

| Room | Beds24 roomId | target numAvail | price1 (EUR) | Notes |
|---|---|---|---|---|
| CHALET | 674465 | **3** (capped; not 4) | 259 | Room max units = 3 |
| Superior Chalet | 674466 | 2 | 329 | Live offers probe bookable after price1 write |

## Why `/channels/settings` returns 401

Same refresh credential that succeeds on inventory/properties returns:

`GET /channels/settings?propertyId=324882` → **HTTP 401** `{"error":"Token not valid"}`

Root cause: token scopes are the ten booking/property/inventory read+write methods and **not** `read:channels` / `write:channels`. OpenAPI lists `channels` as an invite-code scope. Public `/channels/settings` schema is still Alpha (airbnb/vrbo/iCal); both openers still GET/POST `channel=booking` once scoped.

**Opening Fully flexible / Weekly via the channels API waits on the one invite in continuity.md.** Inventory+price1 writes still run.

## Preferred open path

1. Inventory/prices (current scopes, already green): `beds24_open_booking_availability.py` writes `numAvail` + `price1` for `[today .. max(2028-12-31, today+90)]` in year-sized chunks. Trigger: `workflow_dispatch` **or** push to `main` with **`[open-availability]`**. If the token already has channels scopes, this script also opportunistic-opens Fully flexible + Weekly and records `SKIPPED_MISSING_CHANNELS_SCOPE` when it does not.
2. Channel rates (needs new invite): after `BEDS24_REFRESH_CREDENTIAL` has `read:channels` + `write:channels`, **workflow_dispatch** `beds24-open-booking-channel-rates`. That script fails closed with evidence if scopes are still missing. No browser.

## Residual blockers

- **channels scope missing** on the current refresh → cannot API-toggle Booking Fully flexible / Weekly until the one invite is done. Channel-rates workflow is ready-to-dispatch.
- After price+avail or channel writes, allow Beds24→Booking sync lag. Re-check Booking Calendar / extranet; do not use browser login from agents.
