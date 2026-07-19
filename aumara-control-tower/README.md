# AUMARA Control Tower

Working transactional email/webhook service for AUMARA El Cid.

## Run locally

```bash
cd aumara-control-tower
cp .env.example .env
npm install
npm run health
npm run test:email
npm start
```

## Endpoints

### GET /health

Returns service status.

### POST /send

Generic send endpoint. Auth: `Authorization: Bearer $AUMARA_WEBHOOK_TOKEN`.

```bash
curl -X POST http://localhost:8787/send \
  -H "content-type: application/json" \
  -H "authorization: Bearer change-this-token" \
  -d '{
    "to":"elcidspain@gmail.com",
    "guestName":"Test Guest",
    "property":"AUMARA El Cid",
    "checkIn":"2026-07-10",
    "checkOut":"2026-07-12",
    "accessCode":"123456",
    "bookingRef":"TEST-001"
  }'
```

### POST /webhooks/beds24

Beds24-style webhook receiver. It accepts flexible fields: `email`, `guestEmail`, `guest_email`, `mail`, `guestName`, `property`, `checkIn`, `checkOut`, `accessCode`, `pin`, `code`, `bookingRef`.

### GET /beds24/bookings

Reads bookings from Beds24 API V2 (`https://api.beds24.com/v2`) with `BEDS24_TOKEN_CREDENTIAL` only.
Auth required: `Authorization: ******`.

### GET /beds24/messages?bookingId=123456

Reads message history for one booking using `BEDS24_TOKEN_CREDENTIAL`.
Auth required: `Authorization: ******`.

### POST /beds24/messages

Safely sends a host message with write access:
- checks duplicates first through read token;
- exchanges `BEDS24_REFRESH_TOKEN` via `GET /authentication/token`;
- sends message through `POST /bookings/messages` using short-lived access token.
Auth required: `Authorization: ******`.

Request body:

```json
{
  "bookingId": 123456,
  "message": "Hello from AUMARA",
  "dedupe": true
}
```

## Current mail routing

- Provider: Resend
- Reply-to: `elcidspain@gmail.com`
- Test recipient: `elcidspain@gmail.com`
- Temporary sender: `AUMARA El Cid <onboarding@resend.dev>` until the domain sender is verified.

## Production next step

Deploy this folder as a Node service, set environment variables, then connect Beds24 action/webhook to:

```text
POST https://YOUR-SERVICE/webhooks/beds24
Authorization: Bearer AUMARA_WEBHOOK_TOKEN
```
