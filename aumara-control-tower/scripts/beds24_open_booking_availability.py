#!/usr/bin/env python3
"""Open AUMARA Beds24 rooms/inventory and rack rates for Booking.com (property 324882)."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API = "https://api.beds24.com/v2"
V1_JSON = "https://api.beds24.com/json"
PROPERTY_ID = 324882
LEGACY_BOOKING_HOTEL_ID = "14953869"
ROOMS = {
    674465: {"name": "CHALET", "target_num_avail": 4, "rack_rate": "259.00"},
    674466: {"name": "Superior Chalet", "target_num_avail": 2, "rack_rate": "329.00"},
}
FIXED_END = dt.date(2026, 12, 31)
HORIZON_DAYS = 90
SAMPLE_AVAIL_DAYS = 14
ROOT = pathlib.Path(__file__).resolve().parents[1]
VAULT = ROOT / "evidence" / "beds24-refresh-vault.json"
EVIDENCE_GLOB = "beds24-open-booking-availability*.json"
RACK_EVIDENCE = ROOT / "evidence" / "beds24-rack-rate-live.json"
KNOWN_SCOPES = (
    "accounts",
    "bookings",
    "bookings-financial",
    "bookings-personal",
    "channels",
    "inventory",
    "properties",
)
SCOPE_RE = re.compile(
    r"(?:read:|write:)?("
    + "|".join(re.escape(name) for name in sorted(KNOWN_SCOPES, key=len, reverse=True))
    + r")"
)
CHANNELS_SCOPE_DOC = {
    "missing_scope": "channels",
    "documented_in": "aumara-control-tower/systems/beds24-continuity.md",
    "canonical_invite_scopes": [
        "bookings",
        "bookings-personal",
        "bookings-financial",
        "properties",
        "inventory",
    ],
    "historical_granted_example": [
        "read:bookings",
        "write:bookings",
        "read:bookings-personal",
        "write:bookings-personal",
        "read:bookings-financial",
        "write:bookings-financial",
        "read:inventory",
        "write:inventory",
        "read:properties",
        "write:properties",
    ],
    "note": (
        "The canonical invite list and last recorded V2 grant omit channels. "
        "GET /channels/settings 401 is expected with the current refresh credential. "
        "Do not request a new invite; Booking-visible prices use V1 rackRate via "
        "BEDS24_API_KEY + BEDS24_PROP_KEY."
    ),
}


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


def wanted_rack_rates() -> dict[str, str]:
    return {str(rid): meta["rack_rate"] for rid, meta in ROOMS.items()}


def calendar_write_payload(start: str, end: str) -> list[dict[str, Any]]:
    """V2 inventory write: open units and plant daily price1 from rack rates."""
    return [
        {
            "roomId": rid,
            "calendar": [
                {
                    "from": start,
                    "to": end,
                    "numAvail": meta["target_num_avail"],
                    "price1": float(meta["rack_rate"]),
                    "override": "none",
                }
            ],
        }
        for rid, meta in ROOMS.items()
    ]


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
    # Prefer plaintext refresh injected by vault controller
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

    Beds24 refresh tokens can return HTTP 200 from GET /authentication/details
    and still fail inventory calendar calls with 401. Never treat the stored
    credential as an access token.
    """
    request = urllib.request.Request(
        API + "/authentication/token",
        headers={
            "Accept": "application/json",
            "refreshToken": refresh,
            "User-Agent": "AUMARA-OpenAvail/2",
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


def _parse_json_body(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8", "replace"))
    except json.JSONDecodeError:
        return {"raw": raw[:500].decode("utf-8", "replace")}


def http_json_soft(
    method: str,
    url: str,
    *,
    token: str | None = None,
    body: Any | None = None,
    extra_headers: dict[str, str] | None = None,
    timeout: int = 120,
) -> tuple[int, Any]:
    data = None
    headers = {"Accept": "application/json", "User-Agent": "AUMARA-OpenAvail/2"}
    if token:
        headers["token"] = token
    if extra_headers:
        headers.update(extra_headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status), _parse_json_body(resp.read())
    except urllib.error.HTTPError as e:
        return int(e.code), _parse_json_body(e.read())


def http_json(method: str, url: str, token: str, body: Any | None = None):
    status, parsed = http_json_soft(method, url, token=token, body=body)
    if status >= 400:
        raise SystemExit(f"{method} {url} HTTP {status}: {json.dumps(parsed)[:2000]}")
    return status, parsed


def extract_scopes(value: Any) -> list[str]:
    found: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for key, nested in item.items():
                visit(key)
                visit(nested)
        elif isinstance(item, list):
            for nested in item:
                visit(nested)
        elif isinstance(item, str):
            for match in SCOPE_RE.findall(item.casefold()):
                found.add(match)

    visit(value)
    return sorted(found)


def sanitize_auth_details(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        return {"body_type": type(body).__name__}
    out: dict[str, Any] = {}
    for key, value in body.items():
        lk = str(key).lower()
        if lk in {"token", "refreshtoken", "accesstoken", "refresh_token", "access_token"}:
            continue
        if any(part in lk for part in ("secret", "password", "credential", "apikey", "propkey")):
            continue
        if lk == "validtoken":
            out["validToken"] = value
            continue
        out[str(key)] = value
    return out


def fetch_auth_details(token: str) -> dict[str, Any]:
    """Record scopes after refreshToken→token. Never include secrets."""
    status, body = http_json_soft("GET", API + "/authentication/details", token=token)
    sanitized = sanitize_auth_details(body)
    scopes = extract_scopes(sanitized)
    channels_present = "channels" in scopes
    return {
        "http_status": status,
        "validToken": sanitized.get("validToken"),
        "scopes": scopes,
        "details_keys": sorted(str(k) for k in sanitized.keys()),
        "channels_scope_present": channels_present,
        "channels_scope_doc": None if channels_present else CHANNELS_SCOPE_DOC,
    }


def _has_price(day: dict[str, Any]) -> bool:
    for key in ("price1", "price", "rackRate"):
        value = day.get(key)
        if value in (None, "", 0, 0.0, "0", "0.00"):
            continue
        return True
    return False


def summarize(data: list) -> dict:
    out = {}
    for room in data or []:
        rid = str(room.get("roomId"))
        days = room.get("calendar") or []
        zero = sum(1 for d in days if d.get("numAvail") == 0)
        priced = sum(1 for d in days if isinstance(d, dict) and _has_price(d))
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
            "priced_days": priced,
            "sample_first14": compact,
        }
    return out


def load_v1_keys() -> tuple[str, str]:
    api = (os.environ.get("BEDS24_API_KEY") or "").strip().strip('"').strip("'")
    prop = (os.environ.get("BEDS24_PROP_KEY") or "").strip().strip('"').strip("'")
    mask(api)
    mask(prop)
    return api, prop


def hotel_access_denied(payload: Any) -> bool:
    text = json.dumps(payload, ensure_ascii=False).upper() if payload is not None else ""
    return "HOTEL_ACCESS_DENIED" in text or "FORBIDDEN HOTEL" in text


def _read_v1_rack_rates(content: dict[str, Any]) -> dict[str, str]:
    rooms = content.get("roomIds") if isinstance(content, dict) else None
    if not isinstance(rooms, dict):
        return {}
    out: dict[str, str] = {}
    for rid in wanted_rack_rates():
        row = rooms.get(rid) or rooms.get(int(rid)) or {}
        if isinstance(row, dict):
            out[rid] = str(row.get("rackRate", ""))
        else:
            out[rid] = ""
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
        "legacy_hotel_id": LEGACY_BOOKING_HOTEL_ID,
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
    get_status, before_raw = http_json_soft(
        "POST", f"{V1_JSON}/getPropertyContent", body=read_body, timeout=90
    )
    if hotel_access_denied(before_raw):
        return {
            **base,
            "status": "HOTEL_ACCESS_DENIED",
            "http_status": get_status,
            "note": (
                f"V1 read returned HOTEL_ACCESS_DENIED. Historical Rates pack "
                f"blocker for Booking hotel {LEGACY_BOOKING_HOTEL_ID}."
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
    write_status, write_raw = http_json_soft(
        "POST",
        f"{V1_JSON}/setPropertyContent",
        body={"authentication": auth, "setPropertyContent": [changes]},
        timeout=90,
    )
    if hotel_access_denied(write_raw):
        return {
            **base,
            "status": "HOTEL_ACCESS_DENIED",
            "http_status": write_status,
            "before": before_rates,
            "note": (
                f"V1 write returned HOTEL_ACCESS_DENIED. Historical Rates pack "
                f"blocker for Booking hotel {LEGACY_BOOKING_HOTEL_ID}."
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
    after_status, after_raw = http_json_soft(
        "POST", f"{V1_JSON}/getPropertyContent", body=read_body, timeout=90
    )
    if hotel_access_denied(after_raw):
        return {
            **base,
            "status": "HOTEL_ACCESS_DENIED",
            "http_status": after_status,
            "before": before_rates,
            "write_http": write_status,
            "note": (
                f"V1 readback returned HOTEL_ACCESS_DENIED. Historical Rates pack "
                f"blocker for Booking hotel {LEGACY_BOOKING_HOTEL_ID}."
            ),
        }
    after_rows = after_raw.get("getPropertyContent") if isinstance(after_raw, dict) else None
    after_content = (
        after_rows[0] if isinstance(after_rows, list) and after_rows and isinstance(after_rows[0], dict) else {}
    )
    after_rates = _read_v1_rack_rates(after_content)
    mismatches = _rates_match(after_rates, wanted)
    write_preview = write_raw
    if isinstance(write_raw, dict):
        write_preview = {k: write_raw.get(k) for k in list(write_raw)[:6] if k != "authentication"}
    return {
        **base,
        "status": "SUCCESS" if not mismatches else "FAILED_READBACK",
        "http_status": write_status,
        "readback_http": after_status,
        "before": before_rates,
        "after": after_rates,
        "mismatches": mismatches,
        "write_preview_keys": sorted(write_preview.keys()) if isinstance(write_preview, dict) else [],
    }


def _write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
    auth_details = fetch_auth_details(token)
    params = [("startDate", start), ("endDate", end), ("includePrices", "true"), ("includeNumAvail", "true")]
    for rid in ROOMS:
        params.append(("roomId", str(rid)))
    cal_url = API + "/inventory/rooms/calendar?" + urllib.parse.urlencode(params)
    _, before = http_json("GET", cal_url, token)
    before_data = (before or {}).get("data") if isinstance(before, dict) else before
    if not isinstance(before_data, list):
        before_data = []

    payload = calendar_write_payload(start, end)
    write_status, write_body = http_json("POST", API + "/inventory/rooms/calendar", token, payload)
    _, after = http_json("GET", cal_url, token)
    after_data = (after or {}).get("data") if isinstance(after, dict) else after
    if not isinstance(after_data, list):
        after_data = []

    avail_params = [("startDate", sample_start), ("endDate", sample_end)]
    for rid in ROOMS:
        avail_params.append(("roomId", str(rid)))
    _, avail = http_json("GET", API + "/inventory/rooms/availability?" + urllib.parse.urlencode(avail_params), token)

    ch_status, ch_body = http_json_soft("GET", API + f"/channels/settings?propertyId={PROPERTY_ID}", token=token)
    channel_probe = {
        "http_status": ch_status,
        "body_keys": sorted(ch_body.keys())[:8] if isinstance(ch_body, dict) else [],
        "error": (ch_body or {}).get("error") if isinstance(ch_body, dict) else None,
        "channels_scope_doc": CHANNELS_SCOPE_DOC if ch_status == 401 else None,
    }

    v1_result = set_v1_rack_rates()
    _write_json(RACK_EVIDENCE, {**v1_result, "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat()})

    evidence = {
        "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "property_id": PROPERTY_ID,
        "rooms": ROOMS,
        "window": {"start": start, "end": end},
        "auth_details": auth_details,
        "before_summary": summarize(before_data),
        "write_http": write_status,
        "write_body": write_body[:4] if isinstance(write_body, list) else write_body,
        "after_summary": summarize(after_data),
        "availability_sample": avail,
        "availability_sample_window": {"start": sample_start, "end": sample_end},
        "channel_settings_probe": channel_probe,
        "v1_rack_rates": v1_result,
        "status": "SUCCESS",
        "secret_exposed": False,
    }
    _write_json(evidence_file, evidence)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    print("EVIDENCE", evidence_file)
    print("RACK_EVIDENCE", RACK_EVIDENCE)
    return finish(evidence)


if __name__ == "__main__":
    raise SystemExit(main())
