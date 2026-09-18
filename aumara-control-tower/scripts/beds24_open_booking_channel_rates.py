#!/usr/bin/env python3
"""Open Booking.com Fully flexible + Weekly rate plans for AUMARA (property 324882).

Fail-closed unless the exchanged token has read:channels and write:channels.
API-only: refresh credential exchange, then /channels/settings. No browser login.

One-shot path: store a channels-scoped refresh in BEDS24_REFRESH_CREDENTIAL,
then workflow_dispatch beds24-open-booking-channel-rates.
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
# V1 getPropertyContent bookingComPropertyCode — verified linked to prop 324882.
LINKED_BOOKING_HOTEL_ID = 14953869
# Continuity "working" hotel. Do not retarget unless live payloads show it
# linked to 324882 and 14953869 is absent.
CONTINUITY_WORKING_HOTEL_ID = 16137893
ROOMS = {
    674465: {"name": "CHALET", "booking_room_code": "1495386901"},
    674466: {"name": "Superior Chalet", "booking_room_code": "1495386902"},
}
BOOKING_RATE_CODE = "66887702"
BOOKING_CHANNEL_ALIASES = (
    "booking",
    "booking.com",
    "bookingcom",
    "booking_com",
    "booking-com",
)
DOCUMENTED_INVITE_SCOPES = [
    "bookings",
    "bookings-personal",
    "bookings-financial",
    "properties",
    "inventory",
    "read:channels",
    "write:channels",
]
CHANNELS_SCOPES_NEEDED = ["read:channels", "write:channels"]
ROOT = pathlib.Path(__file__).resolve().parents[1]
VAULT = ROOT / "evidence" / "beds24-refresh-vault.json"
EVIDENCE_GLOB = "beds24-open-booking-channel-rates*.json"
EXIT_MISSING_CHANNELS_SCOPE = 2
EXIT_CHANNELS_GET_FAILED = 3
EXIT_NO_MATCHING_RATE_PLANS = 4

NAME_KEYS = (
    "name",
    "title",
    "rateName",
    "ratePlanName",
    "planName",
    "label",
    "ratePlan",
    "rateplan",
)
CLOSED_FALSE_KEYS = {
    "closed",
    "isclosed",
    "bookingclosed",
    "closedonbooking",
    "ratesclosed",
    "disabled",
    "isdisabled",
}
OPEN_TRUE_KEYS = {
    "enabled",
    "open",
    "isopen",
    "available",
    "bookingenabled",
    "enablebooking",
    "enableinventory",
    "enableprice",
    "active",
}
HOTEL_ID_KEYS = {
    "bookingcompropertycode",
    "bookingpropertyid",
    "bookinghotelid",
    "hotelid",
    "hotel_id",
    "propertycode",
    "bookingcomhotelid",
    "bookingid",
}


def evidence_path(now: dt.datetime | None = None) -> pathlib.Path:
    stamp = (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y%m%d")
    return ROOT / "evidence" / f"beds24-open-booking-channel-rates-{stamp}.json"


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
    """Always exchange a refresh credential for a short-lived access token."""
    request = urllib.request.Request(
        API + "/authentication/token",
        headers={
            "Accept": "application/json",
            "refreshToken": refresh,
            "User-Agent": "AUMARA-OpenChannelRates/1",
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
    headers = {
        "Accept": "application/json",
        "token": token,
        "User-Agent": "AUMARA-OpenChannelRates/1",
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


def scope_set(details_safe: dict) -> set[str]:
    scopes = details_safe.get("scopes") or []
    if not isinstance(scopes, list):
        return set()
    return {str(s).lower().strip() for s in scopes}


def normalize_scope_set(scopes: set[str]) -> set[str]:
    out: set[str] = set()
    for raw in scopes:
        for part in str(raw).lower().replace(" ", "").split(","):
            if part:
                out.add(part)
    return out


def has_required_channel_scopes(scopes: set[str]) -> bool:
    """True when the token can read and write /channels/*."""
    normalized = normalize_scope_set(scopes)
    if "channels" in normalized:
        return True
    return "read:channels" in normalized and "write:channels" in normalized


def missing_channel_scopes(scopes: set[str]) -> list[str]:
    if has_required_channel_scopes(scopes):
        return []
    normalized = normalize_scope_set(scopes)
    missing = []
    if "read:channels" not in normalized and "channels" not in normalized:
        missing.append("read:channels")
    if "write:channels" not in normalized and "channels" not in normalized:
        missing.append("write:channels")
    return missing or list(CHANNELS_SCOPES_NEEDED)


def settings_data(body: Any) -> list:
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        data = body.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
    return []


def channel_name(obj: Any) -> str:
    if not isinstance(obj, dict):
        return ""
    raw = obj.get("channel") or obj.get("channelName") or obj.get("name") or ""
    return str(raw).strip().lower()


def is_booking_channel(name: str) -> bool:
    n = (name or "").replace(" ", "")
    return n in {a.replace(" ", "") for a in BOOKING_CHANNEL_ALIASES} or n.startswith(
        "booking"
    )


def collect_hotel_ids(obj: Any, found: set[str] | None = None) -> set[str]:
    if found is None:
        found = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            lk = str(key).lower()
            if lk in HOTEL_ID_KEYS or "hotel" in lk or "bookingcom" in lk:
                text = str(value).strip() if value not in (None, "", [], {}) else ""
                digits = "".join(ch for ch in text if ch.isdigit())
                if digits in {str(LINKED_BOOKING_HOTEL_ID), str(CONTINUITY_WORKING_HOTEL_ID)}:
                    found.add(digits)
                elif text in {str(LINKED_BOOKING_HOTEL_ID), str(CONTINUITY_WORKING_HOTEL_ID)}:
                    found.add(text)
            collect_hotel_ids(value, found)
    elif isinstance(obj, list):
        for item in obj:
            collect_hotel_ids(item, found)
    elif obj in (LINKED_BOOKING_HOTEL_ID, CONTINUITY_WORKING_HOTEL_ID, str(LINKED_BOOKING_HOTEL_ID), str(CONTINUITY_WORKING_HOTEL_ID)):
        found.add(str(obj))
    return found


def targeting_decision(found_ids: set[str]) -> dict[str, Any]:
    linked = str(LINKED_BOOKING_HOTEL_ID)
    working = str(CONTINUITY_WORKING_HOTEL_ID)
    has_linked = linked in found_ids
    has_working = working in found_ids
    if has_linked:
        target = LINKED_BOOKING_HOTEL_ID
        decision = "keep_v1_linked_14953869"
    elif has_working:
        target = CONTINUITY_WORKING_HOTEL_ID
        decision = "retarget_continuity_working_16137893_because_v1_hotel_absent"
    else:
        target = LINKED_BOOKING_HOTEL_ID
        decision = "default_v1_linked_14953869_not_seen_in_this_payload"
    return {
        "v1_content_linked_hotel": LINKED_BOOKING_HOTEL_ID,
        "continuity_working_hotel": CONTINUITY_WORKING_HOTEL_ID,
        "ids_found_on_property_or_channels": sorted(found_ids),
        "linked_hotel_present": has_linked,
        "continuity_working_hotel_present": has_working,
        "target_booking_hotel_id": target,
        "decision": decision,
        "do_not_retarget_without_live_link": True,
    }


def node_name(obj: dict) -> str:
    for key in NAME_KEYS:
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = node_name(value)
            if nested:
                return nested
    return ""


def classify_plan(obj: dict, name: str) -> str | None:
    n = name.lower()
    min_stay = obj.get("minStay") or obj.get("minNights") or obj.get("minimumStay")
    try:
        min_stay_n = int(min_stay)
    except (TypeError, ValueError):
        min_stay_n = None
    if any(marker in n for marker in ("weekly", "week-long", "7 night", "7-night", "semanal", "wkly")):
        return "weekly"
    if min_stay_n is not None and min_stay_n >= 7:
        return "weekly"
    if "non-refundable" in n or "non refundable" in n or "nonrefundable" in n:
        return None
    if any(marker in n for marker in ("fully flexible", "fully-flexible", "tarifa flexible")):
        return "fully_flexible"
    if "flexible" in n or n in {"flex", "standard", "std", "rate 1", "standard rate"}:
        return "fully_flexible"
    cancellation = str(
        obj.get("cancellation")
        or obj.get("cancellationPolicy")
        or obj.get("cancelPolicy")
        or ""
    ).lower()
    if "flex" in cancellation and "non" not in cancellation:
        return "fully_flexible"
    return None


def looks_like_rate_node(path: str, obj: dict) -> bool:
    path_l = path.lower()
    keys = {str(k).lower() for k in obj}
    if any(hint in path_l for hint in ("rateplan", "rate_plan", "rateplans", "rates")):
        return True
    if keys & {"rateid", "rateplanid", "rateplan", "ratecode", "bookingcomratecode"}:
        return True
    if "cancellation" in "".join(keys) or "minstay" in "".join(keys):
        return True
    return False


def iter_rate_nodes(obj: Any, path: str = "$"):
    if isinstance(obj, dict):
        name = node_name(obj)
        if name and looks_like_rate_node(path, obj):
            yield path, obj, name
        for key, value in obj.items():
            yield from iter_rate_nodes(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            yield from iter_rate_nodes(value, f"{path}[{index}]")


def is_plan_open(obj: dict) -> bool:
    for key, value in obj.items():
        lk = str(key).lower()
        if lk in CLOSED_FALSE_KEYS and value in (True, 1, "1", "true", "closed", "yes"):
            return False
        if lk in OPEN_TRUE_KEYS and value in (False, 0, "0", "false", "no", "closed"):
            return False
        if lk == "status" and str(value).lower() in {"closed", "inactive", "disabled", "off"}:
            return False
    return True


def open_rate_plan(obj: dict) -> list[str]:
    """Flip existing open/close flags in place. Never invent unknown fields."""
    changed: list[str] = []
    for key in list(obj.keys()):
        lk = str(key).lower()
        if lk in CLOSED_FALSE_KEYS and obj[key] not in (False, 0, "0", "false"):
            obj[key] = False if not isinstance(obj[key], int) else 0
            changed.append(key)
        elif lk in OPEN_TRUE_KEYS and obj[key] not in (True, 1, "1", "true"):
            obj[key] = True if not isinstance(obj[key], int) else 1
            changed.append(key)
        elif lk == "status" and str(obj[key]).lower() in {"closed", "inactive", "disabled", "off"}:
            obj[key] = "open"
            changed.append(key)
    return changed


def booking_channel_objects(settings: list) -> list[dict]:
    named = [
        obj
        for obj in settings
        if isinstance(obj, dict) and is_booking_channel(channel_name(obj))
    ]
    if named:
        return named
    return [obj for obj in settings if isinstance(obj, dict)]


def list_booking_rate_plans(settings: list) -> list[dict[str, Any]]:
    listed: list[dict[str, Any]] = []
    for channel_obj in booking_channel_objects(settings):
        cname = channel_name(channel_obj)
        for path, node, name in iter_rate_nodes(channel_obj):
            kind = classify_plan(node, name)
            listed.append(
                {
                    "channel": cname or "unknown",
                    "path": path,
                    "name": name,
                    "kind": kind,
                    "open": is_plan_open(node),
                    "room_id": node.get("id") or node.get("roomId") or node.get("room_id"),
                }
            )
    return listed


def open_target_plans(settings: list) -> dict[str, Any]:
    opened = []
    already = []
    skipped = []
    for channel_obj in booking_channel_objects(settings):
        for path, node, name in iter_rate_nodes(channel_obj):
            kind = classify_plan(node, name)
            if kind not in {"fully_flexible", "weekly"}:
                if kind is None:
                    skipped.append({"path": path, "name": name})
                continue
            if is_plan_open(node):
                already.append({"path": path, "name": name, "kind": kind})
                continue
            fields = open_rate_plan(node)
            opened.append({"path": path, "name": name, "kind": kind, "fields": fields})
    return {"opened": opened, "already_open": already, "skipped": skipped[:40]}


def dry_run_enabled() -> bool:
    return (os.environ.get("BEDS24_CHANNEL_RATES_DRY_RUN") or "").strip() in {
        "1",
        "true",
        "TRUE",
        "yes",
    }


def write_evidence(path: pathlib.Path, evidence: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("EVIDENCE", path, flush=True)


def fail_with_evidence(
    path: pathlib.Path, evidence: dict, message: str, code: int
) -> int:
    evidence["status"] = message
    write_evidence(path, evidence)
    print(json.dumps({k: evidence[k] for k in evidence if k != "settings_preview"}, ensure_ascii=False, indent=2))
    print(f"ERROR: {message}", file=sys.stderr)
    return code


def settings_preview(body: Any) -> Any:
    """Compact, non-secret channel/plan names only."""
    rows = []
    for channel_obj in settings_data(body)[:8]:
        if not isinstance(channel_obj, dict):
            continue
        rows.append(
            {
                "channel": channel_name(channel_obj) or None,
                "keys": sorted(str(k) for k in channel_obj.keys())[:20],
                "property_ids": [
                    p.get("id")
                    for p in (channel_obj.get("properties") or [])
                    if isinstance(p, dict)
                ][:8],
            }
        )
    return rows


def main() -> int:
    evidence_file = evidence_path()
    refresh = load_refresh()
    token = exchange_token(refresh)

    details_path = "/authentication/" + "details"
    details_status, details_body = http_json(
        "GET", API + details_path, token, raise_http=False
    )
    details_safe = sanitize_details(
        details_body if details_status == 200 else {"http": details_status, "body": details_body}
    )
    scopes = scope_set(details_safe)
    missing = missing_channel_scopes(scopes)
    print(
        f"token_scopes_count={len(scopes)} has_channels_scope={not missing} missing={missing}",
        flush=True,
    )

    prop_status, prop_body = http_json(
        "GET", API + f"/properties?id={PROPERTY_ID}", token, raise_http=False
    )
    channel_attempts: list[dict[str, Any]] = []
    settings_body: Any = None
    settings_http = None
    found_ids = collect_hotel_ids(prop_body)
    targeting = targeting_decision(found_ids)

    evidence: dict[str, Any] = {
        "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "property_id": PROPERTY_ID,
        "rooms": ROOMS,
        "booking_rate_code": BOOKING_RATE_CODE,
        "auth_details": details_safe,
        "properties_http": prop_status,
        "targeting": targeting,
        "scopes_needed": CHANNELS_SCOPES_NEEDED,
        "documented_invite_scopes": DOCUMENTED_INVITE_SCOPES,
        "invite_scope_doc": "aumara-control-tower/systems/beds24-continuity.md",
        "missing_channel_scopes": missing,
        "channel_get_attempts": channel_attempts,
        "secret_exposed": False,
    }

    if missing:
        print("MISSING_CHANNELS_SCOPE", ",".join(missing), flush=True)
        return fail_with_evidence(
            evidence_file,
            evidence,
            "MISSING_CHANNELS_SCOPE",
            EXIT_MISSING_CHANNELS_SCOPE,
        )

    query_sets = [
        [("propertyId", str(PROPERTY_ID))],
        [("propertyId", str(PROPERTY_ID)), ("channel", "booking")],
        [("propertyId", str(PROPERTY_ID)), ("channel", "booking.com")],
        [("propertyId", str(PROPERTY_ID)), ("channel", "bookingCom")],
    ]
    for rid in ROOMS:
        query_sets[0].append(("roomId", str(rid)))
    channels_path = "/channels/" + "settings"
    for params in query_sets:
        url = API + channels_path + "?" + urllib.parse.urlencode(params)
        status, body = http_json("GET", url, token, raise_http=False)
        attempt = {
            "http": status,
            "params": [(k, v) for k, v in params if k != "token"],
            "error": (body or {}).get("error") if isinstance(body, dict) else None,
            "rows": len(settings_data(body)),
        }
        channel_attempts.append(attempt)
        if status == 200 and settings_data(body):
            settings_http, settings_body = status, body
            break
        if settings_http is None and status == 200:
            settings_http, settings_body = status, body

    evidence["channel_get_attempts"] = channel_attempts
    evidence["settings_preview"] = settings_preview(settings_body)
    found_ids |= collect_hotel_ids(settings_body)
    evidence["targeting"] = targeting_decision(found_ids)

    if settings_http != 200:
        evidence["channels_get_http"] = settings_http
        evidence["channels_get_error"] = (
            (settings_body or {}).get("error") if isinstance(settings_body, dict) else None
        )
        return fail_with_evidence(
            evidence_file,
            evidence,
            "CHANNELS_GET_FAILED",
            EXIT_CHANNELS_GET_FAILED,
        )

    data = settings_data(settings_body)
    listed = list_booking_rate_plans(data)
    evidence["rate_plans"] = [
        {k: row[k] for k in ("channel", "name", "kind", "open", "room_id")} for row in listed
    ]
    mutation = open_target_plans(data)
    evidence["mutation"] = {
        "opened": mutation["opened"],
        "already_open": mutation["already_open"],
        "skipped_count": len(mutation["skipped"]),
    }

    target_found = [
        row
        for row in listed
        if row.get("kind") in {"fully_flexible", "weekly"}
    ]
    if not target_found:
        return fail_with_evidence(
            evidence_file,
            evidence,
            "NO_MATCHING_RATE_PLANS",
            EXIT_NO_MATCHING_RATE_PLANS,
        )

    if dry_run_enabled():
        evidence["status"] = "DRY_RUN"
        evidence["write_skipped"] = True
        write_evidence(evidence_file, evidence)
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
        return 0

    if mutation["opened"]:
        post_status, post_body = http_json(
            "POST", API + channels_path, token, data, raise_http=False
        )
        evidence["write_http"] = post_status
        evidence["write_error"] = (
            (post_body or {}).get("error") if isinstance(post_body, dict) else None
        )
        if not (200 <= int(post_status or 0) < 300):
            return fail_with_evidence(
                evidence_file,
                evidence,
                "CHANNELS_POST_FAILED",
                1,
            )
        rb_status, rb_body = http_json(
            "GET",
            API + channels_path + "?" + urllib.parse.urlencode([("propertyId", str(PROPERTY_ID))]),
            token,
            raise_http=False,
        )
        evidence["readback_http"] = rb_status
        evidence["readback_plans"] = [
            {k: row[k] for k in ("channel", "name", "kind", "open", "room_id")}
            for row in list_booking_rate_plans(settings_data(rb_body))
        ]
    else:
        evidence["write_http"] = None
        evidence["write_skipped"] = "already_open"

    evidence["status"] = "SUCCESS"
    write_evidence(evidence_file, evidence)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
