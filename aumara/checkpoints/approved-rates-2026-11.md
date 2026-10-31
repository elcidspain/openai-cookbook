# Approved AUMARA rate grid

- Objective: publish the owner-approved monthly and holiday rates for AUMARA from 2026-11-01 through 2027-12-31.
- Status: blocked at live application.
- Scope: property 324882, Chalet 674465 and Superior Chalet 674466; canonical configuration, its rate consumers, Daily Price p1 loading and read-back, existing legacy flat-rate override protection. Existing reservations, inventory, payment settings, access and the EL CID property are outside this task.
- Authorization: the owner approved the final monthly ladder and holiday windows and explicitly instructed publishing the rates on every connected channel in the current conversation.
- Evidence: AGENTS.md, docs/AI_EXECUTION_POLICY.md, docs/CHECKPOINT_PROTOCOL.md, current rate-canonical.json and the existing canonical-loader/guard/repair/shadow workflows. The approved workbook has 426 nights and 12 holiday windows. Current public November 6–8 checkout previously showed EUR372/EUR532. Open PRs contain no recoverable rate-grid work. Targeted code search returned no results for a known filename, so repository tree metadata was used to locate the existing rate consumers without fetching unrelated source content.
- Planned changes: explicit weekday/weekend rates and dated category spreads; shared canonical calculation; update the existing loader and read-only guard, repair and shadow consumers; supersede the old applied revenue overlay; advance the existing authorized apply trigger.
- Tests: compare both room grids against all 852 approved workbook amounts; unit checks for dates, overlaps, whole-euro prices and category spreads; workflow syntax and embedded-Python compilation; full live p1 read-back and public quote comparison after loading.
- Stop condition: the approved live rates are verified, or a specific external authorization/runner/API/channel blocker is recorded. Do not describe a queued run as live pricing.
- Recovery point: clean main 8505268e5db285f96c0748cf421bc507431ac170; branch fix/aumara-approved-rates-2026-11. No other task begins in this execution.

## Local validation

- `python3 -m unittest discover -s aumara/tests -v`: 7 tests passed.
- `python3 validate_rates.py`: all 852 amounts matched the approved workbook. Four YAML workflows and four embedded Python programs parsed. Pull requests cannot execute the live price-writing job.
- Approved grid SHA256: `172572c2244e45c3c0d08cb863255e4aa107907b698ea96d70399fecedb2a51c`.
- The canonical loader uses the established Production API/PROP credential bindings. Credentials remain inside the existing runner environment.
- Live prices and channel delivery have not yet been verified after applying this grid.

## Published implementation and live blocker

- PR202 was merged as c30beeb43de319a1122e1be0b820f0cd448846cf: https://github.com/elcidspain/openai-cookbook/pull/202.
- The new canon, all four consumers, superseded historical overlay and revision5 apply request are on main. Primary Vercel preview passed. Three legacy Vercel project failures match the unchanged base commit.
- No GitHub Actions run was created for the PR or merge. The workflow UI explicitly says workflows on this fork are disabled due to the scale of Actions usage; maintainer re-enablement is required. This is a runner-execution blocker, not evidence of invalid Beds24 credentials.
- Fresh public checkout after the merge still shows EUR372 for Chalet and EUR532 for Superior for 6–8 November. The target is EUR298/EUR358. Live rate application is NOT complete.
- The direct Beds24 control panel is at a signed-out login form with a reCAPTCHA. A secure user authentication handoff is the next step for the direct-control route. No login values were read or stored.
- Recovery: approved grid digest above; main implementation c30beeb43de319a1122e1be0b820f0cd448846cf; existing loader .github/workflows/aumara-rate-canon-once.yml. Resume after authorized authentication or targeted workflow re-enablement and verify every future p1, then public checkout and channel delivery. Existing reservations and inventory remain outside the change.
