#!/usr/bin/env python3
"""Read-only Beds24 fixed-price audit for AUMARA agent-rate design."""
from __future__ import annotations

import json
import os
import pathlib
import sys
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from beds24_elcid_studio_audit import API_BASES, get_access_token, normalize, request_json

PROPERTY_ID = 324882
ROOM_IDS = {674465, 674466}
OUT = pathlib.Path("aumara-control-tower/evidence/aumara-agent-fixed-price-audit.json")


def resolve_access() -> tuple[str, str, str]:
    direct = normalize(os.environ.get("BEDS24_PROPERTIES_TOKEN"))
    if direct:
        for api_base in API_BASES:
            status, details = request_json("GET", "/authentication/details", headers={"token": direct}, api_base=api_base)
            if 200 <= status < 300 and isinstance(details, dict) and details.get("validToken") is True:
                return direct, api_base, "long_life_token"
    token, mode, api_base, _, _ = get_access_token()
    return token, api_base, mode


def sanitize(value, key_hint: str = ""):
    sensitive = any(word in key_hint.lower() for word in ("agentcode", "ratecode", "vouchercode", "token", "secret", "password"))
    if isinstance(value, dict):
        return {str(k): sanitize(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(v, key_hint) for v in value[:500]]
    if sensitive and value not in (None, "", False, 0):
        return "[REDACTED]"
    return value


def main() -> int:
    token, api_base, auth_mode = resolve_access()
    query = urllib.parse.urlencode({"propertyId": PROPERTY_ID, "includeRateCodes": "true"})
    status, payload = request_json("GET", f"/inventory/fixedPrices?{query}", headers={"token": token}, api_base=api_base)
    result = {
        "schema": "aumara-agent-fixed-price-audit-v1",
        "propertyId": PROPERTY_ID,
        "roomIds": sorted(ROOM_IDS),
        "authMode": auth_mode,
        "httpStatus": status,
        "ok": 200 <= status < 300,
        "payload": sanitize(payload),
        "writePerformed": False,
        "secretLogged": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "AUDIT_COMPLETE", "httpStatus": status, "ok": result["ok"]}))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
