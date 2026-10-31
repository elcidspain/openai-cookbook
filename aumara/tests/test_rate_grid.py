import copy
import datetime as dt
import json
import unittest
from pathlib import Path

from aumara.rate_grid import build_expected, daily_price_setup, future_expected


class ApprovedRateGridTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path("aumara/config/rate-canonical.json").read_text())
        self.grid = build_expected(self.config)

    def test_complete_two_room_horizon(self):
        for dates in self.grid.values():
            self.assertEqual(len(dates), 426)
            self.assertEqual(min(dates), "20261101")
            self.assertEqual(max(dates), "20271231")

    def test_no_general_increase_and_matching_weekend_quote(self):
        self.assertEqual(self.grid["674465"]["20261102"], 139)
        self.assertEqual(self.grid["674466"]["20261102"], 169)
        self.assertEqual(sum(self.grid["674465"][d] for d in ["20261106", "20261107"]), 298)
        self.assertEqual(sum(self.grid["674466"][d] for d in ["20261106", "20261107"]), 358)

    def test_monthly_steps_and_spread_boundary(self):
        self.assertEqual([self.grid[r]["20270331"] for r in ["674465", "674466"]], [149, 179])
        self.assertEqual([self.grid[r]["20270401"] for r in ["674465", "674466"]], [159, 209])
        expected = {3: 149, 4: 159, 5: 169, 6: 179, 7: 189, 8: 199,
                    9: 189, 10: 179, 11: 169, 12: 159}
        # Explicit ordinary weekday samples avoid holiday overrides.
        days = {3: 1, 4: 1, 5: 3, 6: 1, 7: 1, 8: 2, 9: 1, 10: 4, 11: 2, 12: 1}
        for month, price in expected.items():
            self.assertEqual(self.grid["674465"][f"2027{month:02}{days[month]:02}"], price)
        for day, chalet in self.grid["674465"].items():
            self.assertEqual(self.grid["674466"][day] - chalet, 50 if day >= "20270401" else 30)

    def test_special_windows_replace_weekend_price(self):
        self.assertEqual([self.grid[r]["20270326"] for r in ["674465", "674466"]], [179, 209])
        self.assertEqual([self.grid[r]["20271225"] for r in ["674465", "674466"]], [179, 229])
        self.assertEqual([self.grid[r]["20271231"] for r in ["674465", "674466"]], [189, 239])

    def test_invalid_or_unapproved_grid_is_rejected(self):
        for kind in ["overlap", "gap", "fraction", "spread", "approved-amount"]:
            cfg = copy.deepcopy(self.config)
            if kind == "overlap":
                cfg["specialWindows"].append(cfg["specialWindows"][0])
            elif kind == "gap":
                cfg["monthlyRates"].pop()
            elif kind == "fraction":
                cfg["monthlyRates"][0]["chalet"]["weekday"] = 139.5
            elif kind == "spread":
                cfg["monthlyRates"][0]["superiorChalet"]["weekday"] += 1
            else:
                cfg["monthlyRates"][0]["chalet"]["weekday"] += 1
                cfg["monthlyRates"][0]["superiorChalet"]["weekday"] += 1
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                build_expected(cfg)

    def test_future_operations_leave_past_dates_out(self):
        future = future_expected(self.config, dt.date(2027, 12, 31))
        self.assertEqual(future, {"674465": {"20271231": 189}, "674466": {"20271231": 239}})

    def test_daily_price_response_shapes(self):
        row = {"dailyPriceNumber": "1", "minStay": "1"}
        self.assertEqual(daily_price_setup({"roomId": "674465", "dailyPrices": [row]}, "674465"), row)
        self.assertEqual(daily_price_setup([{"roomId": "674465", "dailyPrices": [row]}], "674465"), row)
        with self.assertRaises(ValueError):
            daily_price_setup({"errorCode": 1002}, "674465")


if __name__ == "__main__":
    unittest.main()
