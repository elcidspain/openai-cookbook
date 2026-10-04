from __future__ import annotations

import datetime as dt
import io
import os
import pathlib
import sys
import unittest
import urllib.error

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import beds24_bookings_snapshot as snapshot  # noqa: E402


NOW = dt.datetime(2026, 10, 4, 6, 7, tzinfo=dt.timezone.utc)
SOURCE = (SCRIPTS / "beds24_bookings_snapshot.py").read_text(encoding="utf-8")


class FakeClient:
    def __init__(self, messages_status: int = 200) -> None:
        self.paths: list[str] = []
        self.messages_status = messages_status

    def get_json(self, path: str) -> tuple[int, object]:
        self.paths.append(path)
        if path.startswith("/properties"):
            return 200, {
                "data": [
                    {
                        "id": 324882,
                        "name": "AUMARA",
                        "roomTypes": [
                            {"id": 674465, "name": "Chalet", "qty": 4},
                            {"id": 674466, "name": "Superior Chalet", "qty": 2},
                        ],
                    },
                    {
                        "id": 324903,
                        "name": "EL CID",
                        "roomTypes": [
                            {"id": 674484, "name": "Triple Room", "qty": 1},
                            {"id": 674485, "name": "Twin Room with Terrace", "qty": 4},
                            {"id": 674486, "name": "Studio", "qty": 1},
                        ],
                    },
                ]
            }
        if path.startswith("/bookings/messages"):
            if self.messages_status != 200:
                return self.messages_status, {"error": "Scope required", "code": self.messages_status}
            if "source=guest" in path:
                return 200, {
                    "data": [
                        {
                            "id": 1,
                            "bookingId": 90522148,
                            "propertyId": 324882,
                            "source": "guest",
                            "time": "2026-10-04T04:00:00Z",
                            "message": "Позвоните +34 612 345 678 email guest@example.com " + ("я" * 250),
                            "guestEmail": "guest@example.com",
                        },
                        {
                            "id": 2,
                            "bookingId": 90522149,
                            "source": "guest",
                            "time": "2026-10-04T05:00:00Z",
                            "message": "Это уже ответили",
                        },
                    ]
                }
            return 200, {
                "data": [
                    {
                        "id": 3,
                        "bookingId": 90522149,
                        "source": "host",
                        "time": "2026-10-04T05:30:00Z",
                        "message": "Ответ хозяина",
                    }
                ]
            }
        if path.startswith("/bookings") and "modifiedFrom=" in path:
            return 200, {"data": []}
        if path.startswith("/bookings") and "id=" in path:
            return 200, {
                "data": [
                    {
                        "id": 90522148,
                        "propertyId": 324882,
                        "firstName": "Anna",
                        "lastName": "Kowalski",
                        "email": "guest@example.com",
                        "phone": "+34 612 345 678",
                        "channel": "booking",
                    },
                    {
                        "id": 90522149,
                        "propertyId": 324882,
                        "firstName": "Olga",
                        "lastName": "Ivanova",
                        "channel": "airbnb",
                    },
                ]
            }
        if path.startswith("/bookings") and "propertyId=324882" in path:
            return 200, {
                "data": [
                    {
                        "id": 1001,
                        "propertyId": 324882,
                        "roomId": 674465,
                        "status": "confirmed",
                        "arrival": "2026-10-12",
                        "departure": "2026-10-15",
                        "numAdult": 2,
                        "firstName": "Anna",
                        "lastName": "Kowalski",
                        "email": "guest@example.com",
                        "phone": "+34 612 345 678",
                        "price": 300,
                        "currency": "EUR",
                        "apiSource": "19",
                        "referer": "Booking.com",
                        "bookingTime": "2026-10-04T05:00:00Z",
                    },
                    {
                        "id": 1002,
                        "propertyId": 324882,
                        "roomId": 674466,
                        "status": "cancelled",
                        "arrival": "2026-10-20",
                        "departure": "2026-10-22",
                        "numAdult": 1,
                        "firstName": "Luis",
                        "lastName": "Martinez",
                        "price": 80,
                        "referer": "Airbnb",
                        "apiSource": "46",
                        "cancelTime": "2026-10-04T02:00:00Z",
                    },
                ]
            }
        if path.startswith("/bookings"):
            return 200, {"data": []}
        return 404, {"error": "unexpected path"}


class SnapshotTests(unittest.TestCase):
    def test_module_allows_get_only(self) -> None:
        for banned in ("POST", "PUT", "PATCH", "DELETE"):
            self.assertNotIn(banned, SOURCE)
        request = snapshot.build_get_request("https://api.beds24.com/v2/bookings", {})
        self.assertEqual(request.method, "GET")
        self.assertIsNone(request.data)

    def test_seed_file_and_privacy(self) -> None:
        stays = snapshot.load_manual(snapshot.DEFAULT_MANUAL)
        self.assertEqual(len(stays), 1)
        stay = stays[0]
        self.assertEqual(stay.guest_label, "Serodes")
        self.assertEqual(stay.property_id, 324882)
        self.assertIsNone(stay.room_id)
        self.assertEqual(stay.arrival.isoformat(), "2026-10-10")
        self.assertEqual(stay.departure.isoformat(), "2026-10-11")
        self.assertEqual((stay.departure - stay.arrival).days, 1)
        self.assertEqual(stay.adults, 2)
        self.assertEqual(stay.dogs, 2)
        self.assertEqual(stay.price, 186)
        self.assertTrue(stay.paid)
        self.assertEqual(stay.channel, "direct")
        self.assertTrue(stay.manual)
        hidden = snapshot.manual_stay(
            {
                "guest": "Anna Kowalski",
                "propertyId": 324882,
                "arrival": "2026-10-10",
                "departure": "2026-10-11",
                "email": "secret@example.com",
                "phone": "+34111222333",
                "lastName": "Secretov",
                "channel": "direct",
            },
            1,
        )
        self.assertEqual(hidden.guest_label, "Anna K.")
        self.assertNotIn("Secretov", hidden.guest_label)
        self.assertNotIn("secret@example.com", str(hidden))

    def test_channel_labels(self) -> None:
        self.assertEqual(
            snapshot.channel_label({"apiSource": "19", "referer": "Booking.com"}),
            "Booking.com",
        )
        self.assertEqual(snapshot.channel_label({"apiSource": "46", "referer": "Airbnb"}), "Airbnb")
        self.assertEqual(snapshot.channel_label({"apiSource": "0", "referer": "API"}), "direct")

    def test_report_merges_manual_bookings_and_unanswered_messages(self) -> None:
        client = FakeClient()
        report = snapshot.build_from_client(client, NOW, snapshot.DEFAULT_MANUAL)
        self.assertTrue(all(path.split("?", 1)[0] in {
            "/properties",
            "/bookings",
            "/bookings/messages",
        } for path in client.paths))
        self.assertIn("## Прямые брони вне Beds24", report)
        self.assertIn("Serodes", report)
        self.assertIn("не в Beds24", report)
        self.assertIn("2026-10-10—2026-10-11", report)
        self.assertIn("2 взр. + 2 соб.", report)
        self.assertIn("186.00 EUR, оплачено", report)
        arrivals = report.split("### Заезды на 7 дней", 1)[1].split("###", 1)[0]
        self.assertIn("Serodes", arrivals)
        self.assertIn("не в Beds24", arrivals)
        self.assertNotIn("Anna K.", arrivals)
        departures = report.split("### Выезды на 7 дней", 1)[1].split("###", 1)[0]
        self.assertNotIn("Serodes", departures)
        self.assertIn("не указана (1 номер): 1/30", report)
        self.assertIn("Chalet (4 номера): 3/120", report)
        self.assertIn("Anna K.", report)
        self.assertIn("новая", report)
        self.assertIn("Luis M.", report)
        self.assertIn("отмена", report)
        self.assertIn("486.00 EUR", report)
        self.assertIn("включая 186.00 EUR не в Beds24", report)
        self.assertIn("## Сообщения гостей", report)
        self.assertIn("90522148 · Anna · Booking.com · 2026-10-04 06:00 Europe/Madrid", report)
        self.assertNotIn("90522149", report)
        self.assertNotIn("Это уже ответили", report)
        self.assertNotIn("Kowalski", report)
        self.assertNotIn("Martinez", report)
        self.assertNotIn("Ivanova", report)
        self.assertNotIn("guest@example.com", report)
        self.assertNotIn("612 345 678", report)
        self.assertNotIn("я" * 201, report)
        self.assertIn("[скрыто]", report)
        self.assertIn("## EL CID (324903)", report)

    def test_missing_message_scope_stays_in_the_report(self) -> None:
        client = FakeClient(messages_status=401)
        report = snapshot.build_from_client(client, NOW, snapshot.DEFAULT_MANUAL)
        self.assertIn("Serodes", report)
        self.assertIn("не имеет scope для чтения сообщений", report)
        self.assertIn("bookings-personal", report)
        self.assertIn("HTTP 401", report)
        self.assertNotIn("Это уже ответили", report)
        self.assertNotIn("Позвоните", report)

    def test_exchange_uses_get_only(self) -> None:
        class Response:
            def __init__(self, payload: bytes) -> None:
                self.status = 200
                self._payload = payload

            def read(self) -> bytes:
                return self._payload

            def __enter__(self) -> "Response":
                return self

            def __exit__(self, *_args: object) -> bool:
                return False

        class Opener:
            def __init__(self) -> None:
                self.methods: list[str] = []

            def __call__(self, request: urllib.request.Request, timeout: int = 60) -> Response:
                self.methods.append(request.method or "")
                self.assert_get(request)
                if request.full_url.endswith("/authentication/details"):
                    raise urllib.error.HTTPError(
                        request.full_url,
                        401,
                        "no",
                        None,
                        io.BytesIO(b'{"validToken": false}'),
                    )
                if request.full_url.endswith("/authentication/token"):
                    return Response(b'{"token":"access-token-test"}')
                raise AssertionError(request.full_url)

            @staticmethod
            def assert_get(request: urllib.request.Request) -> None:
                if request.method != "GET" or request.data is not None:
                    raise AssertionError(request.method)

        opener = Opener()
        token, base = snapshot.exchange_token(opener, "refresh-test")
        self.assertEqual(token, "access-token-test")
        self.assertEqual(base, "https://api.beds24.com/v2")
        self.assertEqual(set(opener.methods), {"GET"})

    def test_paused_account_keeps_manual_bookings(self) -> None:
        pause_body = b'{"error":"This account has been paused","token":"refresh-pause-secret"}'

        class Opener:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str]] = []

            def __call__(self, request: urllib.request.Request, timeout: int = 60) -> object:
                self.calls.append((request.method or "", request.full_url))
                if request.method != "GET" or request.data is not None:
                    raise AssertionError(request.method)
                raise urllib.error.HTTPError(
                    request.full_url,
                    403,
                    "paused",
                    None,
                    io.BytesIO(pause_body),
                )

        opener = Opener()
        previous_credential = os.environ.get("BEDS24_REFRESH_CREDENTIAL")
        previous_token = os.environ.get("BEDS24_REFRESH_TOKEN")
        os.environ["BEDS24_REFRESH_CREDENTIAL"] = "refresh-pause-secret"
        os.environ.pop("BEDS24_REFRESH_TOKEN", None)
        try:
            report = snapshot.build_live(NOW, snapshot.DEFAULT_MANUAL, opener)
        finally:
            if previous_credential is None:
                os.environ.pop("BEDS24_REFRESH_CREDENTIAL", None)
            else:
                os.environ["BEDS24_REFRESH_CREDENTIAL"] = previous_credential
            if previous_token is None:
                os.environ.pop("BEDS24_REFRESH_TOKEN", None)
            else:
                os.environ["BEDS24_REFRESH_TOKEN"] = previous_token
        original_build = snapshot.build_live
        snapshot.build_live = lambda now, manual_path, opener=None: report
        try:
            code = snapshot.main(["--now", NOW.isoformat(), "--manual", str(snapshot.DEFAULT_MANUAL)])
        finally:
            snapshot.build_live = original_build
        self.assertEqual(code, 0)
        self.assertTrue(report.startswith("# Снимок бронирований"))
        self.assertIn("⚠️ Beds24 аккаунт на паузе / API:", report)
        self.assertIn(
            'GET https://api.beds24.com/v2/authentication/details HTTP 403: {"error":"This account has been paused","token":"[REDACTED]"}',
            report,
        )
        self.assertIn(
            'GET https://api.beds24.com/v2/authentication/token HTTP 403: {"error":"This account has been paused","token":"[REDACTED]"}',
            report,
        )
        self.assertIn("## Прямые брони вне Beds24", report)
        self.assertIn("Serodes", report)
        self.assertIn("не в Beds24", report)
        self.assertNotIn("refresh-pause-secret", report)
        self.assertGreaterEqual(len(opener.calls), 2)
        self.assertTrue(all(method == "GET" for method, _url in opener.calls))

    def test_bookings_pause_still_renders_manual_section(self) -> None:
        class PausedClient(FakeClient):
            def get_json(self, path: str) -> tuple[int, object]:
                self.paths.append(path)
                return 402, {"success": False, "error": "This account has been paused"}

        report = snapshot.build_from_client(PausedClient(), NOW, snapshot.DEFAULT_MANUAL)
        self.assertIn("⚠️ Beds24 аккаунт на паузе / API:", report)
        self.assertIn("GET /properties HTTP 402:", report)
        self.assertIn('"error": "This account has been paused"', report)
        self.assertIn("## Прямые брони вне Beds24", report)
        self.assertIn("Serodes", report)
        self.assertIn("Сообщения не отправлялись", report)


if __name__ == "__main__":
    unittest.main()
