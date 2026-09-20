#!/usr/bin/env python3
"""Open AUMARA Beds24 inventory + Booking.com channel rate plans (property 324882).

Writes numAvail and price1 for CHALET/Superior through 2028-12-31 so Beds24 can
push Rates & Availability. When the token has channels scopes, also GET/POST
/channels/settings to open Fully flexible + Weekly. Without those scopes the
channel write is skipped (401 is missing scope, not a broken credential).
"""
from __future__ import annotations

import copy
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
# Continuity: working Booking hotel may be 16137893; V1 content last mapped 14953869.
HOTEL_WORKING = "16137893"
HOTEL_LEGACY = "14953869"
BOOKING_HOTEL_ID = int(HOTEL_LEGACY)
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
INVITE_UI_DOC = "aumara-control-tower/systems/beds24-continuity.md"

# One invite must include all of these. OpenAPI category is `channels`;
# token methods are `read:channels` / `write:channels`. Historical invites omitted them.
DOCUMENTED_INVITE_SCOPES = [
    "bookings",
    "bookings-personal",
    "bookings-financial",
    "properties",
    "inventory",
    "channels",
    "read:channels",
    "write:channels",
]
CHANNELS_SCOPES_NEEDED = ["read:channels", "write:channels"]
TARGET_RATE_PLANS = ("Fully flexible", "Weekly")
BOOKING_CHANNEL_QUERY = "booking"
SENSITIVE_PROPERTY_KEYS = {
    "email",
    "phone",
    "mobile",
    "fax",
    "address",
    "token",
    "password",
    "secret",
    "credential",
    "pictures",
    "texts",
}


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


def is_target_rate_name(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    name = value.strip().lower().replace("_", " ").replace("-", " ")
    if name in {"fully flexible", "weekly"}:
        return True
    if "fully flexible" in name:
        return True
    if name == "weekly" or "weekly rate" in name or name.endswith(" weekly"):
        return True
    return False


def enable_target_rate_plans(obj: Any) -> tuple[Any, int]:
    """Set enabled=true / closed=false on Fully flexible + Weekly nodes."""
    flipped = 0

    def walk(node: Any) -> Any:
        nonlocal flipped
        if isinstance(node, list):
            return [walk(item) for item in node]
        if not isinstance(node, dict):
            return node
        out = {key: walk(value) for key, value in node.items()}
        name_keys = ("name", "rateName", "ratePlanName", "ratePlan", "title")
        named = any(is_target_rate_name(out.get(key)) for key in name_keys)
        if named:
            for flag, want in (
                ("enabled", True),
                ("enable", True),
                ("closed", False),
                ("enableBooking", True),
                ("enableInventory", True),
                ("bookingComEnableBooking", 1),
                ("bookingComEnableInventory", 1),
            ):
                if flag in out and out[flag] != want:
                    out[flag] = want
                    flipped += 1
            if "enabled" not in out and "closed" not in out:
                out["enabled"] = True
                flipped += 1
        return out

    return walk(copy.deepcopy(obj)), flipped


def constructed_booking_rate_payload() -> list[dict]:
    """Best-effort POST body when GET settings have no named rate plans."""
    return [
        {
            "channel": BOOKING_CHANNEL_QUERY,
            "properties": [
                {
                    "id": PROPERTY_ID,
                    "roomTypes": [
                        {
                            "id": rid,
                            "enabled": True,
                            "ratePlans": [
                                {"name": name, "enabled": True}
                                for name in TARGET_RATE_PLANS
                            ],
                        }
                        for rid in ROOMS
                    ],
                }
            ],
        }
    ]


def summarize_channel_body(body: Any) -> Any:
    """Keep channel/rate identifiers only — drop large nested content."""
    if not isinstance(body, (dict, list)):
        return type(body).__name__
    keep_keys = {
        "channel",
        "id",
        "name",
        "enabled",
        "closed",
        "enable",
        "rateId",
        "rateCode",
        "ratePlanId",
        "rateName",
        "ratePlanName",
        "hotelId",
        "propertyId",
        "roomId",
        "roomTypes",
        "ratePlans",
        "properties",
        "error",
        "code",
        "success",
        "type",
        "count",
        "data",
    }

    def walk(node: Any, depth: int = 0) -> Any:
        if depth > 8:
            return "[DEPTH_LIMIT]"
        if isinstance(node, list):
            return [walk(item, depth + 1) for item in node[:40]]
        if isinstance(node, dict):
            out = {}
            for key, value in node.items():
                lk = str(key).lower()
                if lk in SENSITIVE_PROPERTY_KEYS or "token" in lk or "password" in lk:
                    continue
                if key in keep_keys or "booking" in lk or "rate" in lk or "hotel" in lk:
                    out[str(key)] = walk(value, depth + 1)
            return out
        if isinstance(node, str):
            return node[:120]
        return node

    return walk(body)


def hotel_id_hits(obj: Any) -> dict[str, list[str]]:
    """Locate working (16137893) vs legacy (14953869) hotel IDs in a JSON tree."""
    found: dict[str, list[str]] = {HOTEL_WORKING: [], HOTEL_LEGACY: []}

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}")
            return
        if isinstance(node, list):
            for index, value in enumerate(node[:80]):
                walk(value, f"{path}[{index}]")
            return
        if node is None or isinstance(node, bool):
            return
        text = str(node).strip()
        for hotel in found:
            if text == hotel:
                found[hotel].append(path)
            elif hotel in text and text != hotel:
                found[hotel].append(f"{path} contains {text[:48]}")

    walk(obj, "$")
    return {hotel: paths[:20] for hotel, paths in found.items()}


def summarize_property_linkage(prop: dict) -> dict[str, Any]:
    rooms = []
    for room in prop.get("roomTypes") or []:
        if not isinstance(room, dict):
            continue
        rooms.append(
            {
                "id": room.get("id"),
                "name": room.get("name"),
                "qty": room.get("qty"),
            }
        )
    price_rules = []
    for rule in prop.get("priceRules") or []:
        if not isinstance(rule, dict):
            continue
        channels = rule.get("channels") if isinstance(rule.get("channels"), dict) else {}
        booking = channels.get("booking") if isinstance(channels.get("booking"), dict) else {}
        price_rules.append(
            {
                "id": rule.get("id"),
                "name": rule.get("name"),
                "minimumStay": rule.get("minimumStay"),
                "booking_enabled": booking.get("enabled"),
                "booking_rateCode": booking.get("rateCode"),
            }
        )
    return {
        "id": prop.get("id"),
        "name": prop.get("name"),
        "channelLinks": prop.get("channelLinks"),
        "rooms": rooms,
        "price_rules": price_rules[:16],
        "hotel_id_hits": hotel_id_hits(prop),
    }


def classify_hotel_linkage(hits: dict[str, list[str]]) -> str:
    working = bool(hits.get(HOTEL_WORKING))
    legacy = bool(hits.get(HOTEL_LEGACY))
    if working and not legacy:
        return "working_16137893_only"
    if legacy and not working:
        return "legacy_14953869_only"
    if working and legacy:
        return "both_present"
    return "absent_from_v2_properties"


def probe_property_hotel_linkage(token: str) -> dict[str, Any]:
    """GET /properties (current token has properties scope) — no secrets logged."""
    query = urllib.parse.urlencode(
        [
            ("id", str(PROPERTY_ID)),
            ("includeAllRooms", "true"),
            ("includePriceRules", "true"),
        ]
    )
    status, body = http_json(
        "GET", API + "/properties?" + query, token, raise_http=False
    )
    rows = (body or {}).get("data") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        rows = []
    aumara = next((row for row in rows if isinstance(row, dict) and row.get("id") == PROPERTY_ID), None)
    summary = summarize_property_linkage(aumara) if isinstance(aumara, dict) else None
    hits = hotel_id_hits(aumara if isinstance(aumara, dict) else body)
    return {
        "http": status,
        "property_count": len(rows),
        "error": (body or {}).get("error") if isinstance(body, dict) else None,
        "summary": summary,
        "hotel_id_hits": hits,
        "classification": classify_hotel_linkage(hits),
        "continuity_working": HOTEL_WORKING,
        "continuity_legacy": HOTEL_LEGACY,
        "v1_content_audit_mapped": HOTEL_LEGACY,
    }


def probe_fixed_prices(token: str) -> dict[str, Any]:
    """Inventory-scope read of fixed prices / Booking rate codes."""
    query = urllib.parse.urlencode(
        [("propertyId", str(PROPERTY_ID)), ("includeRateCodes", "true")]
    )
    status, body = http_json(
        "GET", API + "/inventory/fixedPrices?" + query, token, raise_http=False
    )
    rows = (body or {}).get("data") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        rows = []
    compact = []
    for row in rows[:40]:
        if not isinstance(row, dict):
            continue
        channels = row.get("channels") if isinstance(row.get("channels"), dict) else {}
        booking = channels.get("booking") if isinstance(channels.get("booking"), dict) else {}
        compact.append(
            {
                "id": row.get("id"),
                "name": row.get("name"),
                "roomId": row.get("roomId"),
                "minimumStay": row.get("minimumStay"),
                "booking_enabled": booking.get("enabled"),
                "booking_rateCode": booking.get("rateCode"),
                "target_rate": is_target_rate_name(row.get("name")),
            }
        )
    return {
        "http": status,
        "count": len(rows),
        "error": (body or {}).get("error") if isinstance(body, dict) else None,
        "rows": compact,
        "named_target_rates": [row for row in compact if row.get("target_rate")],
    }


def open_booking_channel_rate_plans(token: str, has_channels: bool) -> dict[str, Any]:
    """Open Fully flexible + Weekly via /channels/settings when scoped.

    Missing channels scopes → skip write (401 is expected). Do not treat that
    as a broken BEDS24_REFRESH_CREDENTIAL.
    """
    settings_url = (
        API
        + "/channels/settings?"
        + urllib.parse.urlencode(
            [("propertyId", str(PROPERTY_ID)), ("channel", BOOKING_CHANNEL_QUERY)]
        )
    )
    get_status, get_body = http_json("GET", settings_url, token, raise_http=False)
    result: dict[str, Any] = {
        "has_channels_scope": has_channels,
        "get_http": get_status,
        "get_error": (get_body or {}).get("error") if isinstance(get_body, dict) else None,
        "get_summary": summarize_channel_body(get_body),
        "write_attempted": False,
        "write_http": None,
        "write_summary": None,
        "flipped_flags": 0,
        "target_rate_plans": list(TARGET_RATE_PLANS),
        "scopes_needed": CHANNELS_SCOPES_NEEDED,
        "documented_invite_scopes": DOCUMENTED_INVITE_SCOPES,
        "invite_ui_doc": INVITE_UI_DOC,
    }
    if get_status == 401 and not has_channels:
        result["status"] = "SKIPPED_MISSING_CHANNELS_SCOPE"
        result["diagnosis"] = "missing_channels_scope_on_token"
        return result
    if not has_channels:
        result["status"] = "SKIPPED_MISSING_CHANNELS_SCOPE"
        result["diagnosis"] = "missing_channels_scope_on_token"
        return result
    if get_status != 200:
        result["status"] = "BLOCKED_CHANNELS_GET"
        result["diagnosis"] = "channels_get_rejected_despite_scope"
        return result

    payload, flipped = enable_target_rate_plans(
        (get_body or {}).get("data") if isinstance(get_body, dict) else get_body
    )
    if not payload or flipped == 0:
        payload = constructed_booking_rate_payload()
        result["payload_source"] = "constructed_fully_flexible_weekly"
    else:
        result["payload_source"] = "get_settings_with_enabled_flags"
    result["flipped_flags"] = flipped
    result["write_attempted"] = True
    write_status, write_body = http_json(
        "POST", API + "/channels/settings", token, payload, raise_http=False
    )
    result["write_http"] = write_status
    result["write_summary"] = summarize_channel_body(write_body)
    if 200 <= write_status < 300:
        verify_status, verify_body = http_json("GET", settings_url, token, raise_http=False)
        result["verify_http"] = verify_status
        result["verify_summary"] = summarize_channel_body(verify_body)
        result["status"] = "OPENED" if verify_status == 200 else "WRITE_OK_VERIFY_FAILED"
        result["diagnosis"] = "ok"
        return result
    result["status"] = "WRITE_REJECTED"
    result["diagnosis"] = "channels_post_rejected"
    return result


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

    property_linkage = probe_property_hotel_linkage(token)
    fixed_prices = probe_fixed_prices(token)
    channel_rate_open = open_booking_channel_rate_plans(token, has_channels)
    print(
        f"hotel_linkage={property_linkage.get('classification')} "
        f"channel_rate_open={channel_rate_open.get('status')}",
        flush=True,
    )

    after_summary = summarize(after_data)
    evidence = {
        "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "property_id": PROPERTY_ID,
        "booking_hotel_id": BOOKING_HOTEL_ID,
        "hotel_linkage": property_linkage,
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
        "fixed_prices_probe": fixed_prices,
        "channel_settings_probe": {
            "http": channel_rate_open.get("get_http"),
            "error": channel_rate_open.get("get_error"),
            "has_channels_scope": has_channels,
            "diagnosis": channel_rate_open.get("diagnosis"),
            "scopes_needed": CHANNELS_SCOPES_NEEDED,
            "documented_invite_scopes": DOCUMENTED_INVITE_SCOPES,
            "invite_scope_doc": INVITE_UI_DOC,
        },
        "channel_rate_open": channel_rate_open,
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
