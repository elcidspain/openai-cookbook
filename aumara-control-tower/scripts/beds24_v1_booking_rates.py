#!/usr/bin/env python3
"""V1 JSON path to open Booking.com Fully flexible + Weekly for AUMARA.

Uses Production secrets BEDS24_API_KEY + BEDS24_PROP_KEY against
https://api.beds24.com/json/. Never prints secrets. Never uses passwords.

V1 can enable Booking inventory/price export, list/modify Beds24 rates
(setRates), map daily-price rows (setDailyPriceSetup), and send p1/p2+inventory
(setRoomDates). It cannot call Booking.com "Get Codes"; a Weekly plan with no
Beds24 bookingcomRateCode still needs V2 /channels/settings or a channels-scoped
invite.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Callable

V1_JSON = "https://api.beds24.com/json"
PROPERTY_ID = 324882
LINKED_BOOKING_HOTEL_ID = 14953869
DEFAULT_BOOKING_RATE_CODE = "66887702"
ROOMS = {
    674465: {
        "name": "CHALET",
        "booking_room_code": "1495386901",
        "price": "259.00",
        "inventory": "3",
    },
    674466: {
        "name": "Superior Chalet",
        "booking_room_code": "1495386902",
        "price": "329.00",
        "inventory": "2",
    },
}
V1_CALL_GAP_SEC = 2.0
ROOMDATES_DAYS = 120
RATE_END = dt.date(2028, 12, 31)

# Documented after live mobile reports that pagetype=apiv2 can land on V1 keys.
MOBILE_INVITE_NAV = {
    "do_not_paste_api_keys": True,
    "wrong_page": {
        "signals": [
            "API Key 1",
            "API Key 2",
            "propKey",
            "Prop Key",
            "SETTINGS > ACCOUNT > ACCOUNT ACCESS",
        ],
        "urls_that_may_redirect_mobile_to_v1_keys": [
            "https://beds24.com/control3.php?pagetype=apiv2",
        ],
        "instruction": "If you see API Key 1/2, you are on the V1 key page. Do not copy or paste keys. Go back.",
    },
    "right_page": {
        "menu": "SETTINGS > MARKETPLACE > API",
        "must_see": "Generate invite code",
        "must_not_see": "API Key 1 / API Key 2",
        "scopes": [
            "bookings",
            "bookings-personal",
            "bookings-financial",
            "properties",
            "inventory",
            "channels (READ and WRITE / read:channels + write:channels)",
        ],
        "urls_to_try_in_order": [
            "https://beds24.com/control3.php?pagetype=apiv2",
            "https://beds24.com/control2.php?pagetype=apiv2",
        ],
        "mobile_steps": [
            "Open Beds24 in the phone browser (not the API Key 1/2 screen).",
            "Request Desktop site if the page shows API Key 1 or API Key 2.",
            "Open the menu and tap SETTINGS.",
            "Open MARKETPLACE (not ACCOUNT ACCESS, not API keys).",
            "Tap API.",
            "Confirm the heading is Marketplace API / invite codes, then tap Generate invite code.",
            "Enable READ+WRITE for bookings, bookings-personal, bookings-financial, properties, inventory, and channels.",
            "Generate the invite. Send only the invite code to CoS. Never send API keys or passwords.",
        ],
    },
}

ENABLE_TRUE_KEYS = {
    "roompriceenable",
    "1ppriceenable",
    "2ppriceenable",
    "3ppriceenable",
    "allowbooking",
    "enabled",
    "enable",
    "bookingcomenable",
    "bookingcomenableinventory",
    "bookingcomenableprice",
    "bookingcomenablebooking",
}
CLOSED_FALSE_KEYS = {
    "closed",
    "isclosed",
    "disabled",
    "isdisabled",
}


Classify = Callable[[dict, str], str | None]


def mask(value: str) -> None:
    if value:
        print(f"::add-mask::{value}", flush=True)


def v1_credentials() -> tuple[str, str]:
    api = (os.environ.get("BEDS24_API_KEY") or "").strip().strip('"').strip("'")
    prop = (os.environ.get("BEDS24_PROP_KEY") or "").strip().strip('"').strip("'")
    mask(api)
    mask(prop)
    return api, prop


def _as_list(payload: Any, *keys: str) -> list:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
        if isinstance(value, dict):
            nested = _as_list(value, *keys)
            if nested:
                return nested
            return [value]
    return []


def redact(obj: Any, secrets: tuple[str, ...], depth: int = 0) -> Any:
    if depth > 8:
        return "[DEPTH]"
    if isinstance(obj, dict):
        out = {}
        for key, value in obj.items():
            lk = str(key).lower()
            if any(
                token in lk
                for token in (
                    "apikey",
                    "api_key",
                    "propkey",
                    "prop_key",
                    "password",
                    "token",
                    "secret",
                    "credential",
                    "refreshtoken",
                )
            ):
                out[str(key)] = "[REDACTED]"
            elif lk in {"icalexporturl", "url"} and isinstance(value, str) and "token=" in value.lower():
                out[str(key)] = "[REDACTED_URL]"
            else:
                out[str(key)] = redact(value, secrets, depth + 1)
        return out
    if isinstance(obj, list):
        return [redact(item, secrets, depth + 1) for item in obj[:80]]
    if isinstance(obj, str):
        text = obj
        for secret in secrets:
            if secret and secret in text:
                text = text.replace(secret, "[REDACTED]")
        if len(text) > 500:
            return text[:500]
        return text
    return obj


def v1_post(
    path: str,
    payload: dict,
    *,
    sleep_s: float = V1_CALL_GAP_SEC,
    opener: Callable[..., Any] | None = None,
) -> tuple[int, Any]:
    if sleep_s:
        time.sleep(sleep_s)
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{V1_JSON}/{path}",
        data=raw,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "AUMARA-OpenChannelRates-V1/1",
        },
        method="POST",
    )
    urlopen = opener or urllib.request.urlopen
    try:
        with urlopen(req, timeout=90) as resp:
            body = resp.read()
            status = int(resp.status)
    except urllib.error.HTTPError as exc:
        body = exc.read()
        status = int(exc.code)
    try:
        parsed = json.loads(body.decode("utf-8", "replace")) if body else {}
    except Exception:
        parsed = {"non_json_bytes": len(body or b"")}
    return status, parsed


def property_rooms(payload: Any) -> list[dict]:
    props = _as_list(payload, "getProperty", "property")
    rooms: list[dict] = []
    for prop in props or ([payload] if isinstance(payload, dict) else []):
        if not isinstance(prop, dict):
            continue
        for row in _as_list(prop, "roomTypes", "rooms", "roomIds"):
            rooms.append(row)
        room_ids = prop.get("roomIds")
        if isinstance(room_ids, dict):
            for rid, row in room_ids.items():
                if isinstance(row, dict):
                    rooms.append({"roomId": str(rid), **row})
    return rooms


def rate_rows(payload: Any) -> list[dict]:
    return _as_list(payload, "getRates", "setRates", "rates")


def daily_price_rows(payload: Any) -> list[dict]:
    rows = _as_list(payload, "getDailyPriceSetup", "setDailyPriceSetup", "dailyPrices")
    if rows:
        expanded: list[dict] = []
        for row in rows:
            nested = row.get("dailyPrices")
            if isinstance(nested, list):
                expanded.extend(item for item in nested if isinstance(item, dict))
            else:
                expanded.append(row)
        return expanded
    if isinstance(payload, dict) and isinstance(payload.get("dailyPrices"), list):
        return [row for row in payload["dailyPrices"] if isinstance(row, dict)]
    return []


def intish(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def summarize_room(row: dict) -> dict[str, Any]:
    rid = intish(row.get("roomId") or row.get("id"))
    return {
        "roomId": rid,
        "name": row.get("name"),
        "bookingComEnableInventory": intish(row.get("bookingComEnableInventory")),
        "bookingComEnableBooking": intish(row.get("bookingComEnableBooking")),
        "bookingComRateCode": str(row.get("bookingComRateCode") or "").strip() or None,
        "bookingComRoomCode": str(row.get("bookingComRoomCode") or "").strip() or None,
        "dailyPriceCount": intish(row.get("dailyPriceCount")),
        "minStay": intish(row.get("minStay") or row.get("minNights")),
        "keys": sorted(str(k) for k in row.keys())[:40],
    }


def summarize_rate(row: dict, classify: Classify) -> dict[str, Any]:
    name = str(row.get("name") or row.get("rateName") or "").strip()
    return {
        "rateId": row.get("rateId") or row.get("id"),
        "roomId": intish(row.get("roomId")),
        "name": name or None,
        "kind": classify(row, name),
        "bookingcomRateCode": str(
            row.get("bookingcomRateCode") or row.get("bookingComRateCode") or ""
        ).strip()
        or None,
        "minNights": intish(row.get("minNights") or row.get("minStay")),
        "firstNight": row.get("firstNight"),
        "lastNight": row.get("lastNight"),
        "roomPriceEnable": row.get("roomPriceEnable"),
        "allowBooking": row.get("allowBooking") or row.get("allowbooking"),
        "keys": sorted(str(k) for k in row.keys())[:40],
    }


def summarize_daily(row: dict, classify: Classify) -> dict[str, Any]:
    name = str(row.get("name") or "").strip()
    enable_fields = {
        key: row.get(key)
        for key in row
        if "enable" in str(key).lower() or "bookingcom" in str(key).lower()
    }
    return {
        "dailyPriceNumber": intish(row.get("dailyPriceNumber") or row.get("offerId")),
        "name": name or None,
        "kind": classify(row, name),
        "minStay": intish(row.get("minStay") or row.get("minNights")),
        "bookingcomRateCode": str(
            row.get("bookingcomRateCode") or row.get("bookingComRateCode") or ""
        ).strip()
        or None,
        "enable_fields": enable_fields,
        "keys": sorted(str(k) for k in row.keys())[:40],
    }


def enable_flags(row: dict) -> list[str]:
    changed: list[str] = []
    for key in list(row.keys()):
        lk = str(key).lower()
        if lk in CLOSED_FALSE_KEYS and row[key] not in (False, 0, "0", "false"):
            row[key] = 0 if isinstance(row[key], (int, str)) and str(row[key]).isdigit() else False
            changed.append(key)
        elif lk in ENABLE_TRUE_KEYS and row[key] in (False, 0, "0", "false", "", None):
            row[key] = 1 if not isinstance(row[key], bool) else True
            changed.append(key)
    return changed


def nightly_dates(days: int, *, today: dt.date | None = None) -> dict[str, dict[str, str]]:
    start = today or dt.datetime.now(dt.timezone.utc).date()
    out: dict[str, dict[str, str]] = {}
    for offset in range(max(1, days)):
        day = start + dt.timedelta(days=offset)
        out[day.strftime("%Y%m%d")] = {}
    return out


def roomdates_payload(room_id: int, *, include_p2: bool, today: dt.date | None = None) -> dict:
    spec = ROOMS[room_id]
    dates = nightly_dates(ROOMDATES_DAYS, today=today)
    for slot in dates.values():
        slot["p1"] = spec["price"]
        slot["i"] = spec["inventory"]
        if include_p2:
            slot["p2"] = spec["price"]
    return {"roomId": str(room_id), "dates": dates}


def v1_error_code(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key in ("error", "errorCode", "errorcode"):
            if payload.get(key) not in (None, ""):
                return str(payload.get(key))
        if payload.get("success") is False:
            return "success=false"
    return None


def run_v1(
    *,
    classify: Classify,
    now: dt.datetime | None = None,
    opener: Callable[..., Any] | None = None,
    sleep_s: float = 0.0,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Probe V1, then enable Booking export / rates / daily prices / room dates."""
    api, prop = v1_credentials()
    secrets = tuple(s for s in (api, prop) if s)
    today = (now or dt.datetime.now(dt.timezone.utc)).date()
    result: dict[str, Any] = {
        "api": "v1_json",
        "host": V1_JSON,
        "property_id": PROPERTY_ID,
        "hotel_id": LINKED_BOOKING_HOTEL_ID,
        "methods_tried": [],
        "writes": [],
        "mobile_invite_nav": MOBILE_INVITE_NAV,
        "secret_exposed": False,
    }
    if not api or not prop:
        result["status"] = "V1_KEYS_ABSENT"
        result["note"] = (
            "Production secrets BEDS24_API_KEY + BEDS24_PROP_KEY were not present. "
            "Ilia must not paste V1 API keys. Workflow should load them from Production."
        )
        return result

    auth = {"apiKey": api, "propKey": prop}

    def call(path: str, extra: dict | None = None) -> tuple[int, Any]:
        payload = {"authentication": auth, **(extra or {})}
        status, body = v1_post(path, payload, sleep_s=sleep_s, opener=opener)
        result["methods_tried"].append(
            {
                "path": path,
                "http": status,
                "error": v1_error_code(body),
                "top_keys": sorted(body.keys())[:20] if isinstance(body, dict) else type(body).__name__,
            }
        )
        return status, redact(body, secrets)

    def call_raw(path: str, extra: dict | None = None) -> tuple[int, Any]:
        payload = {"authentication": auth, **(extra or {})}
        status, body = v1_post(path, payload, sleep_s=sleep_s, opener=opener)
        result["methods_tried"].append(
            {
                "path": path,
                "http": status,
                "error": v1_error_code(body),
                "top_keys": sorted(body.keys())[:20] if isinstance(body, dict) else type(body).__name__,
            }
        )
        return status, body

    prop_http, prop_body = call("getProperty", {"includeRooms": True, "includeRoomUnits": False})
    rates_http, rates_body = call("getRates")
    daily_by_room: dict[int, Any] = {}
    for rid in ROOMS:
        _http, daily_body = call("getDailyPriceSetup", {"roomId": str(rid)})
        daily_by_room[rid] = daily_body

    token_http, token_raw = call_raw("getV2RefreshToken")
    minted_refresh = None
    if isinstance(token_raw, dict):
        for key in ("refreshToken", "refreshtoken", "refresh_token", "token"):
            raw = token_raw.get(key)
            if isinstance(raw, str) and raw.strip() and key != "token":
                minted_refresh = raw.strip()
                mask(minted_refresh)
                break
            if key == "token" and isinstance(raw, str) and raw.strip() and "refresh" in json.dumps(token_raw).lower():
                pass
        if not minted_refresh:
            nested = token_raw.get("getV2RefreshToken")
            if isinstance(nested, dict):
                for key in ("refreshToken", "refreshtoken", "refresh_token"):
                    raw = nested.get(key)
                    if isinstance(raw, str) and raw.strip():
                        minted_refresh = raw.strip()
                        mask(minted_refresh)
                        break
    result["getV2RefreshToken"] = {
        "http": token_http,
        "present": bool(minted_refresh),
        "error": v1_error_code(token_raw) if isinstance(token_raw, dict) else None,
        "note": (
            "In-memory only; never stored. If this mint includes channels, V2 "
            "/channels/settings can run without a new invite."
        ),
    }

    rooms = [summarize_room(row) for row in property_rooms(prop_body)]
    rates = [summarize_rate(row, classify) for row in rate_rows(rates_body)]
    daily = {
        str(rid): [summarize_daily(row, classify) for row in daily_price_rows(body)]
        for rid, body in daily_by_room.items()
    }
    result["probe"] = {
        "getProperty_http": prop_http,
        "getRates_http": rates_http,
        "rooms": [row for row in rooms if row.get("roomId") in ROOMS],
        "rates": rates,
        "daily_prices": daily,
        "kinds_seen": sorted({row.get("kind") for row in rates if row.get("kind")}),
    }
    if prop_http >= 400 or (isinstance(prop_body, dict) and v1_error_code(prop_body)):
        result["status"] = "V1_GETPROPERTY_FAILED"
        return result
    if rates_http >= 400:
        result["status"] = "V1_GETRATES_FAILED"
        return result

    writes: list[dict[str, Any]] = []
    kinds_by_room: dict[int, set[str]] = {rid: set() for rid in ROOMS}
    for row in rates:
        rid = row.get("roomId")
        if rid in kinds_by_room and row.get("kind"):
            kinds_by_room[rid].add(str(row["kind"]))

    def record_write(path: str, status: int, body: Any, reason: str) -> None:
        writes.append(
            {
                "path": path,
                "http": status,
                "error": v1_error_code(body) if isinstance(body, dict) else None,
                "reason": reason,
            }
        )

    if dry_run:
        result["status"] = "V1_DRY_RUN"
        result["writes"] = writes
        result["minted_v2_refresh_in_memory"] = bool(minted_refresh)
        return result

    # Enable Booking inventory+price export per room if it is off.
    room_mods = []
    for row in rooms:
        rid = row.get("roomId")
        if rid not in ROOMS:
            continue
        change: dict[str, Any] = {"action": "modify", "roomId": str(rid)}
        needed = False
        if row.get("bookingComEnableInventory") != 1:
            change["bookingComEnableInventory"] = 1
            needed = True
        if row.get("bookingComEnableBooking") != 1:
            change["bookingComEnableBooking"] = 1
            needed = True
        if needed:
            room_mods.append(change)
    if room_mods:
        status, body = call(
            "setProperty",
            {"setProperty": [{"action": "modify", "roomTypes": room_mods}]},
        )
        record_write("setProperty", status, body, "enable bookingCom inventory/booking")

    # Re-enable existing Fully flexible / Weekly rates; create Weekly only when
    # that room has no weekly rate at all.
    rate_mods: list[dict[str, Any]] = []
    original_rates = rate_rows(rates_body)
    for raw in original_rates:
        summary = summarize_rate(raw, classify)
        if summary.get("kind") not in {"fully_flexible", "weekly"}:
            continue
        if summary.get("roomId") not in ROOMS:
            continue
        candidate = dict(raw)
        fields = enable_flags(candidate)
        last = str(candidate.get("lastNight") or "")
        if last and last < today.isoformat():
            candidate["lastNight"] = RATE_END.isoformat()
            fields.append("lastNight")
        if not fields:
            continue
        patch = {
            "action": "modify",
            "rateId": str(candidate.get("rateId") or candidate.get("id")),
            "roomId": str(candidate.get("roomId")),
        }
        for key in fields:
            if key in candidate:
                patch[key] = candidate[key]
        if "lastNight" in fields:
            patch["lastNight"] = RATE_END.isoformat()
        rate_mods.append(patch)

    for rid, spec in ROOMS.items():
        if "weekly" not in kinds_by_room[rid]:
            rate_mods.append(
                {
                    "action": "new",
                    "roomId": str(rid),
                    "name": "Weekly",
                    "firstNight": today.isoformat(),
                    "lastNight": RATE_END.isoformat(),
                    # Was "7" — blocked 1–2 night bookings on beds24.com ("7 Noches").
                    # Short stays are required; keep Weekly as a named plan with minNights=1.
                    "minNights": "1",
                    "maxNights": "30",
                    "roomPrice": spec["price"],
                    "roomPriceEnable": "1",
                    # Empty rate code uses the channel-manager mapping / offer order.
                    # We never invent a Booking.com rate id.
                    "bookingcomRateCode": "",
                }
            )
            kinds_by_room[rid].add("weekly")
        if "fully_flexible" not in kinds_by_room[rid]:
            mapped = next(
                (
                    row.get("bookingComRateCode")
                    for row in rooms
                    if row.get("roomId") == rid and row.get("bookingComRateCode")
                ),
                DEFAULT_BOOKING_RATE_CODE,
            )
            rate_mods.append(
                {
                    "action": "new",
                    "roomId": str(rid),
                    "name": "Fully flexible",
                    "firstNight": today.isoformat(),
                    "lastNight": RATE_END.isoformat(),
                    "minNights": "1",
                    "maxNights": "30",
                    "roomPrice": spec["price"],
                    "roomPriceEnable": "1",
                    "bookingcomRateCode": str(mapped),
                }
            )
            kinds_by_room[rid].add("fully_flexible")

    if rate_mods:
        status, body = call("setRates", {"setRates": rate_mods})
        record_write("setRates", status, body, "enable/create Fully flexible + Weekly rates")

    # Daily price rows: turn on any Booking enable flags already present.
    for rid, body in daily_by_room.items():
        patches = []
        for raw in daily_price_rows(body):
            candidate = dict(raw)
            fields = enable_flags(candidate)
            number = candidate.get("dailyPriceNumber") or candidate.get("offerId")
            if not number:
                continue
            if not fields:
                continue
            patch = {"dailyPriceNumber": str(number)}
            for key in fields:
                patch[key] = candidate[key]
            patches.append(patch)
        if patches:
            status, resp = call(
                "setDailyPriceSetup",
                {
                    "setDailyPriceSetup": [
                        {"action": "modify", "roomId": str(rid), "dailyPrices": patches}
                    ]
                },
            )
            record_write("setDailyPriceSetup", status, resp, f"enable Booking on daily prices room {rid}")

    include_p2 = False
    for row in rooms:
        rid = row.get("roomId")
        if rid not in ROOMS:
            continue
        if (row.get("dailyPriceCount") or 0) >= 2 or len(daily.get(str(rid), [])) >= 2:
            include_p2 = True
            break
    for rid in ROOMS:
        payload = roomdates_payload(rid, include_p2=include_p2, today=today)
        status, resp = call("setRoomDates", payload)
        record_write(
            "setRoomDates",
            status,
            resp,
            f"send p1{' + p2' if include_p2 else ''} + inventory for room {rid}",
        )

    _, rates_after = call("getRates")
    after = [summarize_rate(row, classify) for row in rate_rows(rates_after)]
    kinds_after = {row.get("kind") for row in after if row.get("kind")}
    result["writes"] = writes
    result["rates_after"] = [
        {k: row[k] for k in ("rateId", "roomId", "name", "kind", "bookingcomRateCode", "minNights")}
        for row in after
        if row.get("roomId") in ROOMS
    ]
    result["kinds_after"] = sorted(k for k in kinds_after if k)
    result["minted_v2_refresh_in_memory"] = bool(minted_refresh)
    if minted_refresh:
        result["minted_v2_refresh"] = minted_refresh  # caller must mask and drop before evidence

    has_flex = "fully_flexible" in kinds_after or any(
        row.get("kind") == "fully_flexible" for row in rates
    )
    has_weekly = "weekly" in kinds_after
    write_errors = [w for w in writes if w.get("error") or int(w.get("http") or 0) >= 400]
    if has_flex and has_weekly and not write_errors:
        result["status"] = "SUCCESS"
        result["opens"] = ["fully_flexible", "weekly"]
        result["limitation"] = (
            "V1 opened/created Beds24 rates and sent prices. Booking.com Weekly only "
            "syncs as a distinct extranet plan if a bookingcomRateCode was already mapped "
            "or offer-order mapping hits the Weekly plan."
        )
    elif has_flex and not write_errors:
        result["status"] = "PARTIAL"
        result["opens"] = ["fully_flexible"]
        result["missing"] = ["weekly_booking_rate_id"]
        result["limitation"] = (
            "V1 can price the mapped default rate "
            f"{DEFAULT_BOOKING_RATE_CODE} (likely Fully flexible) via setRates/"
            "setRoomDates. Distinct Booking.com Weekly still needs Get Codes or "
            "V2 /channels/settings."
        )
    else:
        result["status"] = "V1_WRITE_INCOMPLETE"
        result["write_errors"] = write_errors
    return result
