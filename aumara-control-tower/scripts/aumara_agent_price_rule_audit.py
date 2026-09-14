#!/usr/bin/env python3
"""Read-only AUMARA price-rule audit for agent pricing design.

Never prints credentials or agent-code values. It returns only the rule structure
needed to choose a free/compatible price-rule slot safely.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from beds24_elcid_studio_audit import API_BASES, data_rows, get_access_token, normalize, request_json

PROPERTY_ID = 324882


def resolve_access():
    direct = normalize(os.environ.get("BEDS24_PROPERTIES_TOKEN"))
    if direct:
        for api_base in API_BASES:
            status, details = request_json("GET", "/authentication/details", headers={"token": direct}, api_base=api_base)
            if 200 <= status < 300 and isinstance(details, dict) and details.get("validToken") is True:
                return direct, api_base, "long_life_token"
    token, mode, api_base, _, _ = get_access_token()
    return token, api_base, mode


def safe_linking(value):
    if not isinstance(value, dict):
        return None
    return {
        "roomId": value.get("roomId"),
        "priceId": value.get("priceId"),
        "offsetMultiplier": value.get("offsetMultiplier"),
        "offsetAmount": value.get("offsetAmount"),
    }


def main():
    token, api_base, mode = resolve_access()
    path = f"/properties?id={PROPERTY_ID}&includePriceRules=true&includeOffers=true&includeAllRooms=true"
    status, payload = request_json("GET", path, headers={"token": token}, api_base=api_base)
    if not 200 <= status < 300:
        raise SystemExit(f"Beds24 property read failed HTTP {status}")
    rows = data_rows(payload, "AUMARA property")
    if len(rows) != 1 or int(rows[0].get("id") or 0) != PROPERTY_ID:
        raise SystemExit("Property response was not uniquely scoped")
    prop = rows[0]
    room_types = []
    for room in prop.get("roomTypes") or []:
        if not isinstance(room, dict):
            continue
        rules = []
        for rule in room.get("priceRules") or []:
            if not isinstance(rule, dict):
                continue
            codes = rule.get("agentCodes") or []
            rules.append({
                "id": rule.get("id"),
                "name": rule.get("name"),
                "minimumStay": rule.get("minimumStay"),
                "maximumStay": rule.get("maximumStay"),
                "offer": rule.get("offer"),
                "minDaysUntilCheckin": rule.get("minDaysUntilCheckin"),
                "maxDaysUntilCheckin": rule.get("maxDaysUntilCheckin"),
                "priceLinking": safe_linking(rule.get("priceLinking")),
                "agentCodeCount": len(codes) if isinstance(codes, list) else 0,
                "bookingPage": rule.get("bookingPage"),
                "voucherCodes": rule.get("voucherCodes"),
            })
        room_types.append({
            "id": room.get("id"),
            "name": room.get("name"),
            "qty": room.get("qty"),
            "priceRules": rules,
        })
    out = {
        "propertyId": PROPERTY_ID,
        "propertyName": prop.get("name"),
        "currency": prop.get("currency"),
        "credentialMode": mode,
        "rooms": room_types,
        "secretsExposed": False,
        "writePerformed": False,
    }
    print(json.dumps(out, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
