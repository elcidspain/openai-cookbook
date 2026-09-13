#!/usr/bin/env python3
"""Open AUMARA Beds24 rooms/inventory for Booking.com (property 324882)."""
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
    674465: {"name": "CHALET", "target_num_avail": 4},
    674466: {"name": "Superior Chalet", "target_num_avail": 2},
}
START = "2026-09-13"
END = "2026-12-31"
ROOT = pathlib.Path(__file__).resolve().parents[1]
VAULT = ROOT / "evidence" / "beds24-refresh-vault.json"
EVIDENCE = ROOT / "evidence" / "beds24-open-booking-availability-20260913.json"


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
    # If KEK present, prefer decrypting vault (Production vault-sync path)
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
    if direct and kek and direct == kek:
        # Misconfigured: KEK passed as refresh — refuse
        raise SystemExit("BEDS24_REFRESH_CREDENTIAL looks like vault KEK only; need decrypted refresh")
    if direct:
        print("auth_source=env_refresh", flush=True)
        return direct
    raise SystemExit("No Beds24 refresh credential available")


def exchange_token(refresh: str) -> str:
    # Try details first
    try:
        r = urllib.request.Request(
            API + "/authentication/details",
            headers={"Accept": "application/json", "token": refresh, "User-Agent": "AUMARA-OpenAvail/2"},
            method="GET",
        )
        with urllib.request.urlopen(r, timeout=45) as resp:
            if int(resp.status) == 200:
                print("token_mode=direct_access", flush=True)
                return refresh
    except Exception as e:
        print(f"details_probe={type(e).__name__}", flush=True)
    r = urllib.request.Request(
        API + "/authentication/token",
        headers={"Accept": "application/json", "refreshToken": refresh, "User-Agent": "AUMARA-OpenAvail/2"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(r, timeout=45) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SystemExit(f"refresh HTTP {e.code}: {e.read()[:800]!r}")
    token = (body.get("token") or "").strip()
    mask(token)
    if not token:
        raise SystemExit(f"no token keys={list(body.keys())}")
    print("token_mode=refresh_exchange", flush=True)
    return token


def http_json(method: str, url: str, token: str, body: Any | None = None):
    data = None
    headers = {"Accept": "application/json", "token": token, "User-Agent": "AUMARA-OpenAvail/2"}
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
        raise SystemExit(f"{method} {url} HTTP {e.code}: {json.dumps(parsed)[:2000]}")


def summarize(data: list) -> dict:
    out = {}
    for room in data or []:
        rid = str(room.get("roomId"))
        days = room.get("calendar") or []
        zero = sum(1 for d in days if d.get("numAvail") == 0)
        out[rid] = {"days": len(days), "numAvail_zero_days": zero, "sample": days[:2]}
    return out


def main() -> int:
    refresh = load_refresh()
    token = exchange_token(refresh)
    params = [("startDate", START), ("endDate", END), ("includePrices", "true"), ("includeNumAvail", "true")]
    for rid in ROOMS:
        params.append(("roomId", str(rid)))
    cal_url = API + "/inventory/rooms/calendar?" + urllib.parse.urlencode(params)
    _, before = http_json("GET", cal_url, token)
    before_data = (before or {}).get("data") if isinstance(before, dict) else before
    if not isinstance(before_data, list):
        before_data = []

    payload = [
        {
            "roomId": rid,
            "calendar": [
                {
                    "from": START,
                    "to": END,
                    "numAvail": meta["target_num_avail"],
                    "override": "none",
                }
            ],
        }
        for rid, meta in ROOMS.items()
    ]
    write_status, write_body = http_json("POST", API + "/inventory/rooms/calendar", token, payload)
    _, after = http_json("GET", cal_url, token)
    after_data = (after or {}).get("data") if isinstance(after, dict) else after
    if not isinstance(after_data, list):
        after_data = []

    avail_params = [("startDate", "2026-09-19"), ("endDate", "2026-09-26")]
    for rid in ROOMS:
        avail_params.append(("roomId", str(rid)))
    _, avail = http_json("GET", API + "/inventory/rooms/availability?" + urllib.parse.urlencode(avail_params), token)

    # Channel settings probe (Booking rate closed diagnosis)
    ch = None
    try:
        _, ch = http_json("GET", API + f"/channels/settings?propertyId={PROPERTY_ID}", token)
    except SystemExit as e:
        ch = {"error": str(e)[:400]}

    evidence = {
        "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "property_id": PROPERTY_ID,
        "rooms": ROOMS,
        "window": {"start": START, "end": END},
        "before_summary": summarize(before_data),
        "write_http": write_status,
        "write_body": write_body[:4] if isinstance(write_body, list) else write_body,
        "after_summary": summarize(after_data),
        "availability_19_26": avail,
        "channel_settings_probe": ch if not isinstance(ch, dict) else {k: ch.get(k) for k in list(ch)[:8]},
        "status": "SUCCESS",
    }
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    print("EVIDENCE", EVIDENCE)
    # Fail if still all zero avail in window sample
    bad = []
    for rid, s in evidence["after_summary"].items():
        if s.get("numAvail_zero_days", 0) == s.get("days", 0) and s.get("days", 0) > 0:
            bad.append(rid)
    if bad:
        raise SystemExit(f"still fully zero numAvail for rooms {bad}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
