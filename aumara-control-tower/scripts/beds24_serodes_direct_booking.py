#!/usr/bin/env python3
"""Enter one direct AUMARA booking for Serodes, or leave Beds24 unchanged.

The live path runs only when AUMARA_SERODES_DIRECT_BOOKING=1. It reuses the
bookings-snapshot token exchange (BEDS24_REFRESH_CREDENTIAL) and then:

1. reads rooms and units for property 324882;
2. reads availability, calendar numAvail, and unit bookings for 2026-10-10;
3. creates one confirmed booking on a free Superior unit when at least two
   Superior units are configured and one is free that night.

The second Superior unit is preferred. Guest messages, host notifications, and
auto actions are disabled. This script never posts to the guest-message API.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import beds24_bookings_snapshot as snapshot  # noqa: E402


PROPERTY_ID = 324882
SUPERIOR_ROOM_ID = 674466
ARRIVAL = "2026-10-10"
DEPARTURE = "2026-10-11"
NIGHT = ARRIVAL
# unitBookings rejects endDate == startDate ("cannot be earlier than startDate").
INVENTORY_END = DEPARTURE
API_REFERENCE = "AUMARA-SERODES-20261010-186"
LAST_NAME = "Serodes"
ADULTS = 2
CHILDREN = 0
PRICE = 186
NOTES = "Direct booking, 2 dogs, paid 186 EUR, entered by AUMARA Web"
RUN_FLAG = "AUMARA_SERODES_DIRECT_BOOKING"
OCCUPYING = {"confirmed", "request", "new", "black"}
ACTIVE = OCCUPYING


class BookingError(RuntimeError):
    """A Beds24 read or write failed closed."""


def query(path: str, params: list[tuple[str, str]]) -> str:
    return path + "?" + urllib.parse.urlencode(params)


def is_superior(room_id: int, name: str) -> bool:
    if room_id == SUPERIOR_ROOM_ID:
        return True
    return "superior" in name.casefold()


def unit_records(room: dict[str, Any]) -> list[dict[str, Any]]:
    """Return configured units. qty fills any ids the name list omits."""
    named: list[dict[str, Any]] = []
    raw_units = room.get("units")
    if isinstance(raw_units, list):
        for item in raw_units:
            if not isinstance(item, dict):
                continue
            unit_id = snapshot.as_id(item.get("id") or item.get("unitId"))
            if unit_id is None:
                continue
            named.append(
                {
                    "unitId": unit_id,
                    "unitName": snapshot.one_line(str(item.get("name") or "")),
                }
            )
    qty = snapshot.as_int(room.get("qty") or room.get("physicalUnits") or 0, 0)
    known = {item["unitId"] for item in named}
    if qty > len(named):
        for unit_id in range(1, qty + 1):
            if unit_id not in known:
                named.append({"unitId": unit_id, "unitName": ""})
    if not named and qty < 1:
        named.append({"unitId": 1, "unitName": ""})
    named.sort(key=lambda item: int(item["unitId"]))
    return named


def parse_rooms(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rooms: list[dict[str, Any]] = []
    for row in rows:
        if snapshot.as_id(row.get("id") or row.get("propertyId")) != PROPERTY_ID:
            continue
        raw_rooms = row.get("roomTypes") or row.get("rooms") or []
        if not isinstance(raw_rooms, list):
            continue
        for room in raw_rooms:
            if not isinstance(room, dict):
                continue
            room_id = snapshot.as_id(room.get("id") or room.get("roomId"))
            if room_id is None:
                continue
            name = snapshot.one_line(str(room.get("name") or f"room {room_id}"))
            rooms.append(
                {
                    "roomId": room_id,
                    "roomName": name,
                    "qty": snapshot.as_int(room.get("qty") or 0, 0),
                    "superior": is_superior(room_id, name),
                    "units": unit_records(room),
                }
            )
    rooms.sort(key=lambda item: (item["roomName"].casefold(), item["roomId"]))
    return rooms


def night_map(row: dict[str, Any]) -> dict[str, Any] | None:
    """Return the night's unit counts. None means that date was not in the payload."""
    bookings = row.get("unitBookings")
    if not isinstance(bookings, dict) or NIGHT not in bookings:
        return None
    night = bookings.get(NIGHT)
    return night if isinstance(night, dict) else None


def index_unit_bookings(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    indexed: dict[int, dict[str, Any]] = {}
    for row in rows:
        room_id = snapshot.as_id(row.get("roomId"))
        if room_id is None:
            continue
        indexed[room_id] = row
    return indexed


def availability_on(rows: list[dict[str, Any]], room_id: int) -> bool | None:
    for row in rows:
        if snapshot.as_id(row.get("roomId")) != room_id:
            continue
        availability = row.get("availability")
        if isinstance(availability, dict) and NIGHT in availability:
            return bool(availability[NIGHT])
        return None
    return None


def covers_night(item: dict[str, Any]) -> bool:
    start = snapshot.parse_date(item.get("from"))
    end = snapshot.parse_date(item.get("to"))
    night = snapshot.parse_date(NIGHT)
    if start is None or end is None or night is None:
        return False
    return start <= night <= end


def num_avail_on(rows: list[dict[str, Any]], room_id: int) -> int | None:
    for row in rows:
        if snapshot.as_id(row.get("roomId")) != room_id:
            continue
        calendar = row.get("calendar")
        if not isinstance(calendar, list):
            return None
        for item in calendar:
            if isinstance(item, dict) and covers_night(item) and "numAvail" in item:
                return snapshot.as_int(item.get("numAvail"), 0)
        return None
    return None


def overlaps_night(row: dict[str, Any]) -> bool:
    arrival = snapshot.parse_date(row.get("arrival"))
    departure = snapshot.parse_date(row.get("departure"))
    night = snapshot.parse_date(NIGHT)
    status = str(row.get("status") or "").strip().lower()
    if arrival is None or departure is None or night is None:
        return False
    return status in OCCUPYING and arrival <= night < departure


def booking_label(row: dict[str, Any]) -> str:
    return snapshot.guest_label(str(row.get("firstName") or ""), str(row.get("lastName") or ""))


def public_units(
    rooms: list[dict[str, Any]],
    unit_rows: dict[int, dict[str, Any]],
    occupants: dict[tuple[int, int | None], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []
    for room in rooms:
        room_id = int(room["roomId"])
        night = night_map(unit_rows[room_id]) if room_id in unit_rows else None
        for unit in room["units"]:
            unit_id = int(unit["unitId"])
            count: int | None
            if night is None:
                count = None
            else:
                count = snapshot.as_int(night.get(str(unit_id), night.get(unit_id, 0)), 0)
            assigned = occupants.get((room_id, unit_id), [])
            report.append(
                {
                    "roomId": room_id,
                    "roomName": room["roomName"],
                    "superior": bool(room["superior"]),
                    "unitId": unit_id,
                    "unitName": unit["unitName"],
                    "night": NIGHT,
                    "unitBookings": count,
                    "occupyingBookingIds": [item["bookingId"] for item in assigned],
                    "occupyingGuests": [item["guestLabel"] for item in assigned],
                }
            )
        if night is not None and snapshot.as_int(night.get("unassigned"), 0) > 0:
            report.append(
                {
                    "roomId": room_id,
                    "roomName": room["roomName"],
                    "superior": bool(room["superior"]),
                    "unitId": None,
                    "unitName": "unassigned",
                    "night": NIGHT,
                    "unitBookings": snapshot.as_int(night.get("unassigned"), 0),
                    "occupyingBookingIds": [
                        item["bookingId"] for item in occupants.get((room_id, None), [])
                    ],
                    "occupyingGuests": [
                        item["guestLabel"] for item in occupants.get((room_id, None), [])
                    ],
                }
            )
    return report


def superior_units(rooms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chosen: list[dict[str, Any]] = []
    for room in sorted(rooms, key=lambda item: int(item["roomId"])):
        if not room["superior"]:
            continue
        for unit in room["units"]:
            chosen.append(
                {
                    "roomId": int(room["roomId"]),
                    "roomName": room["roomName"],
                    "unitId": int(unit["unitId"]),
                    "unitName": unit["unitName"],
                }
            )
    return chosen


def room_can_sell(
    room_id: int,
    availability_rows: list[dict[str, Any]],
    calendar_rows: list[dict[str, Any]],
) -> tuple[bool, str]:
    available = availability_on(availability_rows, room_id)
    if available is None:
        return False, f"availability for room {room_id} on {NIGHT} was not returned"
    if not available:
        return False, f"room {room_id} availability on {NIGHT} is false"
    remaining = num_avail_on(calendar_rows, room_id)
    if remaining is None:
        return False, f"numAvail for room {room_id} on {NIGHT} was not returned"
    if remaining < 1:
        return False, f"room {room_id} numAvail on {NIGHT} is {remaining}"
    return True, ""


def choose_unit(
    rooms: list[dict[str, Any]],
    unit_rows: dict[int, dict[str, Any]],
    availability_rows: list[dict[str, Any]],
    calendar_rows: list[dict[str, Any]],
    occupants: dict[tuple[int, int | None], list[dict[str, Any]]],
) -> dict[str, Any]:
    """Pick the second Superior unit when it is free. Otherwise another free one."""
    superior = superior_units(rooms)
    if len(superior) < 2:
        names = [
            f"{item['roomName']} unit {item['unitId']}" + (f" ({item['unitName']})" if item["unitName"] else "")
            for item in superior
        ] or ["none"]
        return {
            "create": False,
            "reason": (
                f"no free Superior unit: only {len(superior)} Superior unit(s) configured "
                f"({', '.join(names)})"
            ),
        }

    def count_for(item: dict[str, Any]) -> int | None:
        row = unit_rows.get(item["roomId"])
        if row is None:
            return None
        night = night_map(row)
        if night is None:
            return None
        unit_id = item["unitId"]
        raw = night.get(str(unit_id), night.get(unit_id, 0))
        return snapshot.as_int(raw, 0)

    def conflict(item: dict[str, Any], count: int) -> bool:
        assigned = occupants.get((item["roomId"], item["unitId"]), [])
        return count == 0 and len(assigned) > 0

    preferred = superior[1]
    candidates = [preferred] + [item for item in superior if item is not preferred]
    blockers: list[str] = []
    for item in candidates:
        count = count_for(item)
        label = f"{item['roomName']} unit {item['unitId']}"
        if count is None:
            blockers.append(f"{label} occupancy was not returned")
            continue
        if count > 0:
            blockers.append(f"{label} has {count} unit booking(s) on {NIGHT}")
            continue
        if conflict(item, count):
            blockers.append(f"{label} is already occupied by a booking on {NIGHT}")
            continue
        sellable, why = room_can_sell(item["roomId"], availability_rows, calendar_rows)
        if not sellable:
            blockers.append(why)
            continue
        return {"create": True, "unit": item, "reason": ""}
    return {
        "create": False,
        "reason": "no free Superior unit on " + NIGHT + ": " + "; ".join(blockers),
    }


def build_payload(unit: dict[str, Any]) -> list[dict[str, Any]]:
    payload = [
        {
            "roomId": unit["roomId"],
            "unitId": unit["unitId"],
            "status": "confirmed",
            "arrival": ARRIVAL,
            "departure": DEPARTURE,
            "numAdult": ADULTS,
            "numChild": CHILDREN,
            "lastName": LAST_NAME,
            "channel": "direct",
            "apiReference": API_REFERENCE,
            "allowChannelUpdate": "none",
            "allowAutoAction": "disable",
            "price": PRICE,
            "deposit": PRICE,
            "notes": NOTES,
            "actions": {
                "notifyGuest": False,
                "notifyHost": False,
                "assignBooking": False,
                "checkAvailability": True,
                "allowWebhooks": True,
                "autoInvoiceItemCharge": False,
            },
            "invoiceItems": [
                {
                    "type": "charge",
                    "description": "Direct stay",
                    "qty": 1,
                    "amount": PRICE,
                },
                {
                    "type": "payment",
                    "description": "Paid 186 EUR",
                    "qty": 1,
                    "amount": PRICE,
                },
            ],
        }
    ]
    assert_silent(payload)
    return payload


def assert_silent(payload: list[dict[str, Any]]) -> None:
    item = payload[0]
    actions = item.get("actions") or {}
    if item.get("message") or item.get("email") or item.get("phone") or item.get("mobile"):
        raise BookingError("refusing a payload that contains a guest message or contact")
    if actions.get("notifyGuest") is not False or actions.get("notifyHost") is not False:
        raise BookingError("refusing a payload that notifies the guest or host")
    if item.get("allowAutoAction") != "disable":
        raise BookingError("refusing a payload that leaves auto actions enabled")
    if "comments" in item:
        raise BookingError("refusing a payload that sets guest comments")


def active_reference(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    matches = [
        row
        for row in rows
        if str(row.get("apiReference") or "") == API_REFERENCE
        and str(row.get("status") or "").strip().lower() in ACTIVE
    ]
    if not matches:
        cancelled = [
            row
            for row in rows
            if str(row.get("apiReference") or "") == API_REFERENCE
        ]
        if cancelled:
            booking_id = snapshot.as_id(cancelled[0].get("id"))
            raise BookingError(
                f"apiReference {API_REFERENCE} belongs to booking {booking_id} "
                f"with status {cancelled[0].get('status')}; not creating another"
            )
        return None
    if len(matches) > 1:
        raise BookingError(f"apiReference {API_REFERENCE} matched {len(matches)} active bookings")
    return matches[0]


def result_base(rooms_report: list[dict[str, Any]], superior_count: int) -> dict[str, Any]:
    return {
        "schema": "aumara.serodes-direct-booking.v1",
        "propertyId": PROPERTY_ID,
        "arrival": ARRIVAL,
        "departure": DEPARTURE,
        "apiReference": API_REFERENCE,
        "guestMessagesSent": False,
        "autoActions": "disable",
        "notifyGuest": False,
        "notifyHost": False,
        "superiorUnitCount": superior_count,
        "units": rooms_report,
        "secretExposed": False,
    }


def describe_existing(row: dict[str, Any], base: dict[str, Any], outcome: str) -> dict[str, Any]:
    base.update(
        {
            "outcome": outcome,
            "reason": "",
            "bookingId": snapshot.as_id(row.get("id")),
            "roomId": snapshot.as_id(row.get("roomId")),
            "unitId": snapshot.as_id(row.get("unitId")),
            "status": row.get("status"),
            "price": snapshot.as_float(row.get("price")),
            "deposit": snapshot.as_float(row.get("deposit")),
            "notes": row.get("notes"),
            "exitCode": 0,
        }
    )
    return base


def paid_amount(row: dict[str, Any], kind: str) -> float:
    total = 0.0
    for item in row.get("invoiceItems") or []:
        if not isinstance(item, dict) or item.get("type") != kind:
            continue
        total += snapshot.as_float(item.get("amount")) * snapshot.as_int(item.get("qty") or 1, 1)
    return total


def verify_created(row: dict[str, Any], unit: dict[str, Any]) -> None:
    problems: list[str] = []
    if snapshot.as_id(row.get("roomId")) != unit["roomId"]:
        problems.append(f"roomId {row.get('roomId')}")
    if snapshot.as_id(row.get("unitId")) != unit["unitId"]:
        problems.append(f"unitId {row.get('unitId')}")
    if str(row.get("status") or "").strip().lower() != "confirmed":
        problems.append(f"status {row.get('status')}")
    if str(row.get("arrival") or "")[:10] != ARRIVAL or str(row.get("departure") or "")[:10] != DEPARTURE:
        problems.append("dates")
    if str(row.get("notes") or "") != NOTES:
        problems.append("notes")
    if snapshot.as_int(row.get("numAdult"), -1) != ADULTS:
        problems.append("adults")
    price_ok = snapshot.as_float(row.get("price")) == PRICE or paid_amount(row, "charge") == PRICE
    paid_ok = snapshot.as_float(row.get("deposit")) == PRICE or paid_amount(row, "payment") == PRICE
    if not price_ok:
        problems.append(f"price {row.get('price')}")
    if not paid_ok:
        problems.append(f"deposit {row.get('deposit')}")
    if problems:
        raise BookingError(
            "booking "
            + str(row.get("id"))
            + " was created but readback mismatched: "
            + ", ".join(problems)
        )


def post_errors(body: Any) -> list[str]:
    messages: list[str] = []
    rows = body if isinstance(body, list) else [body]
    for row in rows:
        if not isinstance(row, dict):
            continue
        for item in row.get("errors") or []:
            if isinstance(item, dict) and item.get("message"):
                messages.append(str(item["message"]))
        if row.get("success") is False and not messages:
            messages.append("Beds24 rejected the booking")
    return messages


def created_id(body: Any) -> int | None:
    rows = body if isinstance(body, list) else [body]
    for row in rows:
        if not isinstance(row, dict):
            continue
        booking = row.get("booking")
        if isinstance(booking, dict) and snapshot.as_id(booking.get("id")):
            return snapshot.as_id(booking.get("id"))
        if snapshot.as_id(row.get("id")):
            return snapshot.as_id(row.get("id"))
    return None


def paged(transport: Any, path: str, params: list[tuple[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page in range(1, 11):
        query_params = list(params)
        if page > 1:
            query_params.append(("page", str(page)))
        body = transport.get(query(path, query_params))
        rows.extend(snapshot.data_rows(body, path))
        pages = body.get("pages") if isinstance(body, dict) else None
        if not (isinstance(pages, dict) and pages.get("nextPageExists")):
            return rows
    raise BookingError(f"GET {path} exceeded 10 pages")


def execute(transport: Any) -> dict[str, Any]:
    reference_rows = paged(
        transport,
        "/bookings",
        [
            ("apiReference", API_REFERENCE),
            ("includeInvoiceItems", "true"),
            ("status", "confirmed"),
            ("status", "request"),
            ("status", "new"),
            ("status", "black"),
            ("status", "cancelled"),
        ],
    )
    property_rows = paged(
        transport,
        "/properties",
        [
            ("id", str(PROPERTY_ID)),
            ("includeAllRooms", "true"),
            ("includeUnitDetails", "true"),
        ],
    )
    rooms = parse_rooms(property_rows)
    if not rooms:
        raise BookingError(f"property {PROPERTY_ID} returned no rooms")
    unit_rows = index_unit_bookings(
        paged(
            transport,
            "/inventory/rooms/unitBookings",
            [
                ("propertyId", str(PROPERTY_ID)),
                ("startDate", NIGHT),
                ("endDate", INVENTORY_END),
            ],
        )
    )
    availability_rows = paged(
        transport,
        "/inventory/rooms/availability",
        [
            ("propertyId", str(PROPERTY_ID)),
            ("startDate", NIGHT),
            ("endDate", INVENTORY_END),
        ],
    )
    calendar_rows = paged(
        transport,
        "/inventory/rooms/calendar",
        [
            ("propertyId", str(PROPERTY_ID)),
            ("startDate", NIGHT),
            ("endDate", INVENTORY_END),
            ("includeNumAvail", "true"),
        ],
    )
    booking_rows = paged(
        transport,
        "/bookings",
        [
            ("propertyId", str(PROPERTY_ID)),
            ("arrivalTo", DEPARTURE),
            ("departureFrom", NIGHT),
            ("status", "confirmed"),
            ("status", "request"),
            ("status", "new"),
            ("status", "black"),
        ],
    )
    occupants: dict[tuple[int, int | None], list[dict[str, Any]]] = {}
    for row in booking_rows:
        if not overlaps_night(row):
            continue
        room_id = snapshot.as_id(row.get("roomId"))
        if room_id is None:
            continue
        key = (room_id, snapshot.as_id(row.get("unitId")))
        occupants.setdefault(key, []).append(
            {
                "bookingId": snapshot.as_id(row.get("id")),
                "guestLabel": booking_label(row),
            }
        )
    report = public_units(rooms, unit_rows, occupants)
    base = result_base(report, len(superior_units(rooms)))
    try:
        existing = active_reference(reference_rows)
    except BookingError as exc:
        base.update(
            {
                "outcome": "not_created",
                "reason": str(exc),
                "bookingId": None,
                "roomId": None,
                "unitId": None,
                "exitCode": 1,
            }
        )
        return base
    if existing is not None:
        found = describe_existing(existing, base, "reused")
        found["reason"] = f"apiReference {API_REFERENCE} already has booking {found['bookingId']}"
        return found

    decision = choose_unit(rooms, unit_rows, availability_rows, calendar_rows, occupants)
    if not decision["create"]:
        base.update(
            {
                "outcome": "not_created",
                "reason": decision["reason"],
                "bookingId": None,
                "roomId": None,
                "unitId": None,
                "exitCode": 0,
            }
        )
        return base

    unit = decision["unit"]
    payload = build_payload(unit)
    created = transport.post_booking(payload)
    if post_errors(created):
        raise BookingError("Beds24 did not create the booking: " + "; ".join(post_errors(created)))
    booking_id = created_id(created)
    if booking_id is None:
        reread = paged(
            transport,
            "/bookings",
            [("apiReference", API_REFERENCE), ("includeInvoiceItems", "true")],
        )
        existing = active_reference(reread)
        if existing is None:
            raise BookingError("POST /bookings did not return a booking id")
        booking_id = snapshot.as_id(existing.get("id"))
    readback_rows = paged(
        transport,
        "/bookings",
        [("id", str(booking_id)), ("includeInvoiceItems", "true")],
    )
    readback = next((row for row in readback_rows if snapshot.as_id(row.get("id")) == booking_id), None)
    if readback is None:
        raise BookingError(f"created booking {booking_id} could not be read back")
    verify_created(readback, unit)
    confirmed = describe_existing(readback, base, "created")
    confirmed["roomName"] = unit["roomName"]
    confirmed["unitName"] = unit["unitName"]
    confirmed["reason"] = f"created booking {booking_id} on {unit['roomName']} unit {unit['unitId']}"
    return confirmed


class LiveTransport:
    """GET via the snapshot client, plus one POST /bookings."""

    def __init__(self, api_base: str, token: str, opener: Any, secrets: tuple[str, ...]) -> None:
        self.client = snapshot.GetClient(api_base, token, opener, secrets)
        self.api_base = api_base.rstrip("/")
        self.token = token
        self.opener = opener
        self.secrets = secrets

    def get(self, path: str) -> Any:
        if path.split("?", 1)[0].endswith("/messages"):
            raise BookingError("refusing to read or send guest messages")
        return snapshot.interpret_get(self.client, path)

    def post_booking(self, payload: list[dict[str, Any]]) -> Any:
        assert_silent(payload)
        url = self.api_base + "/bookings"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "token": self.token,
                "User-Agent": "AUMARA-SerodesDirectBooking/1",
            },
        )
        try:
            with self.opener(request, timeout=60) as response:
                status = int(getattr(response, "status", 200))
                raw = response.read()
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            raw = exc.read()
        except urllib.error.URLError as exc:
            raise BookingError(f"POST /bookings failed: {exc.reason}") from exc
        decoded = raw.decode("utf-8", "replace")
        text = snapshot.scrub_raw(decoded, self.secrets)
        try:
            body = json.loads(decoded) if decoded else {}
        except json.JSONDecodeError:
            body = {"error": text}
        if 200 <= status < 300:
            print(
                f"beds24_api POST /bookings HTTP {status} bookingId={created_id(body)}",
                file=sys.stderr,
            )
        else:
            print(
                "beds24_api POST /bookings HTTP "
                + str(status)
                + " "
                + snapshot.verbatim_body(body, self.secrets, text),
                file=sys.stderr,
            )
            raise BookingError(
                "POST /bookings HTTP "
                + str(status)
                + ": "
                + snapshot.verbatim_body(body, self.secrets, text)
            )
        return body


def live_transport() -> LiveTransport:
    credential, source = snapshot.credential_from_env()
    if not credential:
        raise BookingError(f"{source} is missing")
    token, base = snapshot.exchange_token(urllib.request.urlopen, credential)
    return LiveTransport(base, token, urllib.request.urlopen, (credential, token))


def public_result(result: dict[str, Any]) -> dict[str, Any]:
    hidden = {"lastName", "email", "phone", "mobile", "message", "token", "refreshToken"}
    return {key: value for key, value in result.items() if key not in hidden}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Enter the Serodes direct booking once")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = Path(args.output)
    if os.environ.get(RUN_FLAG) != "1":
        result = public_result(
            {
                "schema": "aumara.serodes-direct-booking.v1",
                "outcome": "not_created",
                "reason": f"{RUN_FLAG} is not 1",
                "guestMessagesSent": False,
                "exitCode": 2,
                "secretExposed": False,
            }
        )
    else:
        try:
            result = public_result(execute(live_transport()))
        except (BookingError, snapshot.SnapshotError) as exc:
            result = public_result(
                {
                    "schema": "aumara.serodes-direct-booking.v1",
                    "outcome": "not_created",
                    "reason": snapshot.one_line(str(exc)),
                    "guestMessagesSent": False,
                    "bookingId": None,
                    "exitCode": 1,
                    "secretExposed": False,
                }
            )
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return int(result.get("exitCode", 1))


if __name__ == "__main__":
    sys.exit(main())
