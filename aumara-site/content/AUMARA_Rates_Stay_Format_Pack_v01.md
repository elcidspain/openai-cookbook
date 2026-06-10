# AUMARA Rates & Stay Format Pack v0.1

Source: `control_tower_v9_ordered_cutover_pack`, especially `05_Rates_Source_Inputs_2026.csv` and `07_Rates_Grid_2026.csv`.

## Property

Booking property reference: `14953869`.

## Rate logic

- Currency: EUR.
- Period: 2026 full year.
- Weekend uplift: +10% on Friday / Saturday.
- Holiday uplift: +10% pending holiday list.

## Season bands

| Season | S7 nightly | S9 nightly |
|---|---:|---:|
| Jan–Mar | €200 | €320 |
| Apr–Jun | €250 | €350 |
| Jul–Sep | €320 | €512 |
| Oct–Dec | €250 | €400 |

## Public house products

| Product | House type | Min stay | 3–5 nights | 6+ nights | Commercial meaning |
|---|---|---:|---:|---:|---|
| AUMARA Madrid 7 | S7 | 2 | 0% | 0% | Base compact 2-night product |
| AUMARA Sevilla 7 | S7 | 3 | -12% | -15% | 3+ night slow stay |
| AUMARA Granada 7 | S7 | 3 | -12% | -16% | 3+ night slow stay |
| AUMARA Valencia 7 | S7 | 6 | 0% | -20% | Long-stay compact product |
| AUMARA Verde 9 | S9 | 3 | 0% | -10% | Superior 3+ night product |
| AUMARA Oro 9 | S9 | 3 | 0% | -10% | Superior 3+ night product |

## Website language

AUMARA works with two house families and several stay formats:

- S7 Compact Houses: 2-night escape, 3+ night slow stay, and 6+ night longer stay.
- S9 Superior Houses: larger house format for families, retreats and premium slow weeks.

Public copy can use “from” prices:

- Compact houses from €200 / night in low season.
- Superior houses from €320 / night in low season.
- Peak season from €320 / night for S7 and €512 / night for S9 before weekend / holiday uplift.

## Channel notes

This rate logic is suitable for Booking/Beds24 import or manual channel setup, but should not be pushed until channel mapping and access are clean.

Known channel blocker from Beds24 / Booking.com emails:

- Aumara El Cid — Chalet — roomId 674465.
- Aumara El Cid — Superior Chalet — roomId 674466.
- propid 324882 — Aumara El Cid.
- ownerid 165022 — EL CID / AUMARA.
- Error: `HOTEL_ACCESS_DENIED` / forbidden hotel id(s), including hotel_id 14953869.

## Operating rule

No OTA push without:

1. calendar status verified;
2. unit mapping verified;
3. rates verified;
4. minimum stay verified;
5. photos verified;
6. policies verified;
7. direct enquiry fallback active.
