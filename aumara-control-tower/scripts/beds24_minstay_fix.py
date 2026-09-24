#!/usr/bin/env python3
"""Force AUMARA Beds24 minimum stay to 1 night (property 324882).

Layers fixed (short stays were blocked by more than one rule):
1) Room defaults (V1 setProperty roomTypes.minStay) — historically 2
2) Calendar daily minStay (V2 POST /inventory/rooms/calendar) across
   2026-09-13 .. 2026-12-31
3) V1 rates minNights — Weekly plans were created with minNights=7 by
   beds24_v1_booking_rates.py (commit path open-channel-rates)

Does NOT change prices or numAvail. Does NOT create/cancel bookings.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API = "https://api.beds24.com/v2"
V1 = "https://api.beds24.com/json"
PROPERTY_ID = 324882
ROOMS = {
    674465: {"name": "CHALET"},
    674466: {"name": "Superior Chalet"},
}
START = "2026-09-13"
END = "2026-12-31"
PROBE_START = "2026-09-20"
PROBE_END = "2026-10-15"
CONFIRM_START = "2026-09-20"
CONFIRM_END = "2026-09-30"
TARGET_MIN_STAY = 1
TARGET_MAX_STAY = 365
FOCUS_DATE = "2026-09-24"
ROOT = pathlib.Path(__file__).resolve().parents[1]
VAULT = ROOT / "evidence" / "beds24-refresh-vault.json"
EVIDENCE = ROOT / "evidence" / "beds24-minstay-fix-20260924.json"
# Also land under open-avail artifact glob so CI always uploads it.
EVIDENCE_ALIAS = ROOT / "evidence" / "beds24-open-booking-availability-minstay-20260924.json"


def mask(v: str) -> None:
    if v:
        print(f"::add-mask::{v}", flush=True)


def vault_key(kek: str) -> bytes:
    digest = hashlib.sha256(("AUMARA_BEDS24_REFRESH_VAULT_V1\0" + kek).encode()).digest()
    import base64

    return base64.urlsafe_b64encode(digest)


def load_refresh() -> str:
    direct = (
        os.environ.get("BEDS24_REFRESH_CREDENTIAL")
        or os.environ.get("BEDS24_REFRESH_TOKEN")
        or ""
    ).strip().strip('"').strip("'")
    kek = (os.environ.get("BEDS24_VAULT_KEK") or "").strip().strip('"').strip("'")
    mask(direct)
    mask(kek)
    if direct and (not kek or direct != kek):
        print("auth_source=env_refresh", flush=True)
        return direct
    if kek and VAULT.exists():
        from cryptography.fernet import Fernet

        vault_data = json.loads(VAULT.read_text(encoding="utf-8"))
        cipher = vault_data.get("ciphertext")
        if not cipher:
            raise SystemExit("vault missing ciphertext")
        cred = Fernet(vault_key(kek)).decrypt(cipher.encode()).decode().strip()
        mask(cred)
        print("auth_source=vault_decrypt", flush=True)
        return cred
    raise SystemExit("No Beds24 refresh credential available")


def exchange_token(refresh: str) -> str:
    request = urllib.request.Request(
        API + "/authentication/token",
        headers={
            "Accept": "application/json",
            "refreshToken": refresh,
            "User-Agent": "AUMARA-MinStayFix/2",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"refresh HTTP {e.code}: {e.read()[:800]!r}")
    token = (body.get("token") or "").strip()
    mask(token)
    if not token:
        raise SystemExit(f"no token keys={list(body.keys())}")
    print("token_mode=refresh_exchange", flush=True)
    return token


def http_json(
    method: str, url: str, token: str, body: Any | None = None, raise_http: bool = True
):
    data = None
    headers = {
        "Accept": "application/json",
        "token": token,
        "User-Agent": "AUMARA-MinStayFix/2",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
            return int(resp.status), (json.loads(raw.decode()) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            parsed = json.loads(raw.decode("utf-8", "replace")) if raw else {}
        except Exception:
            parsed = {"raw": raw[:500].decode("utf-8", "replace")}
        if raise_http:
            raise SystemExit(f"{method} {url} HTTP {e.code}: {json.dumps(parsed)[:2000]}")
        return int(e.code), parsed


def v1_keys() -> tuple[str, str] | None:
    api = (os.environ.get("BEDS24_API_KEY") or "").strip().strip('"').strip("'")
    prop = (os.environ.get("BEDS24_PROP_KEY") or "").strip().strip('"').strip("'")
    mask(api)
    mask(prop)
    if api and prop:
        return api, prop
    return None


def v1_call(path: str, payload: dict, api: str, prop: str) -> tuple[int, Any]:
    body = dict(payload)
    body["authentication"] = {"apiKey": api, "propKey": prop}
    req = urllib.request.Request(
        f"{V1}/{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "AUMARA-MinStayFix/2",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read()
            status = int(resp.status)
            data = json.loads(raw.decode("utf-8", "replace")) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        status = int(e.code)
        try:
            data = json.loads(raw.decode("utf-8", "replace")) if raw else {}
        except Exception:
            data = {"raw": raw[:500].decode("utf-8", "replace")}
    time.sleep(2.2)
    return status, data


def calendar_data(payload: Any) -> list:
    data = (payload or {}).get("data") if isinstance(payload, dict) else payload
    return data if isinstance(data, list) else []


def day_min_stay(day: dict) -> Any:
    for key in ("minStay", "minStayArrival", "minNights", "minimumStay"):
        if key in day and day[key] is not None:
            return day[key]
    return None


def summarize_minstay(rooms: list, focus: str = FOCUS_DATE) -> dict:
    out: dict[str, Any] = {}
    for room in rooms or []:
        rid = str(room.get("roomId"))
        days = room.get("calendar") or []
        values: list[Any] = []
        by_date: dict[str, Any] = {}
        for d in days:
            from_d = d.get("from") or d.get("date") or d.get("startDate")
            date_key = from_d[:10] if isinstance(from_d, str) and len(from_d) >= 10 else None
            ms = day_min_stay(d)
            if ms is not None:
                values.append(ms)
            if date_key:
                by_date[date_key] = {
                    "minStay": ms,
                    "maxStay": d.get("maxStay"),
                    "numAvail": d.get("numAvail"),
                    "price1": d.get("price1"),
                }
        focus_window = {
            k: by_date[k] for k in sorted(by_date) if "2026-09-20" <= k <= "2026-09-30"
        }
        hist: dict[str, int] = {}
        for v in values:
            hist[str(v)] = hist.get(str(v), 0) + 1
        out[rid] = {
            "name": ROOMS.get(int(rid), {}).get("name") if rid.isdigit() else None,
            "days": len(days),
            "minStay_histogram": hist,
            "focus_date": focus,
            "focus_minStay": (by_date.get(focus) or {}).get("minStay"),
            "focus_window_2026_09_20_30": focus_window,
            "sample_first3": days[:3],
            "keys_on_first_day": sorted((days[0] or {}).keys()) if days else [],
        }
    return out


def build_minstay_payload() -> list[dict]:
    return [
        {
            "roomId": rid,
            "calendar": [
                {
                    "from": START,
                    "to": END,
                    "minStay": TARGET_MIN_STAY,
                    "minStayArrival": TARGET_MIN_STAY,
                    "maxStay": TARGET_MAX_STAY,
                }
            ],
        }
        for rid in ROOMS
    ]


def fix_v1_room_defaults(api: str, prop: str) -> dict[str, Any]:
    before_status, before = v1_call(
        "getProperty",
        {"includeRooms": True, "includeRoomUnits": False, "includeAccountAccess": False},
        api,
        prop,
    )
    rooms_before = []
    props = before.get("getProperty") if isinstance(before, dict) else None
    if isinstance(props, list) and props:
        rooms_before = props[0].get("roomTypes") or []
    snapshot_before = [
        {
            "roomId": r.get("roomId"),
            "name": r.get("name"),
            "minStay": r.get("minStay"),
            "maxStay": r.get("maxStay"),
        }
        for r in rooms_before
        if str(r.get("roomId")) in {str(x) for x in ROOMS}
    ]
    room_mods = [
        {
            "action": "modify",
            "roomId": str(rid),
            "minStay": str(TARGET_MIN_STAY),
            "maxStay": str(TARGET_MAX_STAY),
        }
        for rid in ROOMS
    ]
    write_status, write_body = v1_call(
        "setProperty",
        {"setProperty": [{"action": "modify", "roomTypes": room_mods}]},
        api,
        prop,
    )
    after_status, after = v1_call(
        "getProperty",
        {"includeRooms": True, "includeRoomUnits": False, "includeAccountAccess": False},
        api,
        prop,
    )
    rooms_after = []
    props_a = after.get("getProperty") if isinstance(after, dict) else None
    if isinstance(props_a, list) and props_a:
        rooms_after = props_a[0].get("roomTypes") or []
    snapshot_after = [
        {
            "roomId": r.get("roomId"),
            "name": r.get("name"),
            "minStay": r.get("minStay"),
            "maxStay": r.get("maxStay"),
        }
        for r in rooms_after
        if str(r.get("roomId")) in {str(x) for x in ROOMS}
    ]
    return {
        "get_before_http": before_status,
        "rooms_before": snapshot_before,
        "write_http": write_status,
        "write_ok": 200 <= write_status < 300,
        "get_after_http": after_status,
        "rooms_after": snapshot_after,
    }


def _as_list(payload: Any, *keys: str) -> list:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []
    for key in keys:
        val = payload.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
        if isinstance(val, dict):
            for nested in ("rates", "rate", "data", "items"):
                maybe = val.get(nested)
                if isinstance(maybe, list):
                    return [x for x in maybe if isinstance(x, dict)]
            # dict keyed by id
            out = []
            for k, v in val.items():
                if isinstance(v, dict):
                    row = dict(v)
                    row.setdefault("rateId", row.get("rateId") or row.get("id") or k)
                    out.append(row)
            if out:
                return out
    return []


def fix_v1_rates_min_nights(api: str, prop: str) -> dict[str, Any]:
    status, body = v1_call("getRates", {}, api, prop)
    rows = _as_list(body, "getRates", "setRates", "rates", "data")
    if not rows and isinstance(body, list):
        rows = [x for x in body if isinstance(x, dict)]
    print(f"v1_getRates_http={status} rows={len(rows)}", flush=True)
    before = []
    patches = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        rid = raw.get("roomId") or raw.get("roomid")
        try:
            rid_i = int(rid)
        except (TypeError, ValueError):
            continue
        if rid_i not in ROOMS:
            continue
        rate_id = raw.get("rateId") or raw.get("id")
        name = str(raw.get("name") or raw.get("rateName") or "")
        min_n = raw.get("minNights") or raw.get("minStay")
        before.append(
            {
                "rateId": rate_id,
                "roomId": rid_i,
                "name": name,
                "minNights": min_n,
            }
        )
        try:
            min_i = int(str(min_n).strip()) if min_n is not None else None
        except ValueError:
            min_i = None
        if min_i is None or min_i > TARGET_MIN_STAY:
            patches.append(
                {
                    "action": "modify",
                    "rateId": str(rate_id),
                    "roomId": str(rid_i),
                    "minNights": str(TARGET_MIN_STAY),
                }
            )
    # Deduplicate by rateId
    seen = set()
    uniq = []
    for patch in patches:
        rid = patch["rateId"]
        if rid in seen:
            continue
        seen.add(rid)
        uniq.append(patch)
    patches = uniq
    print(f"v1_rate_patches={len(patches)} sample={patches[:6]}", flush=True)
    write_status, write_body = (None, None)
    if patches:
        write_status, write_body = v1_call("setRates", {"setRates": patches}, api, prop)
    # Re-read
    status2, body2 = v1_call("getRates", {}, api, prop)
    rows2 = _as_list(body2, "getRates", "setRates", "rates", "data")
    if not rows2 and isinstance(body2, list):
        rows2 = [x for x in body2 if isinstance(x, dict)]
    print(f"v1_getRates_after_http={status2} rows={len(rows2)}", flush=True)
    after = []
    for raw in rows2:
        if not isinstance(raw, dict):
            continue
        rid = raw.get("roomId") or raw.get("roomid")
        try:
            rid_i = int(rid)
        except (TypeError, ValueError):
            continue
        if rid_i not in ROOMS:
            continue
        after.append(
            {
                "rateId": raw.get("rateId") or raw.get("id"),
                "roomId": rid_i,
                "name": str(raw.get("name") or raw.get("rateName") or ""),
                "minNights": raw.get("minNights") or raw.get("minStay"),
            }
        )
    return {
        "get_before_http": status,
        "rates_before": before,
        "patches": patches,
        "write_http": write_status,
        "write_body_type": type(write_body).__name__,
        "get_after_http": status2,
        "rates_after": after,
    }


def probe_offers(token: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    arrival, departure = "2026-09-24", "2026-09-26"
    for rid, meta in ROOMS.items():
        params = urllib.parse.urlencode(
            [
                ("roomId", str(rid)),
                ("arrival", arrival),
                ("departure", departure),
                ("numAdults", "2"),
            ]
        )
        status, body = http_json(
            "GET", API + "/inventory/rooms/offers?" + params, token, raise_http=False
        )
        out[str(rid)] = {
            "http": status,
            "name": meta["name"],
            "arrival": arrival,
            "departure": departure,
            "success": body.get("success") if isinstance(body, dict) else None,
            "error": body.get("error") if isinstance(body, dict) else None,
            "count": body.get("count") if isinstance(body, dict) else None,
            "top_keys": sorted(body.keys())[:20] if isinstance(body, dict) else None,
        }
    return out


def attribution(v1_rates: dict | None, v1_rooms: dict | None, before_cal: dict) -> dict:
    weekly_before = []
    if v1_rates:
        for row in v1_rates.get("rates_before") or []:
            name = str(row.get("name") or "").lower()
            try:
                mn = int(str(row.get("minNights")).strip()) if row.get("minNights") is not None else None
            except ValueError:
                mn = None
            if "weekly" in name or (mn is not None and mn >= 7):
                weekly_before.append(row)
    return {
        "who_set_minStay_7": {
            "actor": "aumara-control-tower/scripts/beds24_v1_booking_rates.py",
            "mechanism": 'setRates action=new name="Weekly" minNights="7"',
            "triggered_by": (
                "GitHub Action beds24-open-booking-channel-rates.yml "
                "(commit message marker [open-channel-rates] / workflow_dispatch)"
            ),
            "evidence": (
                "Weekly fixedPrices 6967585/6967587 exist for rooms 674465/674466; "
                "script historically hard-coded minNights=7 when creating Weekly rates. "
                "No human Beds24 UI actor is named by the API (no modifiedBy field)."
            ),
            "room_default_was": "minStay=2 (content audit 2026-08-25 + live V1 getProperty)",
            "calendar_before_this_fix": {
                rid: s.get("focus_minStay") for rid, s in (before_cal or {}).items()
            },
            "weekly_or_7plus_rates_before": weekly_before,
        },
        "v1_room_defaults_write": v1_rooms,
        "v1_rates_write": {
            "patched_count": len((v1_rates or {}).get("patches") or []),
            "rates_after": (v1_rates or {}).get("rates_after"),
        }
        if v1_rates
        else {"skipped": "BEDS24_API_KEY/PROP_KEY not in env"},
    }


def main() -> int:
    refresh = load_refresh()
    token = exchange_token(refresh)

    details_status, details_body = http_json(
        "GET", API + "/authentication/details", token, raise_http=False
    )
    scopes = []
    if isinstance(details_body, dict) and details_status == 200:
        scopes = details_body.get("scopes") or []
    print(
        f"details_http={details_status} scopes_count={len(scopes) if isinstance(scopes, list) else 0}",
        flush=True,
    )

    params = [
        ("startDate", PROBE_START),
        ("endDate", PROBE_END),
        ("includeMinStay", "true"),
        ("includePrices", "true"),
        ("includeNumAvail", "true"),
    ]
    for rid in ROOMS:
        params.append(("roomId", str(rid)))
    cal_url = API + "/inventory/rooms/calendar?" + urllib.parse.urlencode(params)
    _, before = http_json("GET", cal_url, token)
    before_data = calendar_data(before)
    before_summary = summarize_minstay(before_data)
    print(
        "BEFORE_FOCUS",
        {r: before_summary[r].get("focus_minStay") for r in before_summary},
        flush=True,
    )
    print(
        "BEFORE_HIST",
        {r: before_summary[r].get("minStay_histogram") for r in before_summary},
        flush=True,
    )

    keys = v1_keys()
    v1_rooms = None
    v1_rates = None
    if keys:
        api, prop = keys
        print("v1_keys=present", flush=True)
        v1_rooms = fix_v1_room_defaults(api, prop)
        print("V1_ROOMS_AFTER", v1_rooms.get("rooms_after"), flush=True)
        v1_rates = fix_v1_rates_min_nights(api, prop)
        print(
            "V1_RATES_AFTER",
            [
                {k: r.get(k) for k in ("rateId", "roomId", "name", "minNights")}
                for r in (v1_rates.get("rates_after") or [])
            ],
            flush=True,
        )
    else:
        print("v1_keys=absent_skipping_room_and_rate_defaults", flush=True)

    payload = build_minstay_payload()
    write_status, write_body = http_json(
        "POST", API + "/inventory/rooms/calendar", token, payload
    )
    print(f"calendar_write_http={write_status}", flush=True)

    confirm_params = [
        ("startDate", CONFIRM_START),
        ("endDate", CONFIRM_END),
        ("includeMinStay", "true"),
        ("includeNumAvail", "true"),
        ("includePrices", "true"),
    ]
    for rid in ROOMS:
        confirm_params.append(("roomId", str(rid)))
    confirm_url = API + "/inventory/rooms/calendar?" + urllib.parse.urlencode(confirm_params)
    _, after = http_json("GET", confirm_url, token)
    after_data = calendar_data(after)
    after_summary = summarize_minstay(after_data)
    print(
        "AFTER_FOCUS",
        {r: after_summary[r].get("focus_minStay") for r in after_summary},
        flush=True,
    )
    print(
        "AFTER_HIST",
        {r: after_summary[r].get("minStay_histogram") for r in after_summary},
        flush=True,
    )

    offers_after = probe_offers(token)
    attr = attribution(v1_rates, v1_rooms, before_summary)

    problems: list[str] = []
    # Prefer V1 room default confirmation when available
    if v1_rooms:
        for row in v1_rooms.get("rooms_after") or []:
            try:
                ms = int(str(row.get("minStay")).strip())
            except (TypeError, ValueError):
                ms = None
            if ms != 1:
                problems.append(
                    f"V1 room {row.get('roomId')} minStay={row.get('minStay')} want=1"
                )
    if v1_rates:
        for row in v1_rates.get("rates_after") or []:
            try:
                mn = int(str(row.get("minNights")).strip()) if row.get("minNights") is not None else None
            except ValueError:
                mn = None
            if mn is not None and mn > 1:
                problems.append(
                    f"V1 rate {row.get('rateId')} ({row.get('name')}) minNights={mn} want<=1"
                )
    for rid, s in after_summary.items():
        focus = s.get("focus_minStay")
        try:
            focus_n = int(focus) if focus is not None else None
        except (TypeError, ValueError):
            focus_n = None
        # Calendar may still echo room default; after V1 room fix it should be 1.
        if focus_n is not None and focus_n > 1:
            problems.append(f"calendar room {rid} {FOCUS_DATE} minStay={focus} (want 1)")

    # If V1 unavailable, require calendar focus == 1
    if not keys:
        for rid, s in after_summary.items():
            focus = s.get("focus_minStay")
            try:
                focus_n = int(focus) if focus is not None else None
            except (TypeError, ValueError):
                focus_n = None
            if focus_n != 1:
                problems.append(
                    f"no-V1 calendar room {rid} {FOCUS_DATE} minStay={focus} want=1"
                )

    status = "PASS" if not problems else "FAIL"
    evidence = {
        "schema": "aumara.beds24-minstay-fix.v2",
        "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "property_id": PROPERTY_ID,
        "rooms": ROOMS,
        "window_written": {
            "start": START,
            "end": END,
            "minStay": TARGET_MIN_STAY,
            "maxStay": TARGET_MAX_STAY,
        },
        "confirm_window": {"start": CONFIRM_START, "end": CONFIRM_END},
        "target_minStay": TARGET_MIN_STAY,
        "auth": {
            "details_http": details_status,
            "scopes_count": len(scopes) if isinstance(scopes, list) else 0,
            "scopes": scopes if isinstance(scopes, list) else None,
            "v1_keys_present": bool(keys),
        },
        "before_summary": before_summary,
        "calendar_write_http": write_status,
        "calendar_write_body_sample": write_body[:4]
        if isinstance(write_body, list)
        else write_body,
        "after_summary": after_summary,
        "v1_room_defaults": v1_rooms,
        "v1_rates": v1_rates,
        "offers_after_2night": offers_after,
        "attribution": attr,
        "problems": problems,
        "status": status,
        "secret_exposed": False,
    }
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
    EVIDENCE.write_text(blob, encoding="utf-8")
    EVIDENCE_ALIAS.write_text(blob, encoding="utf-8")
    try:
        mirror = pathlib.Path("/workspace/evidence/beds24-minstay-fix-20260924.json")
        mirror.parent.mkdir(parents=True, exist_ok=True)
        mirror.write_text(blob, encoding="utf-8")
    except Exception as e:
        print(f"mirror_skip={type(e).__name__}", flush=True)

    print(
        json.dumps(
            {"status": status, "problems": problems, "evidence": str(EVIDENCE)},
            indent=2,
        )
    )
    print("EVIDENCE", EVIDENCE, flush=True)
    if problems:
        raise SystemExit(f"minStay fix incomplete: {problems}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
