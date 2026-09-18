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
            dt.date(2028, 12, 31),
        )

    def test_calendar_chunks_cover_through_2028(self):
        chunks = MODULE.calendar_chunks("2026-09-18", "2028-12-31")
        self.assertGreaterEqual(len(chunks), 3)
        self.assertEqual(chunks[0][0], "2026-09-18")
        self.assertEqual(chunks[-1][1], "2028-12-31")
        reconstructed = []
        for start, end in chunks:
            self.assertLessEqual(
                (dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days,
                MODULE.CALENDAR_CHUNK_DAYS,
            )
            reconstructed.append((start, end))
        self.assertEqual(reconstructed[0][0], "2026-09-18")
        self.assertEqual(reconstructed[-1][1], "2028-12-31")
        self.assertEqual(MODULE.FIXED_END.isoformat(), "2028-12-31")

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
        self.assertIn("BEDS24_API_KEY: ${{ secrets.BEDS24_API_KEY }}", text)
        self.assertIn("BEDS24_PROP_KEY: ${{ secrets.BEDS24_PROP_KEY }}", text)
        self.assertIn("environment: Production", text)
        self.assertIn("BEDS24_REQUIRE_RACK_RATES", text)
        self.assertIn("rack-rates:", text)
        self.assertIn("beds24-rack-rate-live.json", text)
        self.assertNotIn("BEDS24_PASSWORD", text)
        self.assertNotIn("BEDS24_USERNAME", text)
        self.assertNotIn("secrets.BEDS24_REFRESH_TOKEN", text)

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
        payload = MODULE.build_calendar_payload("2026-09-18", "2026-12-31")
        by_room = {row["roomId"]: row["calendar"][0] for row in payload}
        self.assertEqual(by_room[674465]["numAvail"], 3)
        self.assertEqual(by_room[674465]["price1"], 259.0)
        self.assertEqual(by_room[674466]["numAvail"], 2)
        self.assertEqual(by_room[674466]["price1"], 329.0)

    def test_v1_skips_when_legacy_keys_absent(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            result = MODULE.set_v1_rack_rates(sleep_s=0)
        self.assertEqual(result["status"], "SKIPPED_MISSING_V1_SECRETS")
        self.assertEqual(result["wanted"]["674465"], "259.00")
        self.assertEqual(result["legacy_hotel_id"], "14953869")

    def test_v1_rack_rate_write_readback_success(self):
        before = {
            "getPropertyContent": [
                {"roomIds": {"674465": {"rackRate": "0.00"}, "674466": {"rackRate": "0.00"}}}
            ]
        }
        after = {
            "getPropertyContent": [
                {"roomIds": {"674465": {"rackRate": "259.00"}, "674466": {"rackRate": "329.00"}}}
            ]
        }
        calls = []

        def fake_urlopen(request, timeout=None):
            url = getattr(request, "full_url", str(request))
            body = json.loads((request.data or b"{}").decode("utf-8"))
            calls.append(url)
            self.assertEqual(body["authentication"]["apiKey"], "api-secret")
            self.assertEqual(body["authentication"]["propKey"], "prop-secret")
            if url.endswith("/getPropertyContent"):
                return FakeResponse(
                    200, after if any(item.endswith("/setPropertyContent") for item in calls[:-1]) else before
                )
            if url.endswith("/setPropertyContent"):
                room_ids = body["setPropertyContent"][0]["roomIds"]
                self.assertEqual(room_ids["674465"]["rackRate"], "259.00")
                self.assertEqual(room_ids["674466"]["rackRate"], "329.00")
                return FakeResponse(200, {"setPropertyContent": [{"success": True}]})
            raise AssertionError(url)

        env = {"BEDS24_API_KEY": "api-secret", "BEDS24_PROP_KEY": "prop-secret"}
        with mock.patch.dict("os.environ", env, clear=True):
            with mock.patch.object(MODULE.urllib.request, "urlopen", side_effect=fake_urlopen):
                result = MODULE.set_v1_rack_rates(sleep_s=0)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["after"]["674465"], "259.00")
        self.assertEqual(result["after"]["674466"], "329.00")
        self.assertEqual(result["mismatches"], [])
        dumped = json.dumps(result)
        self.assertNotIn("api-secret", dumped)
        self.assertNotIn("prop-secret", dumped)

    def test_v1_hotel_access_denied_is_reported(self):
        def fake_urlopen(request, timeout=None):
            return FakeResponse(
                200,
                {
                    "error": "HOTEL_ACCESS_DENIED",
                    "message": "Request for forbidden hotel id(s) 14953869",
                },
            )

        env = {"BEDS24_API_KEY": "api-secret", "BEDS24_PROP_KEY": "prop-secret"}
        with mock.patch.dict("os.environ", env, clear=True):
            with mock.patch.object(MODULE.urllib.request, "urlopen", side_effect=fake_urlopen):
                result = MODULE.set_v1_rack_rates(sleep_s=0)
        self.assertEqual(result["status"], "HOTEL_ACCESS_DENIED")
        self.assertIn("14953869", result["note"])
        self.assertNotIn("api-secret", json.dumps(result))

    def test_finish_requires_v1_success_when_flag_set(self):
        evidence = {
            "after_summary": {"674465": {"days": 10, "numAvail_zero_days": 0}},
            "v1_rack_rates": {"status": "SKIPPED_MISSING_V1_SECRETS"},
        }
        with mock.patch.dict("os.environ", {"BEDS24_REQUIRE_RACK_RATES": "1"}):
            with self.assertRaises(SystemExit) as raised:
                MODULE.finish(evidence)
        self.assertIn("SKIPPED_MISSING_V1_SECRETS", str(raised.exception))
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(MODULE.finish(evidence), 0)

    def test_booking_map_documents_v1_rack_path(self):
        path = pathlib.Path(__file__).resolve().parents[2] / "docs" / "BEDS24_BOOKING_MAP.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("BEDS24_REFRESH_CREDENTIAL", text)
        self.assertIn("BEDS24_API_KEY", text)
        self.assertIn("BEDS24_PROP_KEY", text)
        self.assertIn("setPropertyContent", text)
        self.assertIn("inventory/rooms/calendar", text)
        self.assertIn("channels", text)
        self.assertIn("14953869", text)
        self.assertIn("HOTEL_ACCESS_DENIED", text)
        self.assertIn("2028-12-31", text)
        self.assertIn("primary", text.lower())


if __name__ == "__main__":
    unittest.main()
