# Beds24 continuity record

Last verified: 2026-09-18

## Canonical account map

- Beds24 account: EL CID / AUMARA
- Owner ID: 165022
- AUMARA property ID: 324882
- AUMARA Chalet room ID: 674465
- AUMARA Superior Chalet room ID: 674466
- Booking.com AUMARA working property (continuity label): 16137893
- Booking.com AUMARA linked to Beds24 property 324882 (V1 `bookingComPropertyCode`, rooms 1495386901/1495386902, rate 66887702): **14953869**
- Booking.com AUMARA legacy/duplicate label: 14953869 (this is the hotel currently linked to prop 324882 — do not retarget to 16137893 unless live `/channels/settings` or property payload shows 16137893 linked and 14953869 absent)
- El Cid Country Club Beds24 property: 324903
- Booking.com El Cid hotel ID: 7090541

Hotel-ID note: V1 content audit (2026-08-25) mapped `bookingComPropertyCode=14953869`. Next live run records `GET /properties?id=324882` classification (`working_16137893_only` / `legacy_14953869_only` / `both_present` / `absent_from_v2_properties`). Operational targeting keeps **14953869** unless that live payload shows 16137893 linked and 14953869 absent.

## Authentication architecture

Default AUMARA automation is **API-based**. V1 JSON uses Production `BEDS24_API_KEY` + `BEDS24_PROP_KEY` (never paste keys from the control panel). V2 uses a refresh token from a Marketplace invite.

Canonical V2 secret name (repo + Production): **`BEDS24_REFRESH_CREDENTIAL`**. Never use `BEDS24_PASSWORD` / `BEDS24_USERNAME`. Keep the refresh credential only in this repository's GitHub Actions secrets.

Try V1 first (`beds24-open-booking-channel-rates`). Do not send Ilia to API Key 1/2.

If a V2 invite is still required (Weekly Booking rate id unknown and no channels scope):

1. Open **SETTINGS > MARKETPLACE > API**. Direct URLs: https://beds24.com/control3.php?pagetype=apiv2 then https://beds24.com/control2.php?pagetype=apiv2. If the page shows **API Key 1 / API Key 2**, it is the wrong page — go back, request Desktop site, use MARKETPLACE not ACCOUNT ACCESS.
2. Generate **one** invite code with read+write for every scope listed below (including **channels**). Historical invites omitted channels and cannot open Booking rate plans via V2.
   - bookings
   - bookings-personal
   - bookings-financial
   - properties
   - inventory
   - read:channels
   - write:channels
3. Exchange the invite once with `GET /api/v2/authentication/setup` using header `code` (workflow **Exchange Beds24 invite code**). CoS obtains the one-time code; never ask for a Beds24 password, username, or V1 API key.
4. Store the returned refresh token only as GitHub Actions secret `BEDS24_REFRESH_CREDENTIAL` (replace the existing value; legacy alias `BEDS24_REFRESH_TOKEN`).
5. Never store the invite code, refresh token, or short-lived token in repository files, email, Airtable, or logs.
6. Use the refresh token at least once every 30 days so it remains valid.
7. Dispatch workflow `beds24-open-booking-channel-rates` (marker `[open-channel-rates]`). It tries V1 first and uses V2 `/channels/settings` only when channels-scoped.

### Exact UI path for ONE invite (Ilia / owner)

Do this as a single invite. Scopes cannot be patched onto an existing token.

1. Log in to the Beds24 control panel as the account owner (no password is stored in this repository).
2. Open **(SETTINGS) MARKETPLACE > API**, or go directly to https://beds24.com/control3.php?pagetype=apiv2
3. Click **Generate invite code**.
4. On the scope form, tick **READ and WRITE** for all of the following on this same invite:
   - `bookings`
   - `bookings-personal`
   - `bookings-financial`
   - `properties`
   - `inventory`
   - **`channels`** (this is the missing scope; needed for `GET/POST /channels/settings`; token methods `read:channels` + `write:channels`)
5. Leave IP whitelist empty (GitHub Actions egress IPs change). Do not restrict to a linked-properties-only token unless that is intentional.
6. Click **Generate invite code** to create the code. Copy it (one-time, expires about 24 hours).
7. Run GitHub Action **Exchange Beds24 invite code** with that code. It writes a refresh-token artifact; it does not print the secret in logs.
8. Paste the artifact into repository **and** Production secret `BEDS24_REFRESH_CREDENTIAL` (one line, no quotes). Delete the artifact after copy (public repo).
9. Dispatch **Open AUMARA Booking.com channel rates** (`beds24-open-booking-channel-rates`). Separately, inventory through 2028-12-31 uses **Open AUMARA Booking.com availability** or a `main` push with `[open-availability]`.

Resulting token methods that must appear on `GET /authentication/details` after exchange:

- `read:bookings` `write:bookings`
- `read:bookings-personal` `write:bookings-personal`
- `read:bookings-financial` `write:bookings-financial`
- `read:properties` `write:properties`
- `read:inventory` `write:inventory`
- **`read:channels` `write:channels`**

## Current verified credential state

Live `open-availability` run 35380827175 (2026-09-18) exchanged `BEDS24_REFRESH_CREDENTIAL` successfully. Token scopes:

- present: bookings(+personal/financial), properties, inventory — all read+write
- **missing: channels** → `GET /channels/settings?propertyId=324882` HTTP 401 `Token not valid`

Inventory+price1 for rooms 674465/674466 is green (CHALET numAvail=3 price1=259; Superior numAvail=2 price1=329). Offers bookable. Channel rate-plan open (Fully flexible + Weekly): dispatch `beds24-open-booking-channel-rates` (V1 Production keys first). V2 `/channels/settings` still waits on the one invite above.

## Booking creation control

Direct booking creation uses:

- `GET https://api.beds24.com/v2/authentication/token` with header `refreshToken`
- `POST https://api.beds24.com/v2/bookings` with header `token`

A new reservation must contain at minimum:

- roomId
- status
- arrival
- departure
- firstName
- lastName

For paid bank-transfer reservations add two invoice items:

- charge for the total stay
- payment for the amount received

Always set a unique `apiReference` to prevent accidental duplicate creation and immediately read the created booking back by `apiReference`.

## Maria Elvira booking packet

- Guest: Maria Elvira Medina Arocas
- Property: AUMARA
- Room: Superior Chalet
- Room ID: 674466
- Arrival: 2026-07-18
- Departure: 2026-07-20
- Total: EUR 660
- Paid: EUR 660 by bank transfer
- Status: confirmed
- API reference: AUMARA-MEDINA-20260718-660

Do not execute this packet twice. First search by `apiReference`; create only when no match exists.

## Ownership

- Business owner: Ilya
- System owner: AI Ops
- Credential owner: Ilya / GitHub repository secrets
- Fallback while channels scope is absent: inventory+price1 API writes still run; `beds24-open-booking-channel-rates` tries Production V1 JSON first. Booking Fully flexible / Weekly V2 flags wait on channels scopes.

## Recovery acceptance

The Beds24 API connector is GREEN for inventory/bookings/properties after:

1. secret `BEDS24_REFRESH_CREDENTIAL` exists;
2. token exchange succeeds;
3. property/room read succeeds for property 324882 and rooms 674465/674466;
4. inventory calendar write of `numAvail` + `price1` succeeds through the open window (currently through **2028-12-31**).

The connector is GREEN for Booking **channel rate plans** after inventory GREEN plus either:

5. V1 JSON (`BEDS24_API_KEY` + `BEDS24_PROP_KEY`) opens Fully flexible + Weekly for rooms 674465/674466; or
6. `GET /authentication/details` shows `read:channels` and `write:channels`, `GET /channels/settings?propertyId=324882&channel=booking` returns HTTP 200, and those plans are enabled.

Canonical live path: workflow `beds24-open-booking-channel-rates` (V1 first, then V2 if scoped).
