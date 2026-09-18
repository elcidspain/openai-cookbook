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
        self.assertEqual(end, "2026-12-31")
        self.assertGreaterEqual(start, now.date().isoformat())
        self.assertNotEqual(start, "2026-09-13")

    def test_window_extends_when_fixed_end_is_behind_horizon(self):
        now = dt.datetime(2026, 12, 20, tzinfo=dt.timezone.utc)
        start, end = MODULE.booking_window(now)
        self.assertEqual(start, "2026-12-20")
        self.assertEqual(end, "2027-03-20")

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
        self.assertNotIn('API + "/authentication/details"', source)

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


if __name__ == "__main__":
    unittest.main()
