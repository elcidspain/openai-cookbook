from __future__ import annotations

import datetime as dt
import pathlib
import sys
import unittest


SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import beds24_cot_note_sync as worker  # noqa: E402


LIVE_ENV = {
    "BEDS24_COT_NOTE_MODE": "live",
    "AUMARA_DISABLE_BOOKING_MUTATIONS": "false",
    "AUMARA_LIVE_BOOKING_WRITES_CONFIRMED": "true",
    "AUMARA_BEDS24_COT_WRITE_CONFIRMATION": worker.LIVE_CONFIRMATION,
    "BEDS24_COT_NOTE_MAX_WRITES": "1",
}


def victor_group():
    shared = {
        "propertyId": worker.PROPERTY_ID,
        "roomId": worker.TWIN_ROOM_ID,
        "status": "confirmed",
        "masterId": 89946081,
        "guestComments": (
            "En la triple una cuna que tendrá 8 meses mi hija, gracias. "
            "Habitaciones juntas y no fumadores."
        ),
        "infoItems": [],
    }
    return [
        {
            **shared,
            "id": 89946081,
            "numAdult": 2,
            "numChild": 1,
        },
        {
            **shared,
            "id": 89946083,
            "numAdult": 2,
            "numChild": 0,
        },
    ]


class FakeClient:
    def __init__(self, bookings, *, post_success=True):
        self.bookings = bookings
        self.post_success = post_success
        self.get_requests = 0
        self.post_requests = 0
        self.posted = []

    def request_json(self, method, path, body=None):
        if method == "GET":
            self.get_requests += 1
            if path.startswith("/bookings?") and "id=" not in path:
                return 200, {"data": self.bookings}
            if path.startswith("/bookings?") and "id=" in path:
                return 200, {"data": self.bookings[:1]}
        if method == "POST":
            self.post_requests += 1
            self.posted.append(body)
            if not self.post_success:
                return 400, {"error": "rejected"}
            info_item = body[0]["infoItems"][0]
            self.bookings[0]["infoItems"] = [info_item]
            return 201, [{"success": True}]
        raise AssertionError(f"Unexpected request: {method} {path}")


class CotNoteSyncTests(unittest.TestCase):
    def test_regression_group_uses_actual_twin_and_ignores_triple_phrase(self):
        candidates, audit = worker.plan_cot_notes(victor_group())
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["bookingId"], 89946081)
        self.assertEqual(
            candidates[0]["text"],
            "BABY COT REQUIRED — PREPARE BEFORE ARRIVAL — "
            "Booking 89946081 — infant age 8 months.",
        )
        self.assertEqual(audit[0]["action"], "pending_write")

    def test_conflict_is_manual_when_adults_exceed_room_capacity(self):
        rows = victor_group()
        rows[0]["numAdult"] = 3
        candidates, audit = worker.plan_cot_notes(rows)
        self.assertEqual(candidates, [])
        self.assertEqual(audit[0]["action"], "manual_review")
        self.assertEqual(audit[0]["reason"], "room_or_occupancy_not_proved")

    def test_live_write_is_read_back_and_changes_only_infoitems(self):
        client = FakeClient(victor_group())
        report = worker.run(
            client,
            today=dt.date(2026, 7, 30),
            values=LIVE_ENV,
        )
        self.assertEqual(report["summary"]["notesWritten"], 1)
        self.assertEqual(report["summary"]["notesReadBackVerified"], 1)
        self.assertEqual(report["safety"]["bookingFieldsChanged"], ["infoItems"])
        self.assertEqual(report["safety"]["guestMessagesSent"], 0)
        self.assertEqual(client.post_requests, 1)

    def test_existing_note_is_idempotent(self):
        rows = victor_group()
        rows[0]["infoItems"] = [
            {
                "code": worker.NOTE_CODE,
                "text": (
                    "BABY COT REQUIRED — PREPARE BEFORE ARRIVAL — "
                    "Booking 89946081 — infant age 8 months."
                ),
            }
        ]
        client = FakeClient(rows)
        report = worker.run(
            client,
            today=dt.date(2026, 7, 30),
            values=LIVE_ENV,
        )
        self.assertEqual(report["summary"]["notesWritten"], 0)
        self.assertEqual(report["summary"]["duplicates"], 1)
        self.assertEqual(client.post_requests, 0)

    def test_live_guards_fail_closed(self):
        client = FakeClient(victor_group())
        with self.assertRaises(worker.CotNoteError):
            worker.run(
                client,
                today=dt.date(2026, 7, 30),
                values={**LIVE_ENV, "BEDS24_COT_NOTE_MAX_WRITES": "2"},
            )
        self.assertEqual(client.post_requests, 0)


if __name__ == "__main__":
    unittest.main()
