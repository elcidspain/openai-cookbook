#!/usr/bin/env python3
"""Harden the two dormant AUMARA AI-agent Fixed Price control slots.

This script only touches the two known control IDs, keeps them disabled and in the
past, removes agent codes, disables both booking pages, disables channel management,
and turns every returned OTA/channel flag off. It then verifies the live read-back.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from beds24_elcid_studio_audit import API_BASES, get_access_token, normalize, request_json

PROPERTY_ID = 324882
CONTROLS = {
    6952922: {"roomId": 674465, "name": "AUMARA AI Agent Control - Chalet DORMANT"},
    6952923: {"roomId": 674466, "name": "AUMARA AI Agent Control - Superior Chalet DORMANT"},
}
OUT = pathlib.Path("aumara-control-tower/evidence/aumara-agent-control-harden.json")


def access() -> tuple[str, str]:
    direct = normalize(os.environ.get("BEDS24_PROPERTIES_TOKEN"))
    if direct:
        for api_base in API_BASES:
            status, details = request_json("GET", "/authentication/details", headers={"token": direct}, api_base=api_base)
            if 200 <= status < 300 and isinstance(details, dict) and details.get("validToken") is True:
                return direct, api_base
    token, _, api_base, _, _ = get_access_token()
    return token, api_base


def call(method: str, path: str, token: str, api_base: str, payload=None):
    body = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
    headers = {"accept": "application/json", "token": token}
    if body is not None:
        headers["content-type"] = "application/json"
    req = urllib.request.Request(api_base + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        return exc.code, {}


def read_controls(token: str, api_base: str):
    query = urllib.parse.urlencode({"propertyId": PROPERTY_ID, "includeRateCodes": "true"})
    status, body = call("GET", "/inventory/fixedPrices?" + query, token, api_base)
    if not 200 <= status < 300 or not isinstance(body, dict) or not isinstance(body.get("data"), list):
        raise RuntimeError(f"control read failed HTTP {status}")
    rows = {int(r.get("id") or 0): r for r in body["data"] if int(r.get("id") or 0) in CONTROLS}
    if set(rows) != set(CONTROLS):
        raise RuntimeError(f"expected control IDs {sorted(CONTROLS)}, got {sorted(rows)}")
    for fid, expected in CONTROLS.items():
        row = rows[fid]
        if int(row.get("propertyId") or 0) != PROPERTY_ID or int(row.get("roomId") or 0) != expected["roomId"]:
            raise RuntimeError(f"control {fid} scope mismatch")
        if str(row.get("name") or "") != expected["name"]:
            raise RuntimeError(f"control {fid} name mismatch")
        if str(row.get("lastNight") or "") >= "2026-09-15" or row.get("roomPriceEnable") is not False:
            raise RuntimeError(f"control {fid} is not safely dormant")
    return rows


def main() -> int:
    token, api_base = access()
    before = read_controls(token, api_base)
    payload = []
    for fid, row in before.items():
        channels = row.get("channels") or {}
        payload.append({
            "id": fid,
            "propertyId": PROPERTY_ID,
            "roomId": int(row["roomId"]),
            "roomPriceEnable": False,
            "agentCodes": [],
            "bookingPage": {"direct": False, "agent": False},
            "channelManagement": "notUsed",
            "channels": {str(name): {"enable": False} for name in channels},
        })
    status, _ = call("POST", "/inventory/fixedPrices", token, api_base, payload)
    if status != 201:
        raise RuntimeError(f"control hardening failed HTTP {status}")
    after = read_controls(token, api_base)
    result = {"schema": "aumara-agent-control-harden-v1", "propertyId": PROPERTY_ID, "postHttpStatus": status, "controls": {}}
    for fid, row in after.items():
        page = row.get("bookingPage") or {}
        channels = row.get("channels") or {}
        channel_values = [bool((v or {}).get("enable")) for v in channels.values() if isinstance(v, dict)]
        ok = (
            row.get("roomPriceEnable") is False
            and not (row.get("agentCodes") or [])
            and page.get("direct") is False
            and page.get("agent") is False
            and row.get("channelManagement") == "notUsed"
            and not any(channel_values)
        )
        result["controls"][str(fid)] = {
            "roomId": row.get("roomId"),
            "roomPriceEnable": row.get("roomPriceEnable"),
            "bookingPage": page,
            "channelManagement": row.get("channelManagement"),
            "channelCount": len(channels),
            "enabledChannelCount": sum(channel_values),
            "agentCodeCount": len(row.get("agentCodes") or []),
            "verified": ok,
        }
        if not ok:
            raise RuntimeError(f"control {fid} hardening read-back failed")
    result["allVerified"] = all(v["verified"] for v in result["controls"].values())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "controls": result["controls"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
