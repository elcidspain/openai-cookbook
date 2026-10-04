from __future__ import annotations

import json
import pathlib
import sys
import unittest


SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import beds24_serodes_direct_booking as booking  # noqa: E402


NOTES = "Direct booking, 2 dogs, paid 186 EUR, entered by AUMARA Web"


def rooms_payload(superior_qty: int = 2, extra_superior: bool = False) -> dict:
    superior_units = [
        {"id": index, "name": f"Superior {index}"} for index in range(1, superior_qty + 1)
    ]
    room_types = [
        {
            "id": 674465,
            "name": "Chalet",
            "qty": 4,
            "units": [{"id": index, "name": f"Chalet {index}"} for index in range(1, 5)],
        },
        {
            "id": 674466,
            "name": "Superior Chalet",
            "qty": superior_qty,
            "units": superior_units,
        },
    ]
    if extra_superior:
        room_types.append({"id": 674499, "name": "Superior Annex", "qty": 1, "units": [{"id": 1, "name": "Annex"}]})
    return {"data": [{"id": 324882, "name": "AUMARA", "roomTypes": room_types}]}


def unit_bookings(counts: dict[str, int], room_id: int = 674466, qty: int = 2) -> dict:
    return {
        "data": [
            {
                "roomId": room_id,
                "propertyId": 324882,
                "name": "Superior Chalet",
                "qty": qty,
                "unitBookings": {"2026-10-10": counts},
            },
            {
                "roomId": 674465,
                "propertyId": 324882,
                "name": "Chalet",
                "qty": 4,
                "unitBookings": {"2026-10-10": {"1": 0, "2": 0, "3": 0, "4": 0, "unassigned": 0}},
            },
        ]
    }


def availability(superior: bool = True, room_id: int = 674466) -> dict:
    return {
        "data": [
            {"roomId": 674465, "availability": {"2026-10-10": True}},
            {"roomId": room_id, "availability": {"2026-10-10": superior}},
        ]
    }


def calendar(num_avail: int = 1, room_id: int = 674466) -> dict:
    return {
        "data": [
            {"roomId": 674465, "calendar": [{"from": "2026-10-10", "to": "2026-10-10", "numAvail": 3}]},
            {"roomId": room_id, "calendar": [{"from": "2026-10-10", "to": "2026-10-10", "numAvail": num_avail}]},
        ]
    }


def alejandro(unit_id: int = 1) -> dict:
    return {
        "id": 88001,
        "propertyId": 324882,
        "roomId": 674466,
        "unitId": unit_id,
        "status": "confirmed",
        "arrival": "2026-10-10",
        "departure": "2026-10-12",
        "firstName": "Alejandro",
        "lastName": "Borges",
        "channel": "airbnb",
        "numAdult": 2,
    }


class FakeTransport:
    def __init__(
        self,
        superior_qty: int = 2,
        counts: dict[str, int] | None = None,
        available: bool = True,
        num_avail: int = 1,
        bookings: list[dict] | None = None,
        reference: list[dict] | None = None,
        post_body: dict | None = None,
    ) -> None:
        self.posts: list[list[dict]] = []
        self.gets: list[str] = []
        self.superior_qty = superior_qty
        self.counts = counts if counts is not None else {"1": 1, "2": 0, "unassigned": 0}
        self.available = available
        self.num_avail = num_avail
        self.bookings = bookings if bookings is not None else [alejandro()]
        self.reference = reference or []
        self.post_body = post_body

    def get(self, path: str) -> dict:
        self.gets.append(path)
        if path.startswith("/properties"):
            return rooms_payload(self.superior_qty)
        if path.startswith("/inventory/rooms/unitBookings"):
            return unit_bookings(self.counts, qty=self.superior_qty)
        if path.startswith("/inventory/rooms/availability"):
            return availability(self.available)
        if path.startswith("/inventory/rooms/calendar"):
            return calendar(self.num_avail)
        if path.startswith("/bookings") and "apiReference=" in path:
            return {"data": self.reference}
        if path.startswith("/bookings") and "id=" in path:
            return {"data": self.reference}
        if path.startswith("/bookings"):
            return {"data": self.bookings}
        raise AssertionError(path)

    def post_booking(self, payload: list[dict]) -> dict:
        self.posts.append(payload)
        if self.post_body is not None:
            return self.post_body
        self.reference = [
            {
                "id": 99001,
                "propertyId": 324882,
                "roomId": payload[0]["roomId"],
                "unitId": payload[0]["unitId"],
                "status": "confirmed",
                "arrival": "2026-10-10",
                "departure": "2026-10-11",
                "numAdult": 2,
                "numChild": 0,
                "price": 186,
                "deposit": 186,
                "notes": NOTES,
                "channel": "direct",
                "apiReference": booking.API_REFERENCE,
                "invoiceItems": [
                    {"type": "charge", "qty": 1, "amount": 186},
                    {"type": "payment", "qty": 1, "amount": 186},
                ],
            }
        ]
        return {"success": True, "booking": {"id": 99001}}


class SerodesBookingTests(unittest.TestCase):
    def test_source_never_sends_guest_messages(self) -> None:
        source = (SCRIPTS / "beds24_serodes_direct_booking.py").read_text(encoding="utf-8")
        self.assertNotIn("/bookings/messages", source)
        self.assertIn('allowAutoAction": "disable"', source)
        self.assertIn('"notifyGuest": False', source)
        self.assertIn('"notifyHost": False', source)

    def test_creates_on_second_superior_unit(self) -> None:
        transport = FakeTransport()
        result = booking.execute(transport)
        self.assertEqual(result["outcome"], "created")
        self.assertEqual(result["bookingId"], 99001)
        self.assertEqual(result["roomId"], 674466)
        self.assertEqual(result["unitId"], 2)
        self.assertEqual(result["exitCode"], 0)
        self.assertFalse(result["guestMessagesSent"])
        self.assertEqual(len(transport.posts), 1)
        payload = transport.posts[0][0]
        self.assertEqual(payload["status"], "confirmed")
        self.assertEqual(payload["price"], 186)
        self.assertEqual(payload["deposit"], 186)
        self.assertEqual(payload["notes"], NOTES)
        self.assertEqual(payload["lastName"], "Serodes")
        self.assertEqual(payload["numAdult"], 2)
        self.assertEqual(payload["numChild"], 0)
        self.assertEqual(payload["channel"], "direct")
        self.assertEqual(payload["arrival"], "2026-10-10")
        self.assertEqual(payload["departure"], "2026-10-11")
        self.assertEqual(payload["unitId"], 2)
        self.assertFalse(payload["actions"]["notifyGuest"])
        self.assertFalse(payload["actions"]["notifyHost"])
        self.assertFalse(payload["actions"]["assignBooking"])
        self.assertTrue(payload["actions"]["checkAvailability"])
        self.assertEqual(payload["allowAutoAction"], "disable")
        self.assertNotIn("message", payload)
        self.assertNotIn("email", payload)
        self.assertNotIn("phone", payload)
        self.assertNotIn("comments", payload)
        self.assertEqual(payload["invoiceItems"][0]["amount"], 186)
        self.assertEqual(payload["invoiceItems"][1]["type"], "payment")
        unit_path = next(path for path in transport.gets if path.startswith("/inventory/rooms/unitBookings"))
        self.assertIn("startDate=2026-10-10", unit_path)
        self.assertIn("endDate=2026-10-11", unit_path)
        self.assertNotIn("endDate=2026-10-10", unit_path)
        guests = [
            item["occupyingGuests"]
            for item in result["units"]
            if item["roomId"] == 674466 and item["unitId"] == 1
        ]
        self.assertEqual(guests, [["Alejandro B."]])
        self.assertNotIn("Borges", json.dumps(result))

    def test_does_not_create_when_only_one_superior_unit_exists(self) -> None:
        transport = FakeTransport(superior_qty=1, counts={"1": 1, "unassigned": 0}, num_avail=0)
        result = booking.execute(transport)
        self.assertEqual(result["outcome"], "not_created")
        self.assertIsNone(result["bookingId"])
        self.assertEqual(result["superiorUnitCount"], 1)
        self.assertIn("only 1 Superior unit", result["reason"])
        self.assertIn("Superior Chalet unit 1", result["reason"])
        self.assertEqual(transport.posts, [])
        names = {(item["roomName"], item["unitId"], item["unitName"]) for item in result["units"]}
        self.assertIn(("Chalet", 1, "Chalet 1"), names)
        self.assertIn(("Chalet", 4, "Chalet 4"), names)
        self.assertIn(("Superior Chalet", 1, "Superior 1"), names)
        self.assertNotIn(("Superior Chalet", 2, "Superior 2"), names)

    def test_does_not_create_when_both_superior_units_are_taken(self) -> None:
        transport = FakeTransport(counts={"1": 1, "2": 1, "unassigned": 0}, num_avail=0, available=False)
        result = booking.execute(transport)
        self.assertEqual(result["outcome"], "not_created")
        self.assertIn("no free Superior unit", result["reason"])
        self.assertEqual(transport.posts, [])

    def test_does_not_create_when_unit_looks_free_but_num_avail_is_zero(self) -> None:
        transport = FakeTransport(counts={"1": 1, "2": 0, "unassigned": 0}, num_avail=0, available=True)
        result = booking.execute(transport)
        self.assertEqual(result["outcome"], "not_created")
        self.assertIn("numAvail", result["reason"])
        self.assertEqual(transport.posts, [])

    def test_does_not_create_when_availability_is_false(self) -> None:
        transport = FakeTransport(counts={"1": 0, "2": 0, "unassigned": 0}, available=False, num_avail=1)
        result = booking.execute(transport)
        self.assertEqual(result["outcome"], "not_created")
        self.assertIn("availability", result["reason"])
        self.assertEqual(transport.posts, [])

    def test_prefers_the_second_unit_when_both_are_free(self) -> None:
        transport = FakeTransport(counts={"1": 0, "2": 0, "unassigned": 0}, bookings=[], num_avail=2)
        result = booking.execute(transport)
        self.assertEqual(result["outcome"], "created")
        self.assertEqual(result["unitId"], 2)
        self.assertEqual(transport.posts[0][0]["unitId"], 2)

    def test_reuses_existing_api_reference_without_posting(self) -> None:
        existing = {
            "id": 77001,
            "roomId": 674466,
            "unitId": 2,
            "status": "confirmed",
            "arrival": "2026-10-10",
            "departure": "2026-10-11",
            "price": 186,
            "deposit": 186,
            "notes": NOTES,
            "apiReference": booking.API_REFERENCE,
        }
        transport = FakeTransport(reference=[existing])
        result = booking.execute(transport)
        self.assertEqual(result["outcome"], "reused")
        self.assertEqual(result["bookingId"], 77001)
        self.assertEqual(transport.posts, [])

    def test_uses_the_other_free_superior_unit_when_the_second_is_taken(self) -> None:
        transport = FakeTransport(
            counts={"1": 0, "2": 1, "unassigned": 0},
            bookings=[alejandro(unit_id=2)],
            num_avail=1,
        )
        result = booking.execute(transport)
        self.assertEqual(result["outcome"], "created")
        self.assertEqual(result["unitId"], 1)
        self.assertEqual(transport.posts[0][0]["unitId"], 1)

    def test_rejects_a_payload_that_would_notify(self) -> None:
        payload = booking.build_payload({"roomId": 674466, "unitId": 2, "roomName": "Superior", "unitName": ""})
        payload[0]["actions"]["notifyGuest"] = True
        with self.assertRaises(booking.BookingError):
            booking.assert_silent(payload)

    def test_missing_night_is_not_treated_as_free(self) -> None:
        transport = FakeTransport()
        original = transport.get

        def get(path: str) -> dict:
            body = original(path)
            if path.startswith("/inventory/rooms/unitBookings"):
                for row in body["data"]:
                    if row["roomId"] == 674466:
                        row["unitBookings"] = {}
            return body

        transport.get = get  # type: ignore[method-assign]
        result = booking.execute(transport)
        self.assertEqual(result["outcome"], "not_created")
        self.assertIn("occupancy was not returned", result["reason"])
        self.assertEqual(transport.posts, [])

    def test_run_flag_blocks_live_execution(self) -> None:
        self.assertNotEqual(__import__("os").environ.get(booking.RUN_FLAG), "1")


if __name__ == "__main__":
    unittest.main()
