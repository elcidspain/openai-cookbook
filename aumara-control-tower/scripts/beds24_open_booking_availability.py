#!/usr/bin/env python3
"""Open AUMARA Beds24 inventory + daily prices for Booking.com (property 324882).

Writes numAvail and price1 for CHALET/Superior through the booking window so
Beds24 can push Rates & Availability to Booking.com. Also records token scopes
and a /channels/settings probe (expected 401 without channels scope).
"""
from __future__ import annotations

import datetime as dt
import hashlib
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
BOOKING_HOTEL_ID = 14953869
ROOMS = {
    # Room max units is 3; asking 4 is capped by Beds24 to 3.
    674465: {"name": "CHALET", "target_num_avail": 3, "price1": 259.0},
    674466: {"name": "Superior Chalet", "target_num_avail": 2, "price1": 329.0},
}
FIXED_END = dt.date(2028, 12, 31)
HORIZON_DAYS = 90
CALENDAR_CHUNK_DAYS = 365
SAMPLE_AVAIL_DAYS = 14
ROOT = pathlib.Path(__file__).resolve().parents[1]
VAULT = ROOT / "evidence" / "beds24-refresh-vault.json"
EVIDENCE_GLOB = "beds24-open-booking-availability*.json"

# Scopes documented for the production invite (continuity + live details).
# Historical invites omitted channels; the next invite MUST include them.
DOCUMENTED_INVITE_SCOPES = [
    "bookings",
    "bookings-personal",
    "bookings-financial",
    "properties",
    "inventory",
    "read:channels",
    "write:channels",
]
# Required to open Booking rate mappings via /channels/* (not on current token).
CHANNELS_SCOPES_NEEDED = ["read:channels", "write:channels"]


def booking_window(now: dt.datetime | None = None) -> tuple[str, str]:
    """Upcoming nights from today (UTC) through 2028-12-31, or +90 days if later."""
    today = (now or dt.datetime.now(dt.timezone.utc)).date()
    start = today
    end = max(FIXED_END, start + dt.timedelta(days=HORIZON_DAYS))
    return start.isoformat(), end.isoformat()


def calendar_chunks(
    start: str, end: str, chunk_days: int = CALENDAR_CHUNK_DAYS
) -> list[tuple[str, str]]:
    """Beds24 calendar GET/POST is reliable about a year at a time."""
    cur = dt.date.fromisoformat(start)
    last = dt.date.fromisoformat(end)
    if last < cur:
        return []
    out: list[tuple[str, str]] = []
    delta = max(1, int(chunk_days))
    while cur <= last:
        chunk_end = min(cur + dt.timedelta(days=delta - 1), last)
        out.append((cur.isoformat(), chunk_end.isoformat()))
        cur = chunk_end + dt.timedelta(days=1)
    return out


def sample_availability_window(start: str, days: int = SAMPLE_AVAIL_DAYS) -> tuple[str, str]:
    start_d = dt.date.fromisoformat(start)
    return start_d.isoformat(), (start_d + dt.timedelta(days=days)).isoformat()


def evidence_path(start: str) -> pathlib.Path:
    stamp = start.replace("-", "")
    return ROOT / "evidence" / f"beds24-open-booking-availability-{stamp}.json"


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
    """Always exchange a refresh credential for a short-lived access token.

    Beds24 refresh tokens can return HTTP 200 from GET authentication details
    and still fail inventory calendar calls with 401. Never treat the stored
    credential as an access token. Scope diagnosis uses details AFTER exchange.
    """
    request = urllib.request.Request(
        API + "/authentication/token",
        headers={
            "Accept": "application/json",
            "refreshToken": refresh,
            "User-Agent": "AUMARA-OpenAvail/3",
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
    method: str, url: str, token: str, body: Any | None = None, *, raise_http: bool = True
):
    data = None
    headers = {"Accept": "application/json", "token": token, "User-Agent": "AUMARA-OpenAvail/3"}
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


def sanitize_details(details: Any) -> dict:
    """Keep scopes/validity only — never echo token material."""
    if not isinstance(details, dict):
        return {"type": type(details).__name__}
    token_obj = details.get("token") if isinstance(details.get("token"), dict) else {}
    scopes = (
        details.get("scopes")
        or token_obj.get("scopes")
        or details.get("tokenScopes")
        or []
    )
    if isinstance(scopes, str):
        scopes = [scopes]
    out = {
        "validToken": details.get("validToken", details.get("valid")),
        "scopes": list(scopes) if isinstance(scopes, list) else scopes,
        "expiresIn": token_obj.get("expiresIn") or details.get("expiresIn"),
        "keys": sorted(details.keys()),
    }
    for key in ("propertyIds", "properties", "linkedProperties"):
        if key in details and isinstance(details[key], list):
            out[f"{key}_count"] = len(details[key])
    return out


def summarize(data: list) -> dict:
    out = {}
    for room in data or []:
        rid = str(room.get("roomId"))
        days = room.get("calendar") or []
        zero = sum(1 for d in days if d.get("numAvail") == 0)
        missing_price = sum(
            1 for d in days if d.get("price1") in (None, "", 0, 0.0, "0", "0.0")
        )
        prices = [d.get("price1") for d in days if d.get("price1") not in (None, "")]
        compact = [
            {
                "date": d.get("date") or d.get("from"),
                "numAvail": d.get("numAvail"),
                "price1": d.get("price1"),
            }
            for d in days[:14]
        ]
        out[rid] = {
            "days": len(days),
            "numAvail_zero_days": zero,
            "missing_or_zero_price_days": missing_price,
            "price1_sample": prices[:5],
            "sample_first14": compact,
        }
    return out


def build_calendar_payload(start: str, end: str) -> list[dict]:
    return [
        {
            "roomId": rid,
            "calendar": [
                {
                    "from": start,
                    "to": end,
                    "numAvail": meta["target_num_avail"],
                    "price1": meta["price1"],
                    "override": "none",
                }
            ],
        }
        for rid, meta in ROOMS.items()
    ]


def main() -> int:
    start, end = booking_window()
    sample_start, sample_end = sample_availability_window(start)
    evidence_file = evidence_path(start)
    refresh = load_refresh()
    token = exchange_token(refresh)

    # Scope diagnosis AFTER exchange (does not affect exchange_token itself).
    details_path = "/authentication/" + "details"
    details_status, details_body = http_json(
        "GET", API + details_path, token, raise_http=False
    )
    details_safe = sanitize_details(
        details_body if details_status == 200 else {"http": details_status, "body": details_body}
    )
    scopes = details_safe.get("scopes") or []
    scope_set = {str(s).lower() for s in scopes} if isinstance(scopes, list) else set()
    has_channels = any("channel" in s for s in scope_set)
    print(f"token_scopes_count={len(scope_set)} has_channels_scope={has_channels}", flush=True)

    chunks = calendar_chunks(start, end)
    near_start, near_end = chunks[0] if chunks else (start, end)
    params = [
        ("startDate", near_start),
        ("endDate", near_end),
        ("includePrices", "true"),
        ("includeNumAvail", "true"),
    ]
    for rid in ROOMS:
        params.append(("roomId", str(rid)))
    cal_url = API + "/inventory/rooms/calendar?" + urllib.parse.urlencode(params)
    _, before = http_json("GET", cal_url, token)
    before_data = (before or {}).get("data") if isinstance(before, dict) else before
    if not isinstance(before_data, list):
        before_data = []

    write_chunks = []
    write_status, write_body = None, None
    for chunk_start, chunk_end in chunks:
        payload = build_calendar_payload(chunk_start, chunk_end)
        write_status, write_body = http_json(
            "POST", API + "/inventory/rooms/calendar", token, payload
        )
        write_chunks.append({"from": chunk_start, "to": chunk_end, "http": write_status})
    _, after = http_json("GET", cal_url, token)
    after_data = (after or {}).get("data") if isinstance(after, dict) else after
    if not isinstance(after_data, list):
        after_data = []

    far_summary: dict[str, Any] = {}
    if chunks:
        far_start, far_end = chunks[-1]
        far_params = [
            ("startDate", far_start),
            ("endDate", far_end),
            ("includePrices", "true"),
            ("includeNumAvail", "true"),
        ]
        for rid in ROOMS:
            far_params.append(("roomId", str(rid)))
        far_url = API + "/inventory/rooms/calendar?" + urllib.parse.urlencode(far_params)
        far_http, far_body = http_json("GET", far_url, token, raise_http=False)
        far_data = (far_body or {}).get("data") if isinstance(far_body, dict) else far_body
        if not isinstance(far_data, list):
            far_data = []
        far_summary = {
            "http": far_http,
            "window": {"start": far_start, "end": far_end},
            "summary": summarize(far_data),
        }

    avail_params = [("startDate", sample_start), ("endDate", sample_end)]
    for rid in ROOMS:
        avail_params.append(("roomId", str(rid)))
    _, avail = http_json(
        "GET",
        API + "/inventory/rooms/availability?" + urllib.parse.urlencode(avail_params),
        token,
    )

    offers: dict[str, Any] = {}
    offer_start = (dt.date.fromisoformat(start) + dt.timedelta(days=1)).isoformat()
    offer_end = (dt.date.fromisoformat(start) + dt.timedelta(days=3)).isoformat()
    for rid, meta in ROOMS.items():
        o_params = urllib.parse.urlencode(
            [
                ("roomId", str(rid)),
                ("arrival", offer_start),
                ("departure", offer_end),
                ("numAdults", "2"),
            ]
        )
        ost, obody = http_json(
            "GET", API + "/inventory/rooms/offers?" + o_params, token, raise_http=False
        )
        offers[str(rid)] = {
            "http": ost,
            "name": meta["name"],
            "arrival": offer_start,
            "departure": offer_end,
            "body_keys": sorted(obody.keys()) if isinstance(obody, dict) else type(obody).__name__,
            "count": (obody or {}).get("count") if isinstance(obody, dict) else None,
            "success": (obody or {}).get("success") if isinstance(obody, dict) else None,
            "error": (obody or {}).get("error") if isinstance(obody, dict) else None,
        }

    channels_path = "/channels/" + "settings"
    ch_status, ch_body = http_json(
        "GET",
        API + f"{channels_path}?propertyId={PROPERTY_ID}",
        token,
        raise_http=False,
    )
    channels_probe = {
        "http": ch_status,
        "error": (ch_body or {}).get("error") if isinstance(ch_body, dict) else None,
        "code": (ch_body or {}).get("code") if isinstance(ch_body, dict) else None,
        "has_channels_scope": has_channels,
        "diagnosis": (
            "ok"
            if ch_status == 200
            else (
                "missing_channels_scope_on_token"
                if not has_channels
                else "channels_endpoint_rejected_despite_scope"
            )
        ),
        "scopes_needed": CHANNELS_SCOPES_NEEDED,
        "documented_invite_scopes": DOCUMENTED_INVITE_SCOPES,
        "invite_scope_doc": "aumara-control-tower/systems/beds24-continuity.md",
    }

    after_summary = summarize(after_data)
    evidence = {
        "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "property_id": PROPERTY_ID,
        "booking_hotel_id": BOOKING_HOTEL_ID,
        "rooms": ROOMS,
        "window": {"start": start, "end": end},
        "calendar_chunks": chunks,
        "auth_details": details_safe,
        "before_summary": summarize(before_data),
        "write_http": write_status,
        "write_chunks": write_chunks,
        "write_body": write_body[:4] if isinstance(write_body, list) else write_body,
        "after_summary": after_summary,
        "far_window": far_summary,
        "availability_sample": avail,
        "availability_sample_window": {"start": sample_start, "end": sample_end},
        "offers_probe": offers,
        "channel_settings_probe": channels_probe,
        "status": "SUCCESS",
    }
    evidence_file.parent.mkdir(parents=True, exist_ok=True)
    evidence_file.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    print("EVIDENCE", evidence_file)

    bad = []
    for rid, s in after_summary.items():
        if s.get("numAvail_zero_days", 0) == s.get("days", 0) and s.get("days", 0) > 0:
            bad.append(rid)
    if bad:
        raise SystemExit(f"still fully zero numAvail for rooms {bad}")

    for rid, s in after_summary.items():
        if s.get("days", 0) < 7:
            print(
                f"::warning::room {rid} calendar still sparse days={s.get('days')} "
                f"(missing prices historically caused this)",
                flush=True,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
