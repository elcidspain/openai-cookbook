# Checkpoint: merge with sibling executions

Status: complete

## Objective

Union this execution with the other Beds24 sand executions on `elcidspain/openai-cookbook`.

## Merged executions (all ancestors of this branch)

| Execution | Branch | PR | Main SHA |
| --- | --- | --- | --- |
| Beds24 open Booking avail workflow | `cursor/beds24-open-booking-availability-c999` | #159 | `48a6850a` |
| fix Beds24 open-avail token exchange | `cursor/beds24-always-exchange-token-9d9b` | #160 | `03b5967c` |
| Open AUMARA Booking rates via Beds24 API | `cursor/beds24-channel-rates-2028-8cf4` | #163 | `77ca3343` |
| Open Booking rates via V1 keys if possible | `cursor/beds24-v1-channel-rates-84a2` | #165 | `771080b4` |
| This run: channels rates + 2028 + invite docs | `cursor/beds24-booking-channel-rates-d78b` | #166 | this branch |

`origin/main` (`771080b4`) is an ancestor of `HEAD`. No further main commits to merge.

## Unique on this branch vs main

- `beds24_open_booking_availability.py` opportunistic V2 channel open + 2028 window
- availability tests for that path
- continuity + MAP unions (V1-first live path kept; one-invite UI and live-run evidence kept)

## Exclusions

- No live Beds24 writes
- Closed PR #164 not reopened
- AUMARA Radar OAuth/ACP fix stays in `elcidspain/aumara` (no write access from this agent)

## Recovery point

Branch `cursor/beds24-booking-channel-rates-d78b`. Next safe action: review PR #166; do not collapse the three rate-open implementations.
