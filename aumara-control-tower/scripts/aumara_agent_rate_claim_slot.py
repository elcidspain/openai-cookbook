#!/usr/bin/env python3
"""Safely claim Daily Price Rule #2 for the AUMARA AI-agent rate.

This is deliberately a minimal first mutation: it changes only the rule name on
AUMARA property 324882 for the two rentable room types. No price, channel,
offer, inventory, booking, or agent-code setting is changed here.

Preconditions are strict and a partial write is rolled back before failing.
Credentials are never printed.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from beds24_elcid_studio_audit import API_BASES, data_rows, get_access_token, normalize, request_json

PROPERTY_ID = 324882
TARGETS = {674465: "Chalet", 674466: "Superior Chalet"}
PRICE_RULE_ID = 2
TARGET_NAME = "AUMARA AI Agent"
OUT = pathlib.Path("aumara-control-tower/evidence/aumara-agent-rate-slot-claim.json")


def resolve_access() -> tuple[str, str, str]:
    direct = normalize(os.environ.get("BEDS24_PROPERTIES_TOKEN"))
    if direct:
        for api_base in API_BASES:
            status, details = request_json(
                "GET", "/authentication/details", headers={"token": direct}, api_base=api_base
            )
            if 200 <= status < 300 and isinstance(details, dict) and details.get("validToken") is True:
                return direct, api_base, "long_life_token"
    token, mode, api_base, _, _ = get_access_token()
    return token, api_base, mode


def fetch_property(token: str, api_base: str) -> dict:
    path = f"/properties?id={PROPERTY_ID}&includePriceRules=true&includeOffers=true&includeAllRooms=true"
    status, payload = request_json("GET", path, headers={"token": token}, api_base=api_base)
    if not 200 <= status < 300:
        raise RuntimeError(f"Beds24 property read failed HTTP {status}")
    rows = data_rows(payload, "AUMARA property")
    if len(rows) != 1 or int(rows[0].get("id") or 0) != PROPERTY_ID:
        raise RuntimeError("Property response was not uniquely scoped")
    return rows[0]


def target_rules(prop: dict) -> dict[int, dict]:
    found: dict[int, dict] = {}
    for room in prop.get("roomTypes") or []:
        if not isinstance(room, dict):
            continue
        room_id = int(room.get("id") or 0)
        if room_id not in TARGETS:
            continue
        for rule in room.get("priceRules") or []:
            if isinstance(rule, dict) and int(rule.get("id") or 0) == PRICE_RULE_ID:
                found[room_id] = rule
                break
    if set(found) != set(TARGETS):
        raise RuntimeError(f"Expected rule {PRICE_RULE_ID} on both AUMARA room types")
    return found


def is_unused(rule: dict) -> bool:
    return all(
        rule.get(key) in (None, "", [], {})
        for key in (
            "name",
            "minimumStay",
            "maximumStay",
            "offer",
            "minDaysUntilCheckin",
            "maxDaysUntilCheckin",
            "priceLinking",
            "bookingPage",
            "agentCodes",
        )
    )


def post_properties(token: str, api_base: str, name: str | None) -> tuple[int, object]:
    payload = [
        {
            "id": PROPERTY_ID,
            "roomTypes": [
                {
                    "id": room_id,
                    "priceRules": [{"priceruleid": PRICE_RULE_ID, "name": name}],
                }
                for room_id in TARGETS
            ],
        }
    ]
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        api_base + "/properties",
        data=body,
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "token": token,
            "user-agent": "AUMARA-Agent-Rate-Slot-Claim/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read().decode("utf-8", "replace")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"errorType": "non_json_http_error"}
        return exc.code, parsed


def names_snapshot(rules: dict[int, dict]) -> dict[str, object]:
    return {str(room_id): {"roomName": TARGETS[room_id], "ruleId": PRICE_RULE_ID, "name": rule.get("name")} for room_id, rule in rules.items()}


def main() -> int:
    token, api_base, auth_mode = resolve_access()
    before_prop = fetch_property(token, api_base)
    before = target_rules(before_prop)

    for room_id, rule in before.items():
        current_name = rule.get("name")
        if current_name == TARGET_NAME:
            continue
        if not is_unused(rule):
            raise SystemExit(f"Safety gate: price rule {PRICE_RULE_ID} is no longer unused for room {room_id}")

    status, response = post_properties(token, api_base, TARGET_NAME)
    if not 200 <= status < 300:
        raise SystemExit(f"Beds24 slot-claim POST failed HTTP {status}")

    after = target_rules(fetch_property(token, api_base))
    ok = all(rule.get("name") == TARGET_NAME for rule in after.values())
    rolled_back = False
    if not ok:
        rollback_status, _ = post_properties(token, api_base, None)
        rolled_back = 200 <= rollback_status < 300
        raise SystemExit("Beds24 slot claim failed read-back verification; rollback attempted")

    evidence = {
        "schema": "aumara-ai-agent-rate-slot-claim-v1",
        "propertyId": PROPERTY_ID,
        "authMode": auth_mode,
        "ruleId": PRICE_RULE_ID,
        "targetName": TARGET_NAME,
        "before": names_snapshot(before),
        "after": names_snapshot(after),
        "postHttpStatus": status,
        "postResponseShape": type(response).__name__,
        "verified": True,
        "rolledBack": rolled_back,
        "pricesChanged": False,
        "channelsChanged": False,
        "inventoryChanged": False,
        "bookingsChanged": False,
        "secretLogged": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "SLOT_CLAIMED", "ruleId": PRICE_RULE_ID, "verified": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
