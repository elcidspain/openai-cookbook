import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta

API = "https://api.beds24.com/v2"
PROPERTY_ID = 324882
OUTPUT = os.environ.get("AUDIT_OUTPUT", "aumara-agent-commerce-audit.json")


def get_json(path, headers=None, params=None):
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"Accept": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def find_agent_code_nodes(value, path="root", out=None):
    out = out if out is not None else []
    if isinstance(value, dict):
        codes = value.get("agentCodes")
        if isinstance(codes, list) and codes:
            out.append({
                "path": path,
                "code_count": len(codes),
                "minimumStay": value.get("minimumStay"),
                "maximumStay": value.get("maximumStay"),
                "offer": value.get("offer"),
                "bookingPage": value.get("bookingPage"),
                "codes": [str(code) for code in codes if str(code).strip()],
            })
        for key, child in value.items():
            find_agent_code_nodes(child, f"{path}.{key}", out)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            find_agent_code_nodes(child, f"{path}[{index}]", out)
    return out


def safe_offer_rows(payload):
    rows = []
    for room in payload.get("data", []) if isinstance(payload, dict) else []:
        for offer in room.get("offers", []) if isinstance(room, dict) else []:
            rows.append({
                "roomId": room.get("roomId"),
                "propertyId": room.get("propertyId"),
                "offerId": offer.get("offerId"),
                "offerName": offer.get("offerName"),
                "price": offer.get("price"),
                "unitsAvailable": offer.get("unitsAvailable"),
            })
    return rows


def main():
    refresh = os.environ.get("BEDS24_REFRESH_CREDENTIAL", "").strip()
    if not refresh:
        raise RuntimeError("BEDS24_REFRESH_CREDENTIAL is not configured")

    auth = get_json("/authentication/token", headers={"refreshToken": refresh})
    token = str(auth.get("token", "")).strip()
    if not token:
        raise RuntimeError("Beds24 token refresh returned no access token")
    headers = {"token": token}

    properties = get_json(
        "/properties",
        headers=headers,
        params={
            "id": PROPERTY_ID,
            "includeAllRooms": "true",
            "includeOffers": "true",
            "includePriceRules": "true",
        },
    )
    matches = [p for p in properties.get("data", []) if p.get("id") == PROPERTY_ID]
    if not matches:
        raise RuntimeError(f"Property {PROPERTY_ID} was not returned by Beds24")
    prop = matches[0]

    agent_nodes = find_agent_code_nodes(prop)
    agent_codes = []
    for node in agent_nodes:
        for code in node.pop("codes", []):
            if code not in agent_codes:
                agent_codes.append(code)

    arrival = date.today() + timedelta(days=7)
    departure = arrival + timedelta(days=4)
    base_params = {
        "propertyId": PROPERTY_ID,
        "arrival": arrival.isoformat(),
        "departure": departure.isoformat(),
        "numAdults": 2,
        "numChildren": 0,
        "includeTexts": "en",
    }
    public_offers = safe_offer_rows(get_json("/inventory/rooms/offers", headers=headers, params=base_params))
    agent_offer_sets = []
    for index, code in enumerate(agent_codes, start=1):
        params = dict(base_params)
        params["agentCode"] = code
        rows = safe_offer_rows(get_json("/inventory/rooms/offers", headers=headers, params=params))
        agent_offer_sets.append({"agent_label": f"agent_code_{index}", "offers": rows})

    discount_vouchers = []
    for voucher in prop.get("discountVouchers", []) or []:
        if not isinstance(voucher, dict):
            continue
        discount_vouchers.append({
            "number": voucher.get("number"),
            "type": voucher.get("type"),
            "discount": voucher.get("discount"),
            "phrase_configured": bool(str(voucher.get("phrase") or "").strip()),
        })
    one_time = [
        {"discount": v.get("discount")}
        for v in (prop.get("oneTimeVouchers", []) or [])
        if isinstance(v, dict)
    ]

    result = {
        "property": {"id": prop.get("id"), "name": prop.get("name"), "currency": prop.get("currency")},
        "sample": {"arrival": arrival.isoformat(), "departure": departure.isoformat(), "adults": 2},
        "agent_price_rule_nodes": agent_nodes,
        "agent_code_count": len(agent_codes),
        "discount_vouchers": discount_vouchers,
        "one_time_vouchers": {"count": len(one_time), "discounts": one_time},
        "public_offers": public_offers,
        "agent_offer_sets": agent_offer_sets,
        "notes": [
            "Agent code values and voucher phrases are deliberately omitted.",
            "This audit is read-only and makes no pricing, inventory, booking or voucher changes.",
        ],
    }
    with open(OUTPUT, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
    print(json.dumps({
        "property_id": prop.get("id"),
        "agent_code_count": len(agent_codes),
        "discount_voucher_count": len(discount_vouchers),
        "one_time_voucher_count": len(one_time),
        "public_offer_count": len(public_offers),
        "agent_offer_set_count": len(agent_offer_sets),
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"audit_failed: {exc}", file=sys.stderr)
        raise
