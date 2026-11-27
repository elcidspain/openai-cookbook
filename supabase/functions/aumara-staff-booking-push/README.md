# AUMARA Staff booking push

Scope: AUMARA property 324882 only, room IDs 674465 and 674466. A new active Beds24 booking since activation is an event, not a payment or full calendar record. No guest names, email, phone, message content or price is stored or included in push. This change never writes bookings or prices in Beds24.

## Release gate

1. Run the PR checks (Node, Deno, PostgreSQL), then apply schema.sql to the existing Supabase project. All tables and RPCs are service-role-only. Deploy the independent aumara-staff-booking-push Edge Function with index.ts and booking.ts and verify_jwt=false; staff operations perform the existing listMyDevices authentication, webhook uses its own secret. Leave existing aumara-staff-api intact.
2. Open Staff as an authenticated staff member. A first successful status request creates the VAPID keypair and the webhook secret server-side, with a creation-time baseline. Confirm the configuration exists without printing keys.
3. In Beds24 > Settings > Properties > Access > Booking webhook, select AUMARA property 324882. Preserve any pre-existing integrations. Configure V2 without personal data, endpoint https://cguutkghsnhmwzghkmnc.supabase.co/functions/v1/aumara-staff-booking-push/webhook and custom header X-AUMARA-Webhook with the secret from the protected aumara_staff_push_config row. Enter the secret directly through an authorized admin UI; never paste into chat, repo, URL, logs, or a guest message. If existing webhook configuration cannot coexist, stop rather than replace it.
4. Merge the reviewed frontend through the existing Nominalia Staff deployment. Open installed Staff (iOS requires Add to Home Screen), authenticate, tap Enable push and accept OS permission. Send the explicitly labeled test and confirm it actually appears while the app is closed. Provider acceptance alone is not device receipt.
5. Verify the next genuine Beds24 booking appears once in the feed and once on an opted-in device. Check event and outbox evidence by booking ID; do not create a fake guest booking. Repeat event delivery must not create another event or delivery. Record the deployment SHA, webhook settings verification, and device receipt.

## Delivery model

The webhook accepts only new/confirmed AUMARA events booked after the server baseline. Transactional insert uses the booking ID as dedupe key; each currently authorized subscription has its own outbox record. Transient failures return HTTP 503 to request Beds24 retry; expired push endpoints are removed. A provider acceptance is tracked as sent, not as proof the phone displayed the notification. A stable notification tag collapses ambiguous retries. The device lease is at most seven days and no longer than the existing staff device session; reopen Staff to renew. Logout attempts server removal and browser unsubscribe. Notifications do not replace the Beds24 reservation calendar or the operational handover.

Rollback: disable only this Beds24 webhook URL/header, remove push controls via normal Staff rollback, and leave the additive database tables for audit. No existing booking, rate, staff-auth backend or staff data is mutated. Never rotate existing credentials as part of this feature.
