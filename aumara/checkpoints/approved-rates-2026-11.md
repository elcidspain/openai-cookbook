# Approved AUMARA rate grid — live application verified

- Objective: publish the owner-approved monthly and holiday rates for AUMARA from 2026-11-01 through 2027-12-31.
- Status: all 852 Daily Price 1 amounts saved in Beds24 and verified against the approved workbook; public website and checkout checks passed.
- Authorization: the owner approved the monthly ladder and holiday windows and explicitly instructed publishing the rates on every connected channel, using the existing signed-in browser through Remote Desktop Commander.
- Scope: property 324882, Chalet 674465 and Superior Chalet 674466; 426 nights per category, 12 holiday windows. Prices are EUR per whole house per night. Friday and Saturday use weekend prices.
- Existing reservations, inventory, payments, security settings and EL CID property 324903 were not changed.

## Published implementation

- PR202: https://github.com/elcidspain/openai-cookbook/pull/202, merged as c30beeb43de319a1122e1be0b820f0cd448846cf.
- The canonical configuration, shared calculator, loader, drift guard, repair and revenue shadow consumers use the approved explicit monthly and holiday grid. The historical revenue overlay is superseded.
- Local validation: 7 unit tests passed, all 852 calculated amounts matched the approved workbook, four workflow YAML files and four embedded Python programs parsed.
- GitHub Actions remains disabled on this fork due to the scale of Actions usage. No workflow run or API-based application is claimed. Live publication was completed through the existing authenticated Beds24 browser UI.

## Live application and independent read-back

- Completed 68 scoped UI updates to Daily Price 1. The original 852 prices were exported before changes and retained privately for recovery.
- All 852 live amounts matched the approved matrix: zero mismatches, verified 2026-11-01T01:20:23Z.
- Approved and live grid SHA256: `172572c2244e45c3c0d08cb863255e4aa107907b698ea96d70399fecedb2a51c`.
- Read-back sources: fresh server-loaded Beds24 calendar UI, 2026-11-01–2027-10-31 (730 room-night amounts), and fresh Beds24 Excel export, 2027-11-01–2027-12-31 (122 amounts).
- The 29 October–1 November 2027 holiday window and the last nights of December 2027 were verified across calendar-view boundaries. No 2028 nightly price was changed.
- The final published workbook includes monthly rates, the complete 426-night calendar and all 12 approved holiday windows. Editing that workbook does not itself publish prices.

## Root cause corrected

Superior Chalet had a room-level Minimum Price of EUR225/night. That floor overrode correctly lowered daily prices and produced a EUR450 two-night checkout instead of EUR358. Changed only that room's Minimum Price to EUR169 and verified the saved value and public result. Future rate checks must compare room-level floors and the effective checkout total, in addition to Daily Price 1.

## Public verification

Twelve room quotes matched the approved grid. Dates below are check-in/check-out; totals are per stay.

| Stay | Nights | Chalet | Superior | Evidence |
| --- | ---: | ---: | ---: | --- |
| 4–5 November 2026 | 1 | EUR139 | EUR169 | Public checkout |
| 6–8 November 2026 | 2 | EUR298 | EUR358 | Public checkout; Superior also confirmed through the live website |
| 31 December 2026–2 January 2027 | 2 | EUR338 | EUR398 | Website live availability |
| 2–4 July 2027 | 2 | EUR398 | EUR498 | Public checkout |
| 1–2 November 2027 | 1 | EUR189 | EUR239 | Website live availability |
| 30 December 2027–1 January 2028 | 2 | EUR378 | EUR478 | Website live availability; only 2027 nights |

The previous 6–8 November public totals were EUR372/EUR532. Verified new totals are EUR298/EUR358. No booking or payment was submitted during verification.

## Channel checks and remaining external availability blocker

- The existing channel-manager export horizon is two years.
- Airbnb: both AUMARA room mappings use Per Day Pricing, Sync Type Everything; each returned Connected when checked. The Chalet outbound Price Data view has multiplier 1 and EUR139 weekdays / EUR149 Friday–Saturday for the checked available November dates.
- Booking.com: both AUMARA room mappings are Enabled, rate plan 66887702; XML connection is Active. The Superior outbound Price Data view has multiplier 1 and EUR169 weekdays / EUR179 Friday–Saturday for all checked occupancies on available November dates.
- Booking.com still reports the property itself as Closed after an explicit status refresh. Rate loading cannot reopen an externally closed property. Owner action in the Booking.com Extranet is needed before new reservations can resume there. Supporting account correspondence was reviewed privately.
- These checks establish enabled mappings and outgoing price data; they are not an independent OTA acknowledgement of every room-night amount. No claim is made that Booking.com is accepting reservations, or that all other linked channels were independently verified.

## Recovery and next operator action

- Preserve the approved grid hash and private before-change exports; restore only the two authorized rooms and date range if needed.
- Before any future tariff loader runs, verify the room-level minimum price and effective public checkout total as well as p1. Keep the protected legacy flat-rate override checks.
- Do not reapply this grid merely because old notes say live application was blocked; the complete 852-price read-back already passed.
- Next unresolved action: restore external Booking.com property availability through the existing Extranet account, then refresh status and verify a public bookable quote. Payment and any new financial commitment were not performed.
