"""Owner-approved whole-euro AUMARA prices, shared by apply and audit jobs."""

import datetime as dt
import hashlib
import json

ROOM_IDS = {"chalet": "674465", "superiorChalet": "674466"}


def each_day(start, end):
    current = start
    while current <= end:
        yield current
        current += dt.timedelta(days=1)


def whole_eur(value):
    if type(value) is not int or value <= 0:
        raise ValueError("Prices must be positive whole EUR")
    return value


def grid_digest(grid):
    raw = json.dumps(grid, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def build_expected(config, verify_approval=True):
    if config.get("schemaVersion") != 3:
        raise ValueError("Unsupported pricing schema")
    if config.get("property", {}).get("beds24PropertyId") != 324882:
        raise ValueError("Unexpected property")
    if config["property"].get("currency") != "EUR":
        raise ValueError("Unexpected currency")
    if config["policy"].get("weekendDays") != ["FRI", "SAT"]:
        raise ValueError("Unexpected weekend policy")
    for key, room_id in ROOM_IDS.items():
        if str(config["rooms"][key]["roomId"]) != room_id:
            raise ValueError("Unexpected room mapping")
    start = dt.date.fromisoformat(config["effectiveFrom"])
    end = dt.date.fromisoformat(config["horizonThrough"])
    if end < start:
        raise ValueError("Reversed horizon")
    expected = {room_id: {} for room_id in ROOM_IDS.values()}
    covered = set()
    for period in config["monthlyRates"]:
        a, b = (dt.date.fromisoformat(period[key]) for key in ("from", "to"))
        if b < a or a < start or b > end or (a.year, a.month) != (b.year, b.month):
            raise ValueError("Invalid monthly period")
        for day in each_day(a, b):
            key = day.strftime("%Y%m%d")
            if key in covered:
                raise ValueError("Overlapping monthly periods")
            covered.add(key)
            kind = "weekend" if day.weekday() in (4, 5) else "weekday"
            for category, room_id in ROOM_IDS.items():
                expected[room_id][key] = whole_eur(period[category][kind])
    horizon = {day.strftime("%Y%m%d") for day in each_day(start, end)}
    if covered != horizon:
        raise ValueError("Monthly periods do not cover the complete horizon")
    special_days = set()
    for window in config["specialWindows"]:
        a, b = (dt.date.fromisoformat(window[key]) for key in ("from", "to"))
        if b < a or a < start or b > end:
            raise ValueError("Invalid special window")
        for day in each_day(a, b):
            key = day.strftime("%Y%m%d")
            if key in special_days:
                raise ValueError("Overlapping special windows")
            special_days.add(key)
            for category, room_id in ROOM_IDS.items():
                expected[room_id][key] = whole_eur(window[category])
    for day in each_day(start, end):
        key = day.strftime("%Y%m%d")
        spreads = [row["eur"] for row in config["policy"]["superiorSpreads"]
                   if row["from"] <= day.isoformat() <= row["to"]]
        if len(spreads) != 1:
            raise ValueError("Missing or overlapping category-spread policy")
        if expected["674466"][key] - expected["674465"][key] != spreads[0]:
            raise ValueError("Price conflicts with approved category spread")
    if verify_approval and grid_digest(expected) != config["approval"]["gridSha256"]:
        raise ValueError("Grid differs from owner-approved amounts")
    return expected


def future_expected(config, today=None):
    today = today or dt.datetime.now(dt.timezone.utc).date()
    first = today.strftime("%Y%m%d")
    return {rid: {day: price for day, price in dates.items() if day >= first}
            for rid, dates in build_expected(config).items()}


def daily_price_setup(payload, room_id):
    room = payload[0] if isinstance(payload, list) and len(payload) == 1 else payload
    if not isinstance(room, dict) or str(room.get("roomId", room_id)) != str(room_id):
        raise ValueError("Invalid Daily Price room response")
    rows = room.get("dailyPrices")
    if not isinstance(rows, list):
        raise ValueError("Missing Daily Price rows")
    matches = [row for row in rows if isinstance(row, dict)
               and str(row.get("dailyPriceNumber", "1")) == "1"]
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous Daily Price 1")
    return matches[0]
