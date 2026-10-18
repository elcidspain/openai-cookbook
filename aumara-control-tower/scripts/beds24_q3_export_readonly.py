#!/usr/bin/env python3
"""Read-only Beds24 v2 export (GET only). Writes raw JSON to $OUT_DIR; prints only counts."""
import json, os, pathlib, sys, urllib.parse
sys.path.insert(0, os.path.dirname(__file__))
from beds24_elcid_studio_audit import get_access_token, request_json

OUT = pathlib.Path(os.environ["OUT_DIR"]); OUT.mkdir(parents=True, exist_ok=True)
token, _, base, _, _ = get_access_token()
H = {"token": token}

def get_all(path, params):
    rows, page, meta = [], 1, []
    while page <= 60:
        q = list(params) + ([("page", page)] if page > 1 else [])
        st, resp = request_json("GET", path + "?" + urllib.parse.urlencode(q), headers=H, api_base=base)
        meta.append({"page": page, "http": st, "keys": sorted(resp.keys()) if isinstance(resp, dict) else None,
                     "error": (resp.get("error") if isinstance(resp, dict) else None)})
        if not (200 <= st < 300) or not isinstance(resp, dict):
            break
        data = resp.get("data") or []
        rows.extend(data if isinstance(data, list) else [data])
        pages = resp.get("pages") or {}
        if isinstance(pages, dict) and pages.get("nextPageExists"):
            page += 1
        else:
            break
    return rows, meta

result = {"api_base": base, "queries": {}}
props, m = get_all("/properties", [("includeAllRooms", "true")])
result["properties"] = props; result["queries"]["properties"] = m
common = [("includeInvoiceItems", "true"), ("includeInfoItems", "true"), ("includeBookingGroup", "true")]
statuses = [("status", s) for s in ("confirmed", "request", "new", "cancelled", "black", "inquiry")]
qs = {
    "stay_overlap": [("arrivalTo", "2026-09-30"), ("departureFrom", "2026-07-02")],
    "booked_in_q3": [("bookingTimeFrom", "2026-07-01T00:00:00"), ("bookingTimeTo", "2026-09-30T23:59:59")],
    "arrival_q3": [("arrivalFrom", "2026-07-01"), ("arrivalTo", "2026-09-30")],
}
for name, f in qs.items():
    for sname, s in (("default", []), ("allstatus", statuses)):
        rows, m = get_all("/bookings", f + s + common)
        key = f"{name}_{sname}"
        result[key] = rows; result["queries"][key] = m
        print(key, len(rows), [x["http"] for x in m])
print("properties", len(props), sorted({p.get("id") for p in props if isinstance(p, dict)}))
(OUT / "beds24_q3_raw.json").write_text(json.dumps(result, ensure_ascii=False))
