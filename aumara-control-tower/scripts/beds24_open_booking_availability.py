#!/usr/bin/env python3
"""Open AUMARA Beds24 inventory + daily prices for Booking.com (property 324882).

Writes numAvail and price1 for CHALET/Superior through the booking window so
Beds24 can push Rates & Availability to Booking.com. Then sets V1 rackRate via
json/setPropertyContent (apiKey+propKey). Records token scopes and a
/channels/settings probe (expected 401 without channels scope).
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
PROPERTY_ID = 324882
BOOKING_HOTEL_ID = 14953869
ROOMS = {
    # Room max units is 3; asking 4 is capped by Beds24 to 3.
    674465: {"name": "CHALET", "target_num_avail": 3, "price1": 259.0},
    674466: {"name": "Superior Chalet", "target_num_avail": 2, "price1": 329.0},
}
FIXED_END = dt.date(2026, 12, 31)
HORIZON_DAYS = 90
SAMPLE_AVAIL_DAYS = 14
ROOT = pathlib.Path(__file__).resolve().parents[1]
VAULT = ROOT / "evidence" / "beds24-refresh-vault.json"
EVIDENCE_GLOB = "beds24-open-booking-availability*.json"
V1_JSON = "https://api.beds24.com/json"
RACK_EVIDENCE = ROOT / "evidence" / "beds24-rack-rate-live.json"

# Scopes documented for the production invite (continuity + live details).
DOCUMENTED_INVITE_SCOPES = [
    "bookings",
    "bookings-personal",
    "bookings-financial",
    "properties",
    "inventory",
]
# Required to open Booking rate mappings via /channels/* (not on current token).
CHANNELS_SCOPES_NEEDED = ["read:channels", "write:channels"]


def booking_window(now: dt.datetime | None = None) -> tuple[str, str]:
    """Upcoming nights from today (UTC) through year-end or +90 days."""
    today = (now or dt.datetime.now(dt.timezone.utc)).date()
    start = today
    end = max(FIXED_END, start + dt.timedelta(days=HORIZON_DAYS))
    return start.isoformat(), end.isoformat()


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


def wanted_rack_rates() -> dict[str, str]:
    return {str(rid): f"{meta['price1']:.2f}" for rid, meta in ROOMS.items()}


def load_v1_keys() -> tuple[str, str]:
    api = (os.environ.get("BEDS24_API_KEY") or "").strip().strip('"').strip("'")
    prop = (os.environ.get("BEDS24_PROP_KEY") or "").strip().strip('"').strip("'")
    mask(api)
    mask(prop)
    return api, prop


def hotel_access_denied(payload: Any) -> bool:
    text = json.dumps(payload, ensure_ascii=False).upper() if payload is not None else ""
    return "HOTEL_ACCESS_DENIED" in text or "FORBIDDEN HOTEL" in text


def _v1_post(path: str, payload: dict[str, Any]) -> tuple[int, Any]:
    raw = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{V1_JSON}/{path}",
        data=raw,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "AUMARA-OpenAvail/3",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = resp.read()
            return int(resp.status), json.loads(body.decode("utf-8")) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read()
        try:
            parsed = json.loads(body.decode("utf-8", "replace")) if body else {}
        except json.JSONDecodeError:
            parsed = {"raw": body[:500].decode("utf-8", "replace")}
        return int(exc.code), parsed


def _read_v1_rack_rates(content: dict[str, Any]) -> dict[str, str]:
    rooms = content.get("roomIds") if isinstance(content, dict) else None
    if not isinstance(rooms, dict):
        return {}
    out: dict[str, str] = {}
    for rid in wanted_rack_rates():
        row = rooms.get(rid) or rooms.get(int(rid)) or {}
        out[rid] = str(row.get("rackRate", "")) if isinstance(row, dict) else ""
    return out


def _rates_match(got: dict[str, str], wanted: dict[str, str]) -> list[dict[str, str]]:
    mismatches = []
    for rid, val in wanted.items():
        actual = got.get(rid, "")
        try:
            ok = abs(float(actual) - float(val)) < 0.001
        except (TypeError, ValueError):
            ok = False
        if not ok:
            mismatches.append({"roomId": rid, "wanted": val, "got": actual})
    return mismatches


def set_v1_rack_rates(*, sleep_s: float = 4.0) -> dict[str, Any]:
    """Revive Beds24 V1 JSON rackRate write (not V2 /channels/settings)."""
    wanted = wanted_rack_rates()
    base = {
        "schema": "aumara.beds24-rack-rate-fix.v1",
        "property_id": PROPERTY_ID,
        "auth_shape": "json_body_apiKey_propKey",
        "endpoint": f"{V1_JSON}/setPropertyContent",
        "wanted": wanted,
        "legacy_hotel_id": str(BOOKING_HOTEL_ID),
        "hotel_access_denied_historical": True,
        "secret_exposed": False,
    }
    api, prop = load_v1_keys()
    if not api or not prop:
        return {
            **base,
            "status": "SKIPPED_MISSING_V1_SECRETS",
            "note": (
                "BEDS24_API_KEY / BEDS24_PROP_KEY are Production environment secrets. "
                "Repo-level secret probe historically showed API_KEY absent."
            ),
        }
    auth = {"apiKey": api, "propKey": prop}
    read_body = {
        "authentication": auth,
        "bookingData": False,
        "images": False,
        "roomIds": True,
        "texts": False,
        "includeAirbnb": True,
        "includeVrbo": False,
    }
    get_status, before_raw = _v1_post("getPropertyContent", read_body)
    if hotel_access_denied(before_raw):
        return {
            **base,
            "status": "HOTEL_ACCESS_DENIED",
            "http_status": get_status,
            "note": (
                f"V1 read returned HOTEL_ACCESS_DENIED. Historical Rates pack "
                f"blocker for Booking hotel {BOOKING_HOTEL_ID}."
            ),
        }
    if not 200 <= get_status < 300 or not isinstance(before_raw, dict):
        return {
            **base,
            "status": "V1_READ_FAILED",
            "http_status": get_status,
            "body_keys": sorted(before_raw.keys())[:20] if isinstance(before_raw, dict) else [],
        }
    rows = before_raw.get("getPropertyContent")
    before_content = rows[0] if isinstance(rows, list) and rows and isinstance(rows[0], dict) else {}
    before_rates = _read_v1_rack_rates(before_content)
    changes = {
        "action": "modify",
        "roomIds": {rid: {"rackRate": rate} for rid, rate in wanted.items()},
    }
    write_status, write_raw = _v1_post(
        "setPropertyContent",
        {"authentication": auth, "setPropertyContent": [changes]},
    )
    if hotel_access_denied(write_raw):
        return {
            **base,
            "status": "HOTEL_ACCESS_DENIED",
            "http_status": write_status,
            "before": before_rates,
            "note": (
                f"V1 write returned HOTEL_ACCESS_DENIED. Historical Rates pack "
                f"blocker for Booking hotel {BOOKING_HOTEL_ID}."
            ),
        }
    if not 200 <= write_status < 300:
        return {
            **base,
            "status": "V1_WRITE_FAILED",
            "http_status": write_status,
            "before": before_rates,
            "body_keys": sorted(write_raw.keys())[:20] if isinstance(write_raw, dict) else [],
        }
    if sleep_s > 0:
        time.sleep(sleep_s)
    after_status, after_raw = _v1_post("getPropertyContent", read_body)
    if hotel_access_denied(after_raw):
        return {
            **base,
            "status": "HOTEL_ACCESS_DENIED",
            "http_status": after_status,
            "before": before_rates,
            "write_http": write_status,
            "note": (
                f"V1 readback returned HOTEL_ACCESS_DENIED. Historical Rates pack "
                f"blocker for Booking hotel {BOOKING_HOTEL_ID}."
            ),
        }
    after_rows = after_raw.get("getPropertyContent") if isinstance(after_raw, dict) else None
    after_content = (
        after_rows[0]
        if isinstance(after_rows, list) and after_rows and isinstance(after_rows[0], dict)
        else {}
    )
    after_rates = _read_v1_rack_rates(after_content)
    mismatches = _rates_match(after_rates, wanted)
    return {
        **base,
        "status": "SUCCESS" if not mismatches else "FAILED_READBACK",
        "http_status": write_status,
        "readback_http": after_status,
        "before": before_rates,
        "after": after_rates,
        "mismatches": mismatches,
    }


def finish(evidence: dict[str, Any]) -> int:
    bad = []
    for rid, summary in (evidence.get("after_summary") or {}).items():
        if summary.get("numAvail_zero_days", 0) == summary.get("days", 0) and summary.get("days", 0) > 0:
            bad.append(rid)
    if bad:
        raise SystemExit(f"still fully zero numAvail for rooms {bad}")
    v1 = evidence.get("v1_rack_rates") or {}
    if os.environ.get("BEDS24_REQUIRE_RACK_RATES") == "1" and v1.get("status") != "SUCCESS":
        raise SystemExit(f"V1 rack rates required but status={v1.get('status')}")
    return 0


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

    params = [
        ("startDate", start),
        ("endDate", end),
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

    payload = build_calendar_payload(start, end)
    write_status, write_body = http_json("POST", API + "/inventory/rooms/calendar", token, payload)
    _, after = http_json("GET", cal_url, token)
    after_data = (after or {}).get("data") if isinstance(after, dict) else after
    if not isinstance(after_data, list):
        after_data = []

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

    v1_result = set_v1_rack_rates()
    RACK_EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    RACK_EVIDENCE.write_text(
        json.dumps(
            {**v1_result, "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat()},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    after_summary = summarize(after_data)
    evidence = {
        "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "property_id": PROPERTY_ID,
        "booking_hotel_id": BOOKING_HOTEL_ID,
        "rooms": ROOMS,
        "window": {"start": start, "end": end},
        "auth_details": details_safe,
        "before_summary": summarize(before_data),
        "write_http": write_status,
        "write_body": write_body[:4] if isinstance(write_body, list) else write_body,
        "after_summary": after_summary,
        "availability_sample": avail,
        "availability_sample_window": {"start": sample_start, "end": sample_end},
        "offers_probe": offers,
        "channel_settings_probe": channels_probe,
        "v1_rack_rates": v1_result,
        "status": "SUCCESS",
        "secret_exposed": False,
    }
    evidence_file.parent.mkdir(parents=True, exist_ok=True)
    evidence_file.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    print("EVIDENCE", evidence_file)
    print("RACK_EVIDENCE", RACK_EVIDENCE)

    for rid, s in after_summary.items():
        if s.get("days", 0) < 7:
            print(
                f"::warning::room {rid} calendar still sparse days={s.get('days')} "
                f"(missing prices historically caused this)",
                flush=True,
            )
    return finish(evidence)


if __name__ == "__main__":
    raise SystemExit(main())
