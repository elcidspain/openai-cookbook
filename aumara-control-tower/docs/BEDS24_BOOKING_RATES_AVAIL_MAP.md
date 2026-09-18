# Beds24 → Booking.com rates/availability MAP (AUMARA)

One-page inventory of how openai-cookbook opens AUMARA (property **324882**, Booking hotel **14953869**) without browser logins. Canonical secret: **`BEDS24_REFRESH_CREDENTIAL`** (repo + Production). COOKBOOK has zero Beds24 secrets — ignore it.

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

Documented V2 invite scopes (only if V1 cannot finish Weekly). Historical invites omitted channels:

| Scope family | Present on current refresh | Required on next invite |
|---|---|---|
| bookings (+ personal/financial) read/write | yes | yes |
| properties read/write | yes | yes |
| inventory read/write | yes | yes |
| **channels** (`read:channels` + `write:channels`) | **NO** | **yes** |

CoS exchanges via `exchange-beds24-invite.yml` only after Marketplace **Generate invite**. Never ask Ilia to paste a password or API key.

## Hotel targeting (14953869 vs 16137893)

| ID | Source | Linked to prop 324882? |
|---|---|---|
| **14953869** | V1 `getPropertyContent` `bookingComPropertyCode`; rooms `1495386901` / `1495386902`; rate `66887702`; first-guest stays | **Yes** — keep targeting this hotel |
| 16137893 | Continuity “working property” label | **Not verified** on 324882. Do not retarget unless live `/properties` or `/channels/settings` shows 16137893 linked and 14953869 absent |

`HOTEL_ACCESS_DENIED` for 14953869 is a historical Booking connectivity error, not proof that 16137893 is the mapped hotel.

## Inventory / prices / channels — what writes what

| Secret | Workflow / script | API calls | Writes | How Booking.com gets it |
|---|---|---|---|---|
| `BEDS24_API_KEY` + `BEDS24_PROP_KEY` (Production) | `beds24-open-booking-channel-rates.yml` → V1 first | `json/getProperty`, `getRates`, `setRates`, `getDailyPriceSetup`, `setDailyPriceSetup`, `setRoomDates`; probe `getV2RefreshToken` (in-memory) | Enable Booking export; open/create Fully flexible + Weekly Beds24 rates; send p1/p2+inventory | Channel manager pushes the mapped rate(s). Distinct Booking Weekly still needs a mapped `bookingcomRateCode` or V2 channels. |
| `BEDS24_REFRESH_CREDENTIAL` | same workflow → V2 second | After exchange: `GET /authentication/details`; `GET/POST /channels/settings` | Opens **Fully flexible** + **Weekly** flags when `read:channels`+`write:channels` exist | Booking extranet rate-plan open flags. Skipped when scopes missing. |
| same | `beds24-open-booking-availability.yml` → `beds24_open_booking_availability.py` | `POST /inventory/rooms/calendar` (`numAvail`, `price1`) in ~365-day chunks | Daily availability + daily price1 through **2028-12-31** | Already SUCCESS on main (run 35380827175). Do **not** duplicate V1 rackRate. |
| (invite one-shot) | `exchange-beds24-invite.yml` | `GET /authentication/setup` | refresh for `BEDS24_REFRESH_CREDENTIAL` | Only if V1 cannot open Weekly. Marketplace invite, never API Key 1/2. |
| UI secrets (`BEDS24_USERNAME`/`PASSWORD`) | photo UI handshake workflows | browser automation | photos only — **out of scope** | N/A |

## Rooms

| Room | Beds24 roomId | target numAvail | price1 (EUR) | Notes |
|---|---|---|---|---|
| CHALET | 674465 | **3** (capped; not 4) | 259 | Room max units = 3 |
| Superior Chalet | 674466 | 2 | 329 | Sparse calendar (~3 days) historically = **missing daily prices**, not missing room linkage |

## Why `/channels/settings` returns 401

Same refresh credential that succeeds on inventory returns:

`GET /channels/settings?propertyId=324882` → **HTTP 401** `{"error":"Token not valid"}`

Root cause: token scopes include inventory/properties/bookings but **not channels**. V1 JSON does not need that scope. V2 channel flags do.

## Preferred open path

1. Inventory/prices (already green): `beds24_open_booking_availability.py` — `[open-availability]`.
2. Rate plans: dispatch `beds24-open-booking-channel-rates` or main push with **`[open-channel-rates]`**. Tries V1 Production keys first; V2 only if channels-scoped.
3. Invite fallback: Marketplace **Generate invite** with channels scopes. Never API Key 1/2.

## Residual blockers

- V1 cannot invent a Booking.com Weekly rate id (no Get Codes). If `getRates` has no Weekly `bookingcomRateCode`, Weekly still needs V2 channels or one Marketplace invite.
- `control3.php?pagetype=apiv2` may show V1 API Key 1/2 on mobile — that is the wrong page.
- After writes, allow Beds24→Booking sync lag. Do not use browser login from agents.
