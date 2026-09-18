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

## Authentication architecture

Default AUMARA automation is **API-based**. V1 JSON uses Production `BEDS24_API_KEY` + `BEDS24_PROP_KEY` (never paste keys from the control panel). V2 uses a refresh token from a Marketplace invite.

Try V1 first (`beds24-open-booking-channel-rates`). Do not send Ilia to API Key 1/2.

If a V2 invite is still required (Weekly Booking rate id unknown and no channels scope):

1. Open **SETTINGS > MARKETPLACE > API**. Direct URLs: https://beds24.com/control3.php?pagetype=apiv2 then https://beds24.com/control2.php?pagetype=apiv2. If the page shows **API Key 1 / API Key 2**, it is the wrong page — go back, request Desktop site, use MARKETPLACE not ACCOUNT ACCESS.
2. Tap **Generate invite code** with scopes:
   - bookings
   - bookings-personal
   - bookings-financial
   - properties
   - inventory
   - read:channels
   - write:channels
3. Exchange the invite code once through GET /api/v2/authentication/setup using header `code`. CoS obtains the one-time code; never ask for a Beds24 password, username, or V1 API key.
4. Store the returned refresh token only as GitHub Actions secret `BEDS24_REFRESH_CREDENTIAL` (legacy alias: `BEDS24_REFRESH_TOKEN`).
5. Never store the invite code, refresh token or short-lived token in repository files, email, Airtable or logs.
6. Use the refresh token at least once every 30 days so it remains valid.
7. Dispatch workflow `beds24-open-booking-channel-rates` (marker `[open-channel-rates]`). It tries V1 first and uses V2 `/channels/settings` only when channels-scoped.

## Current verified credential state

A sanitized GitHub Actions probe on 2026-07-14 found no Beds24 credential secret under historical candidate names (including `BEDS24_REFRESH_TOKEN`). The live connector now uses repository secret `BEDS24_REFRESH_CREDENTIAL`. Token scopes still omit `read:channels` / `write:channels` until a new invite with the checklist above is exchanged.

## Booking creation control

Direct booking creation uses:

- `GET https://beds24.com/api/v2/authentication/token` with header `refreshToken`
- `POST https://beds24.com/api/v2/bookings` with header `token`

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
- Fallback while API credential is absent: manual reservation in Beds24 calendar and immediate calendar reconciliation

## Recovery acceptance

The Beds24 API connector is GREEN only after all of the following pass:

1. secret `BEDS24_REFRESH_CREDENTIAL` exists;
2. token exchange succeeds;
3. `GET /authentication/details` after exchange includes inventory, properties, bookings, **and** read:channels + write:channels;
4. property/room read succeeds for property 324882 and room 674466;
5. idempotency search by apiReference succeeds;
6. controlled booking creation succeeds;
7. created booking reads back with dates, guest, room, charge and payment;
8. corresponding inventory is blocked;
9. Booking Fully flexible + Weekly rate plans for rooms 674465/674466 are open (workflow `beds24-open-booking-channel-rates`).
