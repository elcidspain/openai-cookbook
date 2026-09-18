# Beds24 → Booking.com rates/availability MAP (AUMARA)

One-page inventory of how this repository opens AUMARA (property **324882**) without browser logins. Canonical V2 secret: **`BEDS24_REFRESH_CREDENTIAL`** (repo + Production). Do not introduce a second V2 secret name. Production already has V1 `BEDS24_API_KEY` + `BEDS24_PROP_KEY`.

## Auth path (do not ask for passwords or API keys)

Ilia is often on the **wrong** Beds24 page (V1 **API Key 1/2**). Do **not** paste those keys. Production already has `BEDS24_API_KEY` + `BEDS24_PROP_KEY`.

Preferred live path (this repo):

1. Dispatch `beds24-open-booking-channel-rates` (or push to main with `[open-channel-rates]`).
2. Workflow loads Production `BEDS24_API_KEY` + `BEDS24_PROP_KEY` and tries V1 JSON first (`getProperty`, `getRates`, `setRates`, `setDailyPriceSetup`, `setRoomDates`, probe `getV2RefreshToken`).
3. If a channels-scoped V2 refresh exists (`BEDS24_REFRESH_CREDENTIAL` or an in-memory V1 mint), POST `/channels/settings` to open **Fully flexible** + **Weekly**.
4. Only if V1 cannot map the Booking.com Weekly rate id and V2 still lacks `channels`, send an **invite code** from Marketplace API — never API keys.

### Wrong page vs right page (mobile)

**Wrong (stop):** SETTINGS → ACCOUNT → ACCOUNT ACCESS / API Key 1 / API Key 2 / Prop Key. `https://beds24.com/control3.php?pagetype=apiv2` may land here on mobile. Do not copy or paste anything.

**Right:** SETTINGS → **MARKETPLACE** → **API** → **Generate invite code**. Must see Generate invite, must not see API Key 1/2.

Mobile:

1. Request Desktop site if API Key 1/2 is visible.
2. Menu → SETTINGS → MARKETPLACE (not ACCOUNT ACCESS) → API.
3. Enable READ+WRITE for bookings, bookings-personal, bookings-financial, properties, inventory, **channels**.
4. Generate invite. CoS exchanges it. Never send passwords.

Direct URLs to try: `https://beds24.com/control3.php?pagetype=apiv2` then `https://beds24.com/control2.php?pagetype=apiv2` (old panel). If either shows API Key 1/2, use the Marketplace menu path above.

Documented **one-invite** V2 scopes (from `aumara-control-tower/systems/beds24-continuity.md`). Historical invites omitted channels. Next invite MUST include channels (only if V1 cannot finish Weekly):

| Scope family | Present on current token (run 35380827175) | Required for next invite |
|---|---|---|
| bookings (+ personal/financial) read/write | yes | yes |
| properties read/write | yes | yes |
| inventory read/write | yes | yes |
| **channels** (`read:channels` + `write:channels`) | **NO** | **yes** |

CoS gets the one-time invite code. Exact UI path: **(SETTINGS) MARKETPLACE > API** / https://beds24.com/control3.php?pagetype=apiv2 — one invite with bookings(+personal/financial), properties, inventory, **and channels**, all READ+WRITE. Exchange via `exchange-beds24-invite.yml` only after Marketplace **Generate invite**. Store the refresh as `BEDS24_REFRESH_CREDENTIAL`. Never ask Ilia to paste a password or API key.

## Hotel targeting (14953869 vs 16137893)

| ID | Source | Linked to prop 324882? |
|---|---|---|
| **14953869** | V1 `getPropertyContent` `bookingComPropertyCode`; rooms `1495386901` / `1495386902`; rate `66887702`; first-guest stays | **Yes** — keep targeting this hotel |
| 16137893 | Continuity “working property” label | **Not verified** on 324882. Do not retarget unless live `/properties` or `/channels/settings` shows 16137893 linked and 14953869 absent |

`HOTEL_ACCESS_DENIED` for 14953869 is a historical Booking connectivity error, not proof that 16137893 is the mapped hotel. Live `GET /properties` records `hotel_linkage.classification` without printing secrets.

## Inventory / prices / channels — what writes what

| Secret | Workflow / script | API calls | Writes | How Booking.com gets it |
|---|---|---|---|---|
| `BEDS24_API_KEY` + `BEDS24_PROP_KEY` (Production) | `beds24-open-booking-channel-rates.yml` → V1 first | `json/getProperty`, `getRates`, `setRates`, `getDailyPriceSetup`, `setDailyPriceSetup`, `setRoomDates`; probe `getV2RefreshToken` (in-memory) | Enable Booking export; open/create Fully flexible + Weekly Beds24 rates; send p1/p2+inventory | Channel manager pushes the mapped rate(s). Distinct Booking Weekly still needs a mapped `bookingcomRateCode` or V2 channels. |
| `BEDS24_REFRESH_CREDENTIAL` | same workflow → V2 second | After exchange: `GET /authentication/details` (fail `MISSING_CHANNELS_SCOPE` if no channels); `GET/POST /channels/settings?propertyId=324882` | Canonical fail-closed open of **Fully flexible** + **Weekly** for rooms 674465+674466 when `read:channels`+`write:channels` exist | Booking extranet rate-plan open flags. Skipped when scopes missing. |
| same | `beds24-open-booking-availability.yml` → `beds24_open_booking_availability.py` | `POST /inventory/rooms/calendar` (`numAvail`, `price1`) in ~365-day chunks through **2028-12-31**; GET calendar/availability/offers; GET `/properties` (hotel linkage); GET `/inventory/fixedPrices`; GET `/channels/settings` (probe). Opportunistic POST `/channels/settings` **only when** `read:channels`+`write:channels` exist (skip on 401) | Daily availability + daily price1 for 674465/674466. Do **not** duplicate V1 rackRate. | Beds24 channel manager pushes Rates & Availability (hotel 14953869). V2 price1 already SUCCESS on main (run 35380827175). |
| same | `beds24-auth-check.yml` → `beds24_auth_check.py` | token exchange + optional inventory open | calendar helper | same |
| same | note/booking/finance/photo workflows | bookings, properties, messages, photos | content/notes/bookings — **not** Booking rate open/close | N/A for rate open |
| (invite one-shot) | `exchange-beds24-invite.yml` | `GET /authentication/setup` | produces refresh token artifact for secret update | bootstrap only; next step is channel-rates dispatch. Only if V1 cannot open Weekly. Marketplace invite, never API Key 1/2. |
| UI secrets (`BEDS24_USERNAME`/`PASSWORD`) | photo UI handshake workflows | browser automation | photos only — **out of scope**; do not use for rates | N/A |

## Rooms

| Room | Beds24 roomId | target numAvail | price1 (EUR) | Notes |
|---|---|---|---|---|
| CHALET | 674465 | **3** (capped; not 4) | 259 | Room max units = 3 |
| Superior Chalet | 674466 | 2 | 329 | Live offers probe bookable after price1 write |

## Why `/channels/settings` returns 401

Same refresh credential that succeeds on inventory/properties returns:

`GET /channels/settings?propertyId=324882` → **HTTP 401** `{"error":"Token not valid"}`

Root cause: token scopes are the ten booking/property/inventory read+write methods and **not** `read:channels` / `write:channels`. OpenAPI lists `channels` as an invite-code scope. Public `/channels/settings` schema is still Alpha (airbnb/vrbo/iCal); both V2 openers still GET/POST `channel=booking` once scoped. V1 JSON does not need that scope. V2 channel flags do.

**Opening Fully flexible / Weekly via the V2 channels API waits on the one invite in continuity.md.** Inventory+price1 writes still run. V1 rate-plan open does not wait on that invite.

## Preferred open path

1. Inventory/prices (current scopes, already green): `beds24_open_booking_availability.py` writes `numAvail` + `price1` for `[today .. max(2028-12-31, today+90)]` in year-sized chunks. Trigger: `workflow_dispatch` **or** push to `main` with **`[open-availability]`**. If the token already has channels scopes, this script also opportunistic-opens Fully flexible + Weekly and records `SKIPPED_MISSING_CHANNELS_SCOPE` when it does not.
2. Rate plans: dispatch `beds24-open-booking-channel-rates` or main push with **`[open-channel-rates]`**. Tries V1 Production keys first; V2 `/channels/settings` only if channels-scoped. The dedicated opener fails closed with evidence if V2 scopes are still missing and V1 cannot finish.
3. Invite fallback: Marketplace **Generate invite** with channels scopes. Never API Key 1/2. After `BEDS24_REFRESH_CREDENTIAL` has `read:channels` + `write:channels`, re-dispatch the channel-rates workflow. No browser.

## Residual blockers

- **channels scope missing** on the current refresh → cannot V2-toggle Booking Fully flexible / Weekly until the one invite is done. Channel-rates workflow is ready-to-dispatch and still tries V1 first.
- V1 cannot invent a Booking.com Weekly rate id (no Get Codes). If `getRates` has no Weekly `bookingcomRateCode`, Weekly still needs V2 channels or one Marketplace invite.
- `control3.php?pagetype=apiv2` may show V1 API Key 1/2 on mobile — that is the wrong page.
- After price+avail or channel writes, allow Beds24→Booking sync lag. Re-check Booking Calendar / extranet; do not use browser login from agents.
