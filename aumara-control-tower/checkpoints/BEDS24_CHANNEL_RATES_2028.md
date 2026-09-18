# Checkpoint — Beds24 channel rates + 2028 window

| Field | Content |
| --- | --- |
| Objective | Agent-ready Booking Fully flexible + Weekly path: channels-scoped script/workflow, invite scope docs, inventory window through 2028-12-31. No passwords. Live channel open only if scopes present. |
| Status | complete — branch `cursor/beds24-channel-rates-2028-8cf4`; channel-rates ready-to-dispatch; live channel POST skipped (current token still missing channels scopes; no local refresh in this environment) |
| Scope | `beds24_open_booking_channel_rates.py` + workflow (dispatch-only live); continuity + invite help include `read:channels`/`write:channels`; open-availability `FIXED_END=2028-12-31` with year chunks; MAP targeting 14953869 vs 16137893. No V1 rackRate duplicate. No browser. No COOKBOOK. Do not live-run channel POST without channels scopes. |
| Evidence | V2 inventory+price1 SUCCESS run 35380827175. `/channels/settings` 401 without channels. V1 content audit `bookingComPropertyCode=14953869` for prop 324882 (rooms 1495386901/02, rate 66887702). Continuity “working” hotel 16137893 not verified as linked. PR #162 closed (V1 duplicate). |
| Changes | See this branch vs `origin/main`. |
| Tests | `python -m unittest aumara-control-tower/scripts/tests/test_beds24_open_booking_channel_rates.py aumara-control-tower/scripts/tests/test_beds24_open_booking_availability.py -v` |
| Stop condition | Channel-rates workflow ready-to-dispatch; invite checklist updated; 2028 window in availability script; PR opened. Live channel open skipped until scopes exist. |
| Recovery point | Branch `cursor/beds24-channel-rates-2028-8cf4`. Next: CoS invite with channels scopes → store `BEDS24_REFRESH_CREDENTIAL` → dispatch `beds24-open-booking-channel-rates`. Inventory 2028 live via `[open-availability]` after merge. |
