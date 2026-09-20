import datetime as dt
import importlib.util
import io
import json
import pathlib
import unittest
from unittest import mock
from urllib.error import HTTPError

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = (
    pathlib.Path(__file__).resolve().parents[3]
    / ".github"
    / "workflows"
    / "beds24-open-booking-availability.yml"
)
SPEC = importlib.util.spec_from_file_location(
    "beds24_open_booking_availability",
    SCRIPTS_DIR / "beds24_open_booking_availability.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FakeResponse:
    def __init__(self, status: int, payload: dict):
        self.status = status
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class Beds24OpenBookingAvailabilityTests(unittest.TestCase):
    def test_window_starts_today_not_stale_september_date(self):
        now = dt.datetime(2026, 9, 18, 17, 0, tzinfo=dt.timezone.utc)
        start, end = MODULE.booking_window(now)
        self.assertEqual(start, "2026-09-18")
        self.assertEqual(end, "2028-12-31")
        self.assertGreaterEqual(start, now.date().isoformat())
        self.assertNotEqual(start, "2026-09-13")

    def test_window_extends_when_fixed_end_is_behind_horizon(self):
        now = dt.datetime(2028, 12, 20, tzinfo=dt.timezone.utc)
        start, end = MODULE.booking_window(now)
        self.assertEqual(start, "2028-12-20")
        self.assertEqual(end, "2029-03-20")

    def test_live_window_covers_upcoming_nights(self):
        today = dt.datetime.now(dt.timezone.utc).date()
        start, end = MODULE.booking_window()
        self.assertGreaterEqual(dt.date.fromisoformat(start), today)
        self.assertLessEqual(start, (today + dt.timedelta(days=1)).isoformat())
        self.assertGreaterEqual(
            dt.date.fromisoformat(end),
            dt.date.fromisoformat(start) + dt.timedelta(days=90),
        )

    def test_sample_availability_follows_start(self):
        sample_start, sample_end = MODULE.sample_availability_window("2026-09-18")
        self.assertEqual(sample_start, "2026-09-18")
        self.assertEqual(sample_end, "2026-10-02")

    def test_evidence_path_uses_start_stamp(self):
        path = MODULE.evidence_path("2026-09-18")
        self.assertEqual(path.name, "beds24-open-booking-availability-20260918.json")

    def test_script_no_longer_hardcodes_past_start(self):
        source = (SCRIPTS_DIR / "beds24_open_booking_availability.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn('START = "2026-09-13"', source)
        self.assertNotIn("2026-09-13", source)
        self.assertNotIn("2026-09-19", source)

    def test_workflow_is_dispatchable_and_maps_repo_secret(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("runs-on: ubuntu-latest", text)
        self.assertIn(
            "python aumara-control-tower/scripts/beds24_open_booking_availability.py",
            text,
        )
        self.assertIn(
            "BEDS24_REFRESH_CREDENTIAL: ${{ secrets.BEDS24_REFRESH_CREDENTIAL }}",
            text,
        )
        self.assertIn(
            "BEDS24_REFRESH_TOKEN: ${{ secrets.BEDS24_REFRESH_CREDENTIAL }}",
            text,
        )
        self.assertIn("actions/upload-artifact@v4", text)
        self.assertIn(
            f"aumara-control-tower/evidence/{MODULE.EVIDENCE_GLOB}",
            text,
        )
        self.assertIn("if: github.event_name == 'workflow_dispatch'", text)
        self.assertIn("[open-availability]", text)
        self.assertNotIn("BEDS24_PASSWORD", text)
        self.assertNotIn("BEDS24_USERNAME", text)
        self.assertNotIn("secrets.BEDS24_REFRESH_TOKEN", text)

    def test_continuity_and_map_document_channels_invite(self):
        continuity = (
            pathlib.Path(__file__).resolve().parents[2]
            / "systems"
            / "beds24-continuity.md"
        ).read_text(encoding="utf-8")
        mapping = (
            pathlib.Path(__file__).resolve().parents[2]
            / "docs"
            / "BEDS24_BOOKING_RATES_AVAIL_MAP.md"
        ).read_text(encoding="utf-8")
        self.assertIn("channels", continuity.lower())
        self.assertIn("read:channels", continuity)
        self.assertIn("write:channels", continuity)
        self.assertIn("control3.php?pagetype=apiv2", continuity)
        self.assertIn("BEDS24_REFRESH_CREDENTIAL", continuity)
        self.assertIn("2028-12-31", mapping)
        self.assertIn("Fully flexible", mapping)
        self.assertIn("Never use `BEDS24_PASSWORD` / `BEDS24_USERNAME`", continuity)

    def test_exchange_token_ignores_details_200_and_returns_exchanged_token(self):
        refresh = "refresh-secret"
        exchanged = "exchanged-access"
        calls = []

        def fake_urlopen(request, timeout=None):
            url = getattr(request, "full_url", str(request))
            headers = {
                key.lower(): value for key, value in request.header_items()
            }
            calls.append((url, headers, timeout))
            if url.rstrip("/").endswith("/authentication/details"):
                return FakeResponse(200, {"validToken": True})
            if url.rstrip("/").endswith("/authentication/token"):
                self.assertEqual(headers.get("refreshtoken"), refresh)
                return FakeResponse(200, {"token": exchanged})
            raise AssertionError(f"unexpected url {url}")

        with mock.patch.object(MODULE.urllib.request, "urlopen", side_effect=fake_urlopen):
            with mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
                token = MODULE.exchange_token(refresh)

        self.assertEqual(token, exchanged)
        self.assertNotEqual(token, refresh)
        token_calls = [call for call in calls if call[0].rstrip("/").endswith("/authentication/token")]
        self.assertEqual(len(token_calls), 1)
        output = stdout.getvalue()
        self.assertIn("token_mode=refresh_exchange", output)
        self.assertNotIn("token_mode=direct_access", output)
        self.assertNotIn(refresh, output)
        source = (SCRIPTS_DIR / "beds24_open_booking_availability.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("token_mode=direct_access", source)
        # exchange_token must not call details; main may probe scopes after exchange.
        import inspect
        exchange_src = inspect.getsource(MODULE.exchange_token)
        self.assertNotIn('API + "/authentication/details"', exchange_src)
        self.assertIn("/authentication/token", exchange_src)
        details_calls = [
            call for call in calls if call[0].rstrip("/").endswith("/authentication/details")
        ]
        self.assertEqual(details_calls, [])

    def test_exchange_token_does_not_fall_back_to_refresh_on_exchange_failure(self):
        refresh = "refresh-secret"

        def fake_urlopen(request, timeout=None):
            url = getattr(request, "full_url", str(request))
            if url.rstrip("/").endswith("/authentication/details"):
                return FakeResponse(200, {"validToken": True})
            if url.rstrip("/").endswith("/authentication/token"):
                raise HTTPError(
                    url,
                    401,
                    "Unauthorized",
                    hdrs={},
                    fp=io.BytesIO(b'{"error":"Token not valid"}'),
                )
            raise AssertionError(f"unexpected url {url}")

        with mock.patch.object(MODULE.urllib.request, "urlopen", side_effect=fake_urlopen):
            with self.assertRaises(SystemExit) as raised:
                MODULE.exchange_token(refresh)
        self.assertIn("refresh HTTP 401", str(raised.exception))


    def test_script_writes_prices_and_probes_scopes(self):
        source = (SCRIPTS_DIR / "beds24_open_booking_availability.py").read_text(encoding="utf-8")
        self.assertIn("price1", source)
        self.assertIn("259", source)
        self.assertIn("329", source)
        self.assertIn("sanitize_details", source)
        self.assertIn("CHANNELS_SCOPES_NEEDED", source)
        # CHALET capped to room max 3
        self.assertIn("674465", source)
        self.assertRegex(source, r"674465[^}]*target_num_avail.: 3")
        payload = MODULE.build_calendar_payload("2026-09-18", "2028-12-31")
        by_room = {row["roomId"]: row["calendar"][0] for row in payload}
        self.assertEqual(by_room[674465]["numAvail"], 3)
        self.assertEqual(by_room[674465]["price1"], 259.0)
        self.assertEqual(by_room[674466]["numAvail"], 2)
        self.assertEqual(by_room[674466]["price1"], 329.0)
        self.assertEqual(by_room[674465]["to"], "2028-12-31")
        self.assertIn("channels", MODULE.DOCUMENTED_INVITE_SCOPES)
        self.assertEqual(MODULE.FIXED_END.isoformat(), "2028-12-31")

    def test_hotel_id_hits_classify_working_vs_legacy(self):
        payload = {
            "id": 324882,
            "channelLinks": {"booking": 1},
            "roomTypes": [{"id": 674465, "bookingHotel": "16137893"}],
        }
        hits = MODULE.hotel_id_hits(payload)
        self.assertEqual(hits[MODULE.HOTEL_WORKING], ["$.roomTypes[0].bookingHotel"])
        self.assertEqual(hits[MODULE.HOTEL_LEGACY], [])
        self.assertEqual(MODULE.classify_hotel_linkage(hits), "working_16137893_only")
        both = MODULE.hotel_id_hits({"a": "16137893", "b": "14953869"})
        self.assertEqual(MODULE.classify_hotel_linkage(both), "both_present")
        none = MODULE.hotel_id_hits({"id": 324882})
        self.assertEqual(MODULE.classify_hotel_linkage(none), "absent_from_v2_properties")

    def test_enable_target_rate_plans_only_opens_named_plans(self):
        data = [
            {
                "channel": "booking",
                "properties": [
                    {
                        "id": 324882,
                        "roomTypes": [
                            {
                                "id": 674465,
                                "ratePlans": [
                                    {"name": "Fully flexible", "enabled": False, "closed": True},
                                    {"name": "Weekly", "enabled": False},
                                    {"name": "Non-refundable", "enabled": False},
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
        updated, flipped = MODULE.enable_target_rate_plans(data)
        plans = updated[0]["properties"][0]["roomTypes"][0]["ratePlans"]
        self.assertTrue(plans[0]["enabled"])
        self.assertFalse(plans[0]["closed"])
        self.assertTrue(plans[1]["enabled"])
        self.assertFalse(plans[2]["enabled"])
        self.assertGreaterEqual(flipped, 2)

    def test_channel_rate_open_skips_write_on_missing_scope_401(self):
        calls = []

        def fake_http(method, url, token, body=None, *, raise_http=True):
            calls.append((method, url, body))
            if method == "GET" and "/channels/settings" in url:
                return 401, {"error": "Token not valid", "code": 401}
            raise AssertionError(f"unexpected {method} {url}")

        with mock.patch.object(MODULE, "http_json", side_effect=fake_http):
            result = MODULE.open_booking_channel_rate_plans("access-token", has_channels=False)
        self.assertEqual(result["status"], "SKIPPED_MISSING_CHANNELS_SCOPE")
        self.assertFalse(result["write_attempted"])
        self.assertEqual([c[0] for c in calls], ["GET"])
        self.assertIn("channels", result["documented_invite_scopes"])

    def test_channel_rate_open_posts_when_scoped_get_succeeds(self):
        get_body = {
            "data": [
                {
                    "channel": "booking",
                    "properties": [
                        {
                            "id": 324882,
                            "roomTypes": [
                                {
                                    "id": 674465,
                                    "ratePlans": [
                                        {"name": "Fully flexible", "enabled": False},
                                        {"name": "Weekly", "enabled": False},
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        calls = []

        def fake_http(method, url, token, body=None, *, raise_http=True):
            calls.append((method, url, body))
            if method == "GET" and "/channels/settings" in url:
                return 200, get_body
            if method == "POST" and url.endswith("/channels/settings"):
                self.assertEqual(token, "access-token")
                plans = body[0]["properties"][0]["roomTypes"][0]["ratePlans"]
                self.assertTrue(plans[0]["enabled"])
                self.assertTrue(plans[1]["enabled"])
                return 201, [{"success": True}]
            raise AssertionError(f"unexpected {method} {url}")

        with mock.patch.object(MODULE, "http_json", side_effect=fake_http):
            result = MODULE.open_booking_channel_rate_plans("access-token", has_channels=True)
        methods = [c[0] for c in calls]
        self.assertEqual(methods, ["GET", "POST", "GET"])
        self.assertEqual(result["status"], "OPENED")
        self.assertTrue(result["write_attempted"])
        self.assertEqual(result["write_http"], 201)

    def test_calendar_chunks_cover_2028_in_year_windows(self):
        chunks = MODULE.calendar_chunks("2026-09-18", "2028-12-31")
        self.assertEqual(chunks[0], ("2026-09-18", "2027-09-17"))
        self.assertEqual(chunks[-1][1], "2028-12-31")
        self.assertGreaterEqual(len(chunks), 3)
        self.assertEqual(MODULE.FIXED_END, dt.date(2028, 12, 31))
        source = (SCRIPTS_DIR / "beds24_open_booking_availability.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("read:channels", source)
        self.assertIn("write:channels", source)


if __name__ == "__main__":
    unittest.main()
