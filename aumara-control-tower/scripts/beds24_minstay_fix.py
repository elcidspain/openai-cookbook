#!/usr/bin/env python3
"""Fix AUMARA Beds24 minimum stay to 1 night (property 324882).

Sets calendar minStay=1 for rooms 674465 (CHALET) and 674466 (Superior Chalet)
across 2026-09-13 .. 2026-12-31. Does NOT change prices or numAvail.
Also probes room defaults / offers for residual 7-night rules and records
attribution clues (no cookbook script historically writes minStay).
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
            "User-Agent": "AUMARA-MinStayFix/1",
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
        "User-Agent": "AUMARA-MinStayFix/1",
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
            # Some responses are one entry per day with "date"
            date_key = None
            if isinstance(from_d, str) and len(from_d) >= 10:
                date_key = from_d[:10]
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
        # Focus around Sep 24: include nearby dates present in by_date
        focus_window = {
            k: by_date[k]
            for k in sorted(by_date)
            if "2026-09-20" <= k <= "2026-09-30"
        }
        # Histogram of minStay
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
    # Only minStay (+ maxStay safety). Do not send prices/numAvail.
    return [
        {
            "roomId": rid,
            "calendar": [
                {
                    "from": START,
                    "to": END,
                    "minStay": TARGET_MIN_STAY,
                    "maxStay": TARGET_MAX_STAY,
                }
            ],
        }
        for rid in ROOMS
    ]


def probe_rooms(token: str) -> dict[str, Any]:
    """Best-effort room defaults / property room list for residual minStay rules."""
    probes: dict[str, Any] = {}
    urls = [
        ("rooms", f"/inventory/rooms?propertyId={PROPERTY_ID}"),
        ("rooms_alt", f"/properties/rooms?propertyId={PROPERTY_ID}"),
        ("property", f"/properties?id={PROPERTY_ID}"),
        (
            "fixed_prices",
            f"/inventory/rooms/fixedPrices?propertyId={PROPERTY_ID}",
        ),
    ]
    for name, path in urls:
        status, body = http_json("GET", API + path, token, raise_http=False)
        safe: Any
        if isinstance(body, dict):
            # Strip potentially large nested blobs; keep minStay-related slices
            text = json.dumps(body)
            if "minStay" in text or "minNights" in text or "minimumStay" in text:
                # Extract compact references
                safe = {
                    "http": status,
                    "top_keys": sorted(body.keys())[:30],
                    "minStay_mentions": text.count("minStay")
                    + text.count("minNights")
                    + text.count("minimumStay"),
                    "snippet": _extract_minstay_snippets(body),
                }
            else:
                safe = {
                    "http": status,
                    "top_keys": sorted(body.keys())[:30] if isinstance(body, dict) else None,
                    "minStay_mentions": 0,
                }
        else:
            safe = {"http": status, "type": type(body).__name__}
        probes[name] = safe
    return probes


def _extract_minstay_snippets(obj: Any, path: str = "", acc: list | None = None, limit: int = 40):
    if acc is None:
        acc = []
    if len(acc) >= limit:
        return acc
    if isinstance(obj, dict):
        interesting = {
            k: obj[k]
            for k in obj
            if str(k).lower()
            in {
                "minstay",
                "minstayarrival",
                "minnights",
                "minimumstay",
                "maxstay",
                "id",
                "roomid",
                "name",
                "propertyid",
            }
        }
        if any(
            str(k).lower() in {"minstay", "minstayarrival", "minnights", "minimumstay"}
            for k in obj
        ):
            acc.append({"path": path, **interesting})
        for k, v in obj.items():
            _extract_minstay_snippets(v, f"{path}.{k}" if path else str(k), acc, limit)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:50]):
            _extract_minstay_snippets(v, f"{path}[{i}]", acc, limit)
    return acc


def probe_offers(token: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    # 2-night stay that UI blocked
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
        offers = []
        if isinstance(body, dict):
            data = body.get("data") or body.get("offers") or []
            if isinstance(data, list):
                for offer in data[:10]:
                    if not isinstance(offer, dict):
                        continue
                    offers.append(
                        {
                            k: offer.get(k)
                            for k in (
                                "offerId",
                                "name",
                                "minStay",
                                "minNights",
                                "maxStay",
                                "price",
                                "error",
                                "message",
                            )
                            if k in offer or k in ("minStay", "minNights", "error", "message")
                        }
                    )
        out[str(rid)] = {
            "http": status,
            "name": meta["name"],
            "arrival": arrival,
            "departure": departure,
            "success": body.get("success") if isinstance(body, dict) else None,
            "error": body.get("error") if isinstance(body, dict) else None,
            "count": body.get("count") if isinstance(body, dict) else None,
            "offers_sample": offers,
            "top_keys": sorted(body.keys())[:20] if isinstance(body, dict) else None,
        }
    return out


def attribution_notes(before_summary: dict, room_probes: dict, offers: dict) -> dict:
    """Infer who/what set minStay=7 from available signals (no audit log API)."""
    calendar_sevens = []
    for rid, s in before_summary.items():
        hist = s.get("minStay_histogram") or {}
        if "7" in hist:
            calendar_sevens.append({"roomId": rid, "days_with_7": hist["7"], "hist": hist})
        focus = s.get("focus_minStay")
        if str(focus) == "7":
            calendar_sevens.append({"roomId": rid, "focus_2026_09_24": 7})

    cookbook_scripts_writing_minstay = []  # verified none historically
    notes = {
        "calendar_minStay_7_found": bool(calendar_sevens),
        "calendar_seven_details": calendar_sevens,
        "room_default_minStay_from_20260825_content_audit": {
            "674465_Chalet": 2,
            "674466_Superior_Chalet": 2,
            "source": "aumara-control-tower/evidence/beds24-content-audit-20260825.json",
        },
        "cookbook_scripts_that_write_minStay": cookbook_scripts_writing_minstay,
        "cookbook_git_search": "no commits/scripts in elcidspain/openai-cookbook set minStay=7",
        "likely_sources_ranked": [
            {
                "rank": 1,
                "source": "Beds24 control-panel calendar / seasonal minStay overrides",
                "reason": (
                    "UI error 'Reserva mínima requerida 7 Noches' on beds24.com booking "
                    "engine for 2026-09-24..26; room defaults historically 2, so daily/"
                    "seasonal calendar minStay is the effective rule."
                ),
            },
            {
                "rank": 2,
                "source": "Channel manager import (Booking.com Weekly / similar)",
                "reason": (
                    "7-night minimum is a common Weekly-rate rule; channels scope missing "
                    "on API token so channel mappings cannot be confirmed via API."
                ),
            },
            {
                "rank": 3,
                "source": "Manual Beds24 UI user (property staff / Ilia / prior operator)",
                "reason": "No API audit log exposed; no cookbook automation writes minStay.",
            },
        ],
        "actor_identity": (
            "NOT attributable to a named user via API (Beds24 inventory calendar has no "
            "modifiedBy field in responses). Attribution is rule-layer based: calendar-"
            "level minStay overrides, not room defaults (defaults were 2) and not "
            "openai-cookbook automation."
        ),
        "room_probes_minStay_snippets": {
            k: (v.get("snippet") if isinstance(v, dict) else None)
            for k, v in (room_probes or {}).items()
        },
        "offers_probe_errors": {
            rid: {"http": o.get("http"), "error": o.get("error"), "count": o.get("count")}
            for rid, o in (offers or {}).items()
        },
    }
    return notes


def assert_after_ok(after_summary: dict) -> list[str]:
    problems = []
    for rid, s in after_summary.items():
        focus = s.get("focus_minStay")
        try:
            focus_n = int(focus) if focus is not None else None
        except (TypeError, ValueError):
            focus_n = None
        if focus_n is None or focus_n > 1:
            problems.append(f"room {rid} focus {FOCUS_DATE} minStay={focus} want=1")
        hist = s.get("minStay_histogram") or {}
        for val, count in hist.items():
            try:
                n = int(val)
            except ValueError:
                continue
            if n > 1 and count > 0:
                # After write, confirm window should be 1; allow reporting residual
                if CONFIRM_START <= FOCUS_DATE <= CONFIRM_END:
                    problems.append(f"room {rid} still has minStay={n} on {count} days in probe")
    return problems


def main() -> int:
    refresh = load_refresh()
    token = exchange_token(refresh)

    # Read-only details probe (scopes only; sanitize)
    details_status, details_body = http_json(
        "GET", API + "/authentication/details", token, raise_http=False
    )
    scopes = []
    if isinstance(details_body, dict) and details_status == 200:
        scopes = details_body.get("scopes") or []
    print(f"details_http={details_status} scopes_count={len(scopes) if isinstance(scopes, list) else 0}", flush=True)

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
    print("BEFORE_FOCUS", {r: before_summary[r].get("focus_minStay") for r in before_summary}, flush=True)
    print("BEFORE_HIST", {r: before_summary[r].get("minStay_histogram") for r in before_summary}, flush=True)

    room_probes = probe_rooms(token)
    offers_before = probe_offers(token)

    payload = build_minstay_payload()
    write_status, write_body = http_json(
        "POST", API + "/inventory/rooms/calendar", token, payload
    )
    print(f"write_http={write_status}", flush=True)

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
    print("AFTER_FOCUS", {r: after_summary[r].get("focus_minStay") for r in after_summary}, flush=True)
    print("AFTER_HIST", {r: after_summary[r].get("minStay_histogram") for r in after_summary}, flush=True)

    offers_after = probe_offers(token)
    attribution = attribution_notes(before_summary, room_probes, offers_before)

    problems = []
    for rid, s in after_summary.items():
        focus = s.get("focus_minStay")
        try:
            focus_n = int(focus) if focus is not None else None
        except (TypeError, ValueError):
            focus_n = None
        if focus_n != 1:
            problems.append(f"room {rid} {FOCUS_DATE} minStay={focus} (want 1)")
        # Any residual >1 in confirm window
        for date_key, info in (s.get("focus_window_2026_09_20_30") or {}).items():
            try:
                ms = int(info.get("minStay")) if info.get("minStay") is not None else None
            except (TypeError, ValueError):
                ms = None
            if ms is not None and ms > 1:
                problems.append(f"room {rid} {date_key} minStay={ms}")

    status = "PASS" if not problems else "FAIL"
    evidence = {
        "schema": "aumara.beds24-minstay-fix.v1",
        "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "property_id": PROPERTY_ID,
        "rooms": ROOMS,
        "window_written": {"start": START, "end": END, "minStay": TARGET_MIN_STAY, "maxStay": TARGET_MAX_STAY},
        "confirm_window": {"start": CONFIRM_START, "end": CONFIRM_END},
        "target_minStay": TARGET_MIN_STAY,
        "auth": {
            "details_http": details_status,
            "scopes_count": len(scopes) if isinstance(scopes, list) else 0,
            "scopes": scopes if isinstance(scopes, list) else None,
        },
        "before_summary": before_summary,
        "write_http": write_status,
        "write_body_sample": write_body[:4] if isinstance(write_body, list) else write_body,
        "after_summary": after_summary,
        "room_defaults_probes": room_probes,
        "offers_before": offers_before,
        "offers_after": offers_after,
        "attribution": attribution,
        "problems": problems,
        "status": status,
        "secret_exposed": False,
    }
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Also mirror under /workspace/evidence when running in Actions checkout layout
    mirror = pathlib.Path("/workspace/evidence/beds24-minstay-fix-20260924.json")
    try:
        mirror.parent.mkdir(parents=True, exist_ok=True)
        mirror.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception as e:
        print(f"mirror_skip={type(e).__name__}", flush=True)

    print(json.dumps({"status": status, "problems": problems, "evidence": str(EVIDENCE)}, indent=2))
    print("EVIDENCE", EVIDENCE, flush=True)
    if problems:
        raise SystemExit(f"minStay fix incomplete: {problems}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
