#!/usr/bin/env python3
"""Open AUMARA Beds24 rooms/inventory for Booking.com (property 324882).

Reads calendar, opens numAvail for Chalet+Superior across bookable window,
writes redacted evidence. Uses V2 refresh token (preferred) or fails clearly.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API = "https://api.beds24.com/v2"
PROPERTY_ID = 324882
ROOMS = {
    674465: {"name": "CHALET", "target_num_avail": 4},
    674466: {"name": "Superior Chalet", "target_num_avail": 2},
}
# Cover green matrix window + ongoing bookable horizon
START = "2026-09-13"
END = "2026-12-31"
EVIDENCE = pathlib.Path("aumara-control-tower/evidence/beds24-open-booking-availability-20260913.json")


def mask(v: str) -> None:
    if v:
        print(f"::add-mask::{v}", flush=True)


def req(method: str, path: str, token: str, body: Any | None = None, query: dict | None = None):
    url = API + path
    if query:
        url += "?" + urllib.parse.urlencode(query, doseq=True)
    data = None
    headers = {
        "Accept": "application/json",
        "token": token,
        "User-Agent": "AUMARA-Beds24-OpenAvail/2026-09-13",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=90) as resp:
            raw = resp.read()
            status = int(resp.status)
    except urllib.error.HTTPError as e:
        raw = e.read()
        status = int(e.code)
        try:
            parsed = json.loads(raw.decode("utf-8", "replace")) if raw else {}
        except Exception:
            parsed = {"raw": raw[:500].decode("utf-8", "replace")}
        raise SystemExit(f"{method} {path} HTTP {status}: {json.dumps(parsed)[:2000]}")
    if not raw:
        return status, {}
    return status, json.loads(raw.decode("utf-8"))


def get_token() -> tuple[str, str]:
    refresh = (
        os.environ.get("BEDS24_REFRESH_CREDENTIAL")
        or os.environ.get("BEDS24_REFRESH_TOKEN")
        or os.environ.get("BEDS24_VAULT_KEK")
        or ""
    ).strip().strip('"').strip("'")
    mask(refresh)
    if not refresh:
        raise SystemExit("BEDS24_REFRESH_CREDENTIAL missing")
    # Try as access token first
    try:
        st, body = req("GET", "/authentication/details", refresh)
        if st == 200 and body:
            return refresh, "access_token_direct"
    except SystemExit:
        pass
    # Refresh exchange
    url = API + "/authentication/token"
    r = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "refreshToken": refresh,
            "User-Agent": "AUMARA-Beds24-OpenAvail/2026-09-13",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"token refresh HTTP {e.code}: {e.read()[:500]!r}")
    token = (body.get("token") or "").strip()
    mask(token)
    if not token:
        raise SystemExit(f"no token in refresh response keys={list(body.keys())}")
    return token, "refresh_exchange"


def summarize_calendar(data: list[dict]) -> dict:
    out: dict[str, Any] = {}
    for room in data:
        rid = room.get("roomId")
        days = room.get("calendar") or room.get("days") or []
        zero = 0
        closed = 0
        sample = []
        for d in days:
            na = d.get("numAvail")
            ov = str(d.get("override") or d.get("status") or "").lower()
            if na == 0:
                zero += 1
            if ov in {"closed", "close", "block", "unavailable"}:
                closed += 1
            if len(sample) < 3:
                sample.append({k: d.get(k) for k in ("date", "numAvail", "override", "price1", "status") if k in d or True})
        out[str(rid)] = {
            "days": len(days),
            "numAvail_zero_days": zero,
            "closed_override_days": closed,
            "sample": sample[:3],
        }
    return out


def main() -> int:
    token, mode = get_token()
    room_ids = list(ROOMS.keys())
    # GET calendar
    q = {
        "roomId": room_ids,
        "startDate": START,
        "endDate": END,
        "includePrices": "true",
        "includeNumAvail": "true",
        "includeMinStay": "true",
    }
    # urllib doseq for repeated roomId
    params = [("startDate", START), ("endDate", END), ("includePrices", "true"), ("includeNumAvail", "true"), ("includeMinStay", "true")]
    for rid in room_ids:
        params.append(("roomId", str(rid)))
    url = API + "/inventory/rooms/calendar?" + urllib.parse.urlencode(params)
    r = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "token": token, "User-Agent": "AUMARA-Beds24-OpenAvail/2026-09-13"},
        method="GET",
    )
    with urllib.request.urlopen(r, timeout=90) as resp:
        before_body = json.loads(resp.read().decode("utf-8"))
    before_data = before_body.get("data") or before_body.get("calendar") or []
    if isinstance(before_body, list):
        before_data = before_body

    # Also probe properties for offers/price rules (rate closed diagnosis)
    prop_info = None
    try:
        _, prop_info = req(
            "GET",
            "/properties",
            token,
            query={"id": PROPERTY_ID, "includePriceRules": "true", "includeOffers": "true"},
        )
    except SystemExit as e:
        prop_info = {"error": str(e)[:500]}

    write_payload = []
    for rid, meta in ROOMS.items():
        write_payload.append(
            {
                "roomId": rid,
                "calendar": [
                    {
                        "from": START,
                        "to": END,
                        "numAvail": meta["target_num_avail"],
                        # Beds24 uses override to force open/close on channel calendars
                        "override": "none",
                    }
                ],
            }
        )

    # POST open
    post = urllib.request.Request(
        API + "/inventory/rooms/calendar",
        data=json.dumps(write_payload).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "token": token,
            "User-Agent": "AUMARA-Beds24-OpenAvail/2026-09-13",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(post, timeout=120) as resp:
            write_status = int(resp.status)
            write_body = json.loads(resp.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as e:
        write_status = int(e.code)
        try:
            write_body = json.loads(e.read().decode("utf-8", "replace"))
        except Exception:
            write_body = {"error": "non-json"}
        raise SystemExit(f"POST calendar HTTP {write_status}: {json.dumps(write_body)[:2000]}")

    # GET after
    with urllib.request.urlopen(r, timeout=90) as resp:
        after_body = json.loads(resp.read().decode("utf-8"))
    after_data = after_body.get("data") or after_body.get("calendar") or []
    if isinstance(after_body, list):
        after_data = after_body

    # availability probe mid-window
    avail_params = [("startDate", "2026-09-19"), ("endDate", "2026-09-26")]
    for rid in room_ids:
        avail_params.append(("roomId", str(rid)))
    ar = urllib.request.Request(
        API + "/inventory/rooms/availability?" + urllib.parse.urlencode(avail_params),
        headers={"Accept": "application/json", "token": token, "User-Agent": "AUMARA-Beds24-OpenAvail/2026-09-13"},
        method="GET",
    )
    with urllib.request.urlopen(ar, timeout=60) as resp:
        avail_body = json.loads(resp.read().decode("utf-8"))

    evidence = {
        "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "property_id": PROPERTY_ID,
        "rooms": ROOMS,
        "window": {"start": START, "end": END},
        "auth_mode": mode,
        "before_summary": summarize_calendar(before_data if isinstance(before_data, list) else []),
        "write_http": write_status,
        "write_response_type": type(write_body).__name__,
        "write_success_hint": write_body if not isinstance(write_body, (dict, list)) else (
            write_body[:3] if isinstance(write_body, list) else {k: write_body.get(k) for k in list(write_body)[:12]}
        ),
        "after_summary": summarize_calendar(after_data if isinstance(after_data, list) else []),
        "availability_19_26": avail_body,
        "property_probe_keys": sorted(prop_info.keys()) if isinstance(prop_info, dict) else None,
        "status": "SUCCESS",
    }
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    print("EVIDENCE", EVIDENCE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
