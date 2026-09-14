#!/usr/bin/env python3
"""Create, verify, then dormancy-safe two AUMARA agent-only Fixed Price control slots.

The random agent code is kept in memory only and never printed or persisted.
The smoke prices are deliberately noncompetitive and are immediately disabled after verification.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from beds24_elcid_studio_audit import API_BASES, get_access_token, normalize, request_json

PROPERTY_ID = 324882
ROOMS = {674465: ("Chalet", 9999.0, 4), 674466: ("Superior Chalet", 9998.0, 6)}
TEST_NIGHT = "2027-05-18"
TEST_DEPARTURE = "2027-05-19"
DORMANT_NIGHT = "2026-09-01"
SMOKE_PREFIX = "AUMARA AI Agent API Smoke"
OUT = pathlib.Path("aumara-control-tower/evidence/aumara-agent-fixed-price-smoke.json")


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
        raw = exc.read().decode("utf-8", "replace")
        try:
            data = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            data = {"errorType": "non_json_http_error"}
        return exc.code, data


def list_prices(token: str, api_base: str):
    q = urllib.parse.urlencode({"propertyId": PROPERTY_ID, "includeRateCodes": "true"})
    status, body = call("GET", "/inventory/fixedPrices?" + q, token, api_base)
    if not 200 <= status < 300 or not isinstance(body, dict) or not isinstance(body.get("data"), list):
        raise RuntimeError(f"fixed price read failed HTTP {status}")
    return body["data"]


def offers(token: str, api_base: str, room_id: int, agent_code: str | None):
    params = [("propertyId", PROPERTY_ID), ("roomId", room_id), ("arrival", TEST_NIGHT), ("departure", TEST_DEPARTURE), ("numAdults", 2), ("numChildren", 0)]
    if agent_code:
        params.append(("agentCode", agent_code))
    return call("GET", "/inventory/rooms/offers?" + urllib.parse.urlencode(params), token, api_base)


def extract_prices(body) -> list[float]:
    out = []
    if isinstance(body, dict):
        for row in body.get("data") or []:
            if isinstance(row, dict):
                for offer in row.get("offers") or []:
                    if isinstance(offer, dict) and isinstance(offer.get("price"), (int, float)):
                        out.append(float(offer["price"]))
    return out


def active_payload(code: str):
    rows = []
    for room_id, (label, smoke_price, guests) in ROOMS.items():
        rows.append({
            "propertyId": PROPERTY_ID, "roomId": room_id, "offerId": 1,
            "firstNight": TEST_NIGHT, "lastNight": TEST_NIGHT,
            "name": f"{SMOKE_PREFIX} - {label}",
            "minNights": 1, "maxNights": 1, "minAdvance": 0, "maxAdvance": 999,
            "strategy": "noOtherPrices", "restrictionStrategy": "stayThrough", "bookingType": "default",
            "roomPrice": smoke_price, "roomPriceEnable": True, "roomPriceGuests": guests,
            "agentCodes": [code], "bookingPage": {"direct": False, "agent": True},
        })
    return rows


def dormant_payload(rows):
    out = []
    for row in rows:
        room_id = int(row["roomId"])
        label, smoke_price, guests = ROOMS[room_id]
        out.append({
            "id": int(row["id"]), "propertyId": PROPERTY_ID, "roomId": room_id, "offerId": 1,
            "firstNight": DORMANT_NIGHT, "lastNight": DORMANT_NIGHT,
            "name": f"AUMARA AI Agent Control - {label} DORMANT",
            "minNights": 1, "maxNights": 1, "strategy": "default", "restrictionStrategy": "stayThrough",
            "roomPrice": smoke_price, "roomPriceEnable": False, "roomPriceGuests": guests,
            "agentCodes": [], "bookingPage": {"direct": False, "agent": False},
        })
    return out


def smoke_rows(rows):
    return [
        row for row in rows
        if int(row.get("roomId") or 0) in ROOMS
        and str(row.get("name") or "").startswith(SMOKE_PREFIX)
        and row.get("id") is not None
    ]


def persist(evidence):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    token, api_base = access()
    code = "AUMARA-AI-" + secrets.token_urlsafe(18)
    created = []
    failure = None
    evidence = {
        "schema": "aumara-agent-fixed-price-smoke-v2",
        "testNight": TEST_NIGHT,
        "rooms": {},
        "secretLogged": False,
    }
    try:
        status, _ = call("POST", "/inventory/fixedPrices", token, api_base, active_payload(code))
        evidence["createHttpStatus"] = status
        if status != 201:
            raise RuntimeError(f"fixed price create failed HTTP {status}")
        current = list_prices(token, api_base)
        for room_id, (label, smoke_price, _) in ROOMS.items():
            matches = [r for r in smoke_rows(current) if int(r.get("roomId") or 0) == room_id]
            if len(matches) != 1:
                raise RuntimeError(f"room {room_id}: expected one smoke fixed price, got {len(matches)}")
            row = matches[0]
            created.append(row)
            page = row.get("bookingPage") or {}
            codes = row.get("agentCodes") or []
            agent_only = page.get("direct") is False and page.get("agent") is True and len(codes) == 1
            if not agent_only:
                raise RuntimeError(f"room {room_id}: agent-only read-back failed")
            public_status, public_body = offers(token, api_base, room_id, None)
            agent_status, agent_body = offers(token, api_base, room_id, code)
            public_prices = extract_prices(public_body)
            agent_prices = extract_prices(agent_body)
            public_seen = smoke_price in public_prices
            agent_seen = smoke_price in agent_prices
            evidence["rooms"][str(room_id)] = {
                "label": label,
                "fixedPriceId": row.get("id"),
                "agentOnlyReadBack": agent_only,
                "publicOfferHttp": public_status,
                "agentOfferHttp": agent_status,
                "smokePriceSeenPublic": public_seen,
                "smokePriceSeenWithAgentCode": agent_seen,
            }
            if public_seen:
                raise RuntimeError(f"room {room_id}: agent-only smoke price leaked into public offers")
            if not 200 <= agent_status < 300 or not agent_seen:
                raise RuntimeError(f"room {room_id}: agent-code offer was not materialized")
        evidence["agentIsolationVerified"] = len(evidence["rooms"]) == len(ROOMS) and all(
            v["agentOnlyReadBack"]
            and 200 <= v["publicOfferHttp"] < 300
            and 200 <= v["agentOfferHttp"] < 300
            and not v["smokePriceSeenPublic"]
            and v["smokePriceSeenWithAgentCode"]
            for v in evidence["rooms"].values()
        )
    except Exception as exc:
        failure = str(exc)
        evidence["verificationFailure"] = failure
    finally:
        try:
            fresh = list_prices(token, api_base)
            cleanup_by_id = {int(r["id"]): r for r in created if r.get("id") is not None}
            cleanup_by_id.update({int(r["id"]): r for r in smoke_rows(fresh)})
            cleanup = list(cleanup_by_id.values())
            evidence["cleanupCandidateCount"] = len(cleanup)
            if cleanup:
                cleanup_status, _ = call("POST", "/inventory/fixedPrices", token, api_base, dormant_payload(cleanup))
                evidence["cleanupHttpStatus"] = cleanup_status
                if cleanup_status != 201:
                    raise RuntimeError(f"dormancy cleanup failed HTTP {cleanup_status}")
                dormant = list_prices(token, api_base)
                ids = {int(r.get("id") or 0): r for r in dormant}
                evidence["dormantVerified"] = all(
                    int(r["id"]) in ids
                    and (ids[int(r["id"])].get("bookingPage") or {}).get("agent") is False
                    and (ids[int(r["id"])].get("bookingPage") or {}).get("direct") is False
                    and ids[int(r["id"])].get("roomPriceEnable") is False
                    and not (ids[int(r["id"])].get("agentCodes") or [])
                    for r in cleanup
                )
                if not evidence["dormantVerified"]:
                    raise RuntimeError("dormancy read-back verification failed")
            else:
                evidence["dormantVerified"] = True
        except Exception as cleanup_exc:
            evidence["cleanupFailure"] = str(cleanup_exc)
            if failure is None:
                failure = str(cleanup_exc)
        evidence["completedAtUtc"] = dt.datetime.now(dt.timezone.utc).isoformat()
        persist(evidence)

    if failure:
        raise SystemExit(failure)
    passed = bool(evidence.get("agentIsolationVerified") and evidence.get("dormantVerified"))
    print(json.dumps({"status": "PASS" if passed else "FAIL", "agentIsolationVerified": evidence.get("agentIsolationVerified"), "dormantVerified": evidence.get("dormantVerified"), "rooms": evidence.get("rooms")}))
    return 0 if passed else 3


if __name__ == "__main__":
    raise SystemExit(main())
