#!/usr/bin/env python3
"""Read-only audit of AUMARA Beds24 pricing/offer configuration.

Uses the existing encrypted Production refresh-token vault. It never writes to Beds24
and never emits credentials. The evidence file contains only sanitized property,
price-rule, offer and fixed-price configuration needed to select a safe agent-only slot.
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import os
import pathlib
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from cryptography.fernet import Fernet

API = "https://api.beds24.com/v2"
PROPERTY_ID = 324882
ROOM_IDS = (674465, 674466)
ROOT = pathlib.Path(__file__).resolve().parents[1]
VAULT = ROOT / "evidence" / "beds24-refresh-vault.json"
OUT = ROOT / "evidence" / "beds24-agent-rate-audit-20260915.json"


def mask(value: str) -> None:
    if value:
        print(f"::add-mask::{value}", flush=True)


def vault_key(kek: str) -> bytes:
    digest = hashlib.sha256(("AUMARA_BEDS24_REFRESH_VAULT_V1\0" + kek).encode()).digest()
    return base64.urlsafe_b64encode(digest)


def load_refresh() -> str:
    direct = (os.environ.get("BEDS24_REFRESH_CREDENTIAL") or os.environ.get("BEDS24_REFRESH_TOKEN") or "").strip().strip('"').strip("'")
    kek = (os.environ.get("BEDS24_VAULT_KEK") or "").strip().strip('"').strip("'")
    mask(direct)
    mask(kek)
    if direct and (not kek or direct != kek):
        return direct
    if kek and VAULT.exists():
        data = json.loads(VAULT.read_text(encoding="utf-8"))
        refresh = Fernet(vault_key(kek)).decrypt(data["ciphertext"].encode()).decode().strip()
        mask(refresh)
        return refresh
    raise SystemExit("No Beds24 refresh credential available")


def request_json(path: str, token: str) -> tuple[int, Any]:
    req = urllib.request.Request(
        API + path,
        headers={"Accept": "application/json", "token": token, "User-Agent": "AUMARA-Agent-Rate-Audit/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read()
            return int(resp.status), json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            body = json.loads(raw.decode("utf-8", "replace")) if raw else {}
        except Exception:
            body = {"raw": raw[:500].decode("utf-8", "replace")}
        return int(exc.code), body


def exchange_token(refresh: str) -> str:
    status, details = request_json("/authentication/details", refresh)
    if 200 <= status < 300 and isinstance(details, dict) and details.get("validToken") is True:
        return refresh
    req = urllib.request.Request(
        API + "/authentication/token",
        headers={"Accept": "application/json", "refreshToken": refresh, "User-Agent": "AUMARA-Agent-Rate-Audit/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Beds24 refresh failed HTTP {exc.code}")
    token = (body.get("token") or "").strip()
    mask(token)
    if not token:
        raise SystemExit("Beds24 refresh returned no access token")
    return token


def sanitize(value: Any, depth: int = 0) -> Any:
    if depth > 14:
        return "[DEPTH_LIMIT]"
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            lk = str(key).lower()
            if any(x in lk for x in ("token", "secret", "password", "credential", "apikey", "api_key", "card")):
                out[str(key)] = "[REDACTED]"
            else:
                out[str(key)] = sanitize(item, depth + 1)
        return out
    if isinstance(value, list):
        return [sanitize(x, depth + 1) for x in value[:250]]
    if isinstance(value, str):
        return value[:2000]
    return value


def get(path: str, token: str) -> dict[str, Any]:
    status, body = request_json(path, token)
    return {"http_status": status, "ok": 200 <= status < 300, "body": sanitize(body)}


def qs(items: list[tuple[str, str]]) -> str:
    return urllib.parse.urlencode(items)


def main() -> int:
    refresh = load_refresh()
    token = exchange_token(refresh)

    prop_query = qs([
        ("id", str(PROPERTY_ID)),
        ("includeAllRooms", "true"),
        ("includeOffers", "true"),
        ("includePriceRules", "true"),
    ])
    fixed_query = qs([
        ("propertyId", str(PROPERTY_ID)),
        ("includeRateCodes", "true"),
    ])
    offer_query = qs([
        ("propertyId", str(PROPERTY_ID)),
        ("arrival", "2026-09-20"),
        ("departure", "2026-09-22"),
        ("numAdults", "2"),
        ("numChildren", "0"),
    ])
    calendar_items = [
        ("startDate", "2026-09-20"),
        ("endDate", "2026-09-22"),
        ("includePrices", "true"),
        ("includeNumAvail", "true"),
    ] + [("roomId", str(rid)) for rid in ROOM_IDS]

    evidence = {
        "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode": "read_only",
        "property_id": PROPERTY_ID,
        "room_ids": list(ROOM_IDS),
        "properties_with_price_rules_and_offers": get("/properties?" + prop_query, token),
        "fixed_prices_with_rate_codes": get("/inventory/fixedPrices?" + fixed_query, token),
        "calculated_public_offers_sample": get("/inventory/rooms/offers?" + offer_query, token),
        "calendar_price_sample": get("/inventory/rooms/calendar?" + qs(calendar_items), token),
        "secret_exposed": False,
        "beds24_mutation_performed": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    statuses = {k: v.get("http_status") for k, v in evidence.items() if isinstance(v, dict) and "http_status" in v}
    print(json.dumps({"status": "AUDIT_COMPLETE", "http": statuses, "evidence": str(OUT)}))
    if not evidence["properties_with_price_rules_and_offers"]["ok"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
