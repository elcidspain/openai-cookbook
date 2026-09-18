import datetime as dt
import importlib.util
import pathlib
import unittest

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
        self.assertEqual(sample_end, "2026-09-25")

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
        self.assertNotIn("BEDS24_PASSWORD", text)
        self.assertNotIn("BEDS24_USERNAME", text)
        self.assertNotIn("secrets.BEDS24_REFRESH_TOKEN", text)


if __name__ == "__main__":
    unittest.main()
