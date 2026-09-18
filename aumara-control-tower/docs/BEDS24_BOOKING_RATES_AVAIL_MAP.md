# Beds24 → Booking.com rates/availability MAP (AUMARA)

One-page inventory of how openai-cookbook opens AUMARA (property **324882**, Booking hotel **14953869**) without browser logins. Canonical secret: **`BEDS24_REFRESH_CREDENTIAL`** (repo + Production). COOKBOOK has zero Beds24 secrets — ignore it.

## Auth path (do not ask for passwords)

1. Read `BEDS24_REFRESH_CREDENTIAL` (refresh token).
2. `GET /authentication/token` with header `refreshToken` → short-lived access token.
3. All API calls use header `token: <access>`.
4. `GET /authentication/details` **after** exchange → scopes (never print token).

Documented invite scopes (from `aumara-control-tower/systems/beds24-continuity.md`). **Next invite MUST include channels** (historical invites did not):

| Scope family | Present on current token | Required for next invite |
|---|---|---|
| bookings (+ personal/financial) read/write | yes | yes |
| properties read/write | yes | yes |
| inventory read/write | yes | yes |
| **channels** (`read:channels` + `write:channels`) | **NO** | **yes** |

CoS gets the one-time invite code. Exchange via `exchange-beds24-invite.yml`. Store the refresh as `BEDS24_REFRESH_CREDENTIAL`, then dispatch `beds24-open-booking-channel-rates`. Never ask Ilia to paste a password.

## Hotel targeting (14953869 vs 16137893)

| ID | Source | Linked to prop 324882? |
|---|---|---|
| **14953869** | V1 `getPropertyContent` `bookingComPropertyCode`; rooms `1495386901` / `1495386902`; rate `66887702`; first-guest stays | **Yes** — keep targeting this hotel |
| 16137893 | Continuity “working property” label | **Not verified** on 324882. Do not retarget unless live `/properties` or `/channels/settings` shows 16137893 linked and 14953869 absent |

`HOTEL_ACCESS_DENIED` for 14953869 is a historical Booking connectivity error, not proof that 16137893 is the mapped hotel.

## Inventory / prices / channels — what writes what

| Secret | Workflow / script | API calls | Writes | How Booking.com gets it |
|---|---|---|---|---|
| `BEDS24_REFRESH_CREDENTIAL` | `beds24-open-booking-availability.yml` → `beds24_open_booking_availability.py` | `POST /inventory/rooms/calendar` (`numAvail`, `price1`) in ~365-day chunks; GET calendar/availability/offers; GET `/channels/settings` (probe) | Daily availability + daily price1 for rooms 674465/674466 through **2028-12-31** | Beds24 channel manager pushes Rates & Availability when inventory+prices change (hotel 14953869). V2 price1 already SUCCESS on main (run 35380827175); do **not** duplicate V1 rackRate. |
| same | `beds24-open-booking-channel-rates.yml` → `beds24_open_booking_channel_rates.py` | After exchange: `GET /authentication/details` (fail `MISSING_CHANNELS_SCOPE` if no channels); `GET /channels/settings?propertyId=324882`; POST mutated Booking rate plans | Opens **Fully flexible** + **Weekly** (or Beds24 equivalents) for rooms 674465+674466 | Booking extranet rate-plan open flags. Live run is **workflow_dispatch only** after a channels-scoped refresh is stored. |
| same | `beds24-auth-check.yml` → `beds24_auth_check.py` | token exchange + optional inventory open | same calendar pattern (legacy helper) | same |
| same | note/booking/finance/photo workflows | bookings, properties, messages, photos | content/notes/bookings — **not** Booking rate open/close | N/A for rate open |
| (invite one-shot) | `exchange-beds24-invite.yml` | `GET /authentication/setup` | produces refresh token artifact for secret update | bootstrap only; next step is channel-rates dispatch |
| UI secrets (`BEDS24_USERNAME`/`PASSWORD`) | photo UI handshake workflows | browser automation | photos only — **out of scope**; do not use for rates | N/A |

## Rooms

| Room | Beds24 roomId | target numAvail | price1 (EUR) | Notes |
|---|---|---|---|---|
| CHALET | 674465 | **3** (capped; not 4) | 259 | Room max units = 3 |
| Superior Chalet | 674466 | 2 | 329 | Sparse calendar (~3 days) historically = **missing daily prices**, not missing room linkage |

## Why `/channels/settings` returns 401

Same refresh credential that succeeds on inventory returns:

`GET /channels/settings?propertyId=324882` → **HTTP 401** `{"error":"Token not valid"}`

Root cause: token scopes include inventory/properties/bookings but **not channels**. Continuity invite list historically never included channels. Channels scope is required to read/write channel mappings / rate-plan open flags via `/channels/*`.

**Opening Fully flexible / Weekly on Booking via channel settings API is blocked until a new invite includes channels scopes.** Inventory+price1 is already open (run 35380827175). Prepare invite exchange; CoS gets the code; then dispatch `beds24-open-booking-channel-rates`.

## Preferred open path

1. Inventory/prices (current scopes, already green): `beds24_open_booking_availability.py` writes `numAvail` + `price1` for `[today .. max(2028-12-31, today+90)]` in year-sized chunks. Trigger: `workflow_dispatch` **or** push to `main` with **`[open-availability]`**.
2. Channel rates (needs new invite): after `BEDS24_REFRESH_CREDENTIAL` has `read:channels` + `write:channels`, **workflow_dispatch** `beds24-open-booking-channel-rates`. Script fails closed with evidence if scopes are still missing. No browser.

## Residual blockers

- **channels scope missing** on the current refresh → cannot API-toggle Booking rate-plan open/close. Channel-rates workflow is ready-to-dispatch.
- After price+avail write, allow Beds24→Booking sync lag (minutes to hours). Re-check Booking Calendar AI / extranet; do not use browser login from agents.
