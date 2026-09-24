# Ilia — shower recap (2026-09-24 ~07:12 CEST)

1. **bc-6d87f01c** (+ связанные **bc-c628c78d**, **bc-1ebcfb3c**): permanently deleted. Workflows `Open AUMARA Booking.com channel rates`, `…availability`, `Exchange Beds24 invite` — **disabled**. BEDS24 secrets left in repo for human-only. Cursor GitHub App still needs Ilia revoke in GitHub UI for hard no-new-agent push.
2. **Min nights сейчас ≠ 1.** Guest still hits Weekly `minNights=7` (rates **6967585/6967587**). Agent fix was stopped when agents were frozen; calendar/Fully flexible was ~`minStay=2` / FF=`1` last evidence (Sep 18).
3. **Weekly@7 origin:** nobody typed “set 7”; Cursor Agent hardcoded `"minNights": "7"` in `beds24_v1_booking_rates.py` on **PR #165**; live via Actions **35383953766** (2026-09-18 19:06Z).
4. **Access that day:** only human GitHub admin **elcidspain** (Ilia); bots cursor/vercel/Copilot; secrets only on this repo. Launch of bc-6d87 under Ilia’s Cursor/GitHub — no other named human collaborator.
5. **Left to check (human):** Booking Chalet 24→26 Sep shows no “7 Noches”; close/disable Weekly 6967585/6967587 or set minNights=1; room calendar minStay=1; re-enable workflows only by hand when ready.
