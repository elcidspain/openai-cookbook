import datetime as dt
import importlib.util
import io
import json
import os
import pathlib
import unittest
from unittest import mock

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = (
    pathlib.Path(__file__).resolve().parents[3]
    / ".github"
    / "workflows"
    / "beds24-open-booking-channel-rates.yml"
)
INVITE_WORKFLOW = (
    pathlib.Path(__file__).resolve().parents[3]
    / ".github"
    / "workflows"
    / "exchange-beds24-invite.yml"
)
SPEC = importlib.util.spec_from_file_location(
    "beds24_open_booking_channel_rates",
    SCRIPTS_DIR / "beds24_open_booking_channel_rates.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FakeResponse:
    def __init__(self, status: int, payload: dict | list):
        self.status = status
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def sample_settings(*, flexible_closed=True, weekly_closed=True):
    return {
        "data": [
            {
                "channel": "booking",
                "properties": [
                    {
                        "id": 324882,
                        "bookingComPropertyCode": "14953869",
                        "roomTypes": [
                            {
                                "id": 674465,
                                "ratePlans": [
                                    {
                                        "name": "Fully flexible",
                                        "closed": flexible_closed,
                                        "enabled": not flexible_closed,
                                    },
                                    {
                                        "name": "Weekly",
                                        "closed": weekly_closed,
                                        "enabled": not weekly_closed,
                                        "minStay": 7,
                                    },
                                    {"name": "Non-refundable", "closed": True, "enabled": False},
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }


class Beds24OpenBookingChannelRatesTests(unittest.TestCase):
    def test_requires_read_and_write_channels(self):
        self.assertFalse(MODULE.has_required_channel_scopes(set()))
        self.assertFalse(MODULE.has_required_channel_scopes({"inventory", "properties"}))
        self.assertFalse(MODULE.has_required_channel_scopes({"read:channels"}))
        self.assertFalse(MODULE.has_required_channel_scopes({"write:channels"}))
        self.assertTrue(
            MODULE.has_required_channel_scopes({"read:channels", "write:channels"})
        )
        self.assertTrue(MODULE.has_required_channel_scopes({"channels"}))
        self.assertEqual(
            MODULE.missing_channel_scopes({"inventory"}),
            ["read:channels", "write:channels"],
        )

    def test_classifies_flexible_and_weekly_aliases(self):
        self.assertEqual(MODULE.classify_plan({}, "Fully flexible"), "fully_flexible")
        self.assertEqual(MODULE.classify_plan({}, "Tarifa flexible"), "fully_flexible")
        self.assertEqual(MODULE.classify_plan({}, "Weekly"), "weekly")
        self.assertEqual(MODULE.classify_plan({}, "Tarifa semanal"), "weekly")
        self.assertEqual(MODULE.classify_plan({"minStay": 7}, "Rate 2"), "weekly")
        self.assertIsNone(MODULE.classify_plan({}, "Non-refundable"))

    def test_open_rate_plan_flips_existing_flags_only(self):
        node = {"name": "Fully flexible", "closed": True, "enabled": False, "mystery": 9}
        changed = MODULE.open_rate_plan(node)
        self.assertEqual(node["closed"], False)
        self.assertEqual(node["enabled"], True)
        self.assertEqual(node["mystery"], 9)
        self.assertCountEqual(changed, ["closed", "enabled"])

    def test_targeting_keeps_v1_linked_hotel(self):
        decision = MODULE.targeting_decision({"14953869", "16137893"})
        self.assertEqual(decision["target_booking_hotel_id"], 14953869)
        self.assertEqual(decision["decision"], "keep_v1_linked_14953869")
        only_working = MODULE.targeting_decision({"16137893"})
        self.assertEqual(only_working["target_booking_hotel_id"], 16137893)
        defaulted = MODULE.targeting_decision(set())
        self.assertEqual(defaulted["target_booking_hotel_id"], 14953869)

    def test_collect_hotel_ids_from_v1_style_fields(self):
        found = MODULE.collect_hotel_ids(
            {"bookingComPropertyCode": "14953869", "other": {"hotelId": 16137893}}
        )
        self.assertEqual(found, {"14953869", "16137893"})

    def test_lists_and_opens_booking_plans_not_airbnb(self):
        payload = sample_settings()
        payload["data"].append(
            {
                "channel": "airbnb",
                "properties": [
                    {
                        "id": 324882,
                        "roomTypes": [
                            {"id": 674465, "ratePlans": [{"name": "Flexible", "closed": True}]}
                        ],
                    }
                ],
            }
        )
        listed = MODULE.list_booking_rate_plans(payload["data"])
        kinds = {row["kind"] for row in listed if row["kind"]}
        self.assertEqual(kinds, {"fully_flexible", "weekly"})
        self.assertTrue(all(row["channel"] == "booking" for row in listed))
        result = MODULE.open_target_plans(payload["data"])
        self.assertEqual(len(result["opened"]), 2)
        booking_plans = payload["data"][0]["properties"][0]["roomTypes"][0]["ratePlans"]
        self.assertFalse(booking_plans[0]["closed"])
        self.assertTrue(booking_plans[0]["enabled"])
        self.assertFalse(booking_plans[1]["closed"])
        self.assertTrue(payload["data"][1]["properties"][0]["roomTypes"][0]["ratePlans"][0]["closed"])

    def test_workflow_is_dispatch_only_for_live_writes(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertIn(
            "python aumara-control-tower/scripts/beds24_open_booking_channel_rates.py",
            text,
        )
        self.assertIn(
            "BEDS24_REFRESH_CREDENTIAL: ${{ secrets.BEDS24_REFRESH_CREDENTIAL }}",
            text,
        )
        self.assertIn("BEDS24_API_KEY: ${{ secrets.BEDS24_API_KEY }}", text)
        self.assertIn("BEDS24_PROP_KEY: ${{ secrets.BEDS24_PROP_KEY }}", text)
        self.assertIn("environment: Production", text)
        self.assertIn("[open-channel-rates]", text)
        self.assertIn("beds24_v1_booking_rates.py", text)
        self.assertNotIn("BEDS24_PASSWORD", text)
        self.assertNotIn("BEDS24_USERNAME", text)
        self.assertIn("actions/upload-artifact@v4", text)
        self.assertIn("beds24-open-booking-channel-rates", text)
        self.assertIn("API Key", text)
        self.assertIn("MARKETPLACE", text)

    def test_invite_workflow_lists_channel_scopes_and_next_step(self):
        text = INVITE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("read:channels", text)
        self.assertIn("write:channels", text)
        self.assertIn("bookings-personal", text)
        self.assertIn("beds24-open-booking-channel-rates", text)
        self.assertIn("BEDS24_REFRESH_CREDENTIAL", text)
        self.assertNotIn("BEDS24_PASSWORD", text)
        self.assertNotIn("paste password", text.lower())

    def test_fail_closed_without_channels_scope_writes_evidence(self):
        tmp = pathlib.Path(self.id().replace(".", "_") + "-evidence.json")
        self.addCleanup(lambda: tmp.exists() and tmp.unlink())

        def fake_http(method, url, token, body=None, raise_http=True):
            if url.rstrip("/").endswith("/authentication/details"):
                return 200, {"validToken": True, "scopes": ["inventory", "properties", "bookings"]}
            if "/properties" in url:
                return 200, {"data": [{"id": 324882, "bookingComPropertyCode": "14953869"}]}
            raise AssertionError(f"unexpected {method} {url}")

        with mock.patch.object(MODULE, "load_refresh", return_value="refresh-secret"):
            with mock.patch.object(MODULE, "exchange_token", return_value="access-token"):
                with mock.patch.object(MODULE, "http_json", side_effect=fake_http):
                    with mock.patch.object(MODULE, "evidence_path", return_value=tmp):
                        with mock.patch("sys.stdout", new_callable=io.StringIO):
                            code = MODULE.main()
        self.assertEqual(code, MODULE.EXIT_MISSING_CHANNELS_SCOPE)
        evidence = json.loads(tmp.read_text(encoding="utf-8"))
        self.assertEqual(evidence["status"], "MISSING_CHANNELS_SCOPE")
        self.assertEqual(evidence["targeting"]["target_booking_hotel_id"], 14953869)
        self.assertNotIn("refresh-secret", json.dumps(evidence))
        self.assertNotIn("access-token", json.dumps(evidence))

    def test_success_posts_opened_plans(self):
        tmp = pathlib.Path(self.id().replace(".", "_") + "-evidence.json")
        self.addCleanup(lambda: tmp.exists() and tmp.unlink())
        settings = sample_settings()
        calls = []

        def fake_http(method, url, token, body=None, raise_http=True):
            calls.append((method, url, body is not None))
            if url.rstrip("/").endswith("/authentication/details"):
                return 200, {
                    "validToken": True,
                    "scopes": ["read:channels", "write:channels", "inventory"],
                }
            if "/properties" in url:
                return 200, {"data": [{"id": 324882, "bookingComPropertyCode": "14953869"}]}
            if method == "GET" and "/channels/settings" in url:
                return 200, settings
            if method == "POST" and url.rstrip("/").endswith("/channels/settings"):
                return 201, {"success": True}
            raise AssertionError(f"unexpected {method} {url}")

        with mock.patch.object(MODULE, "load_refresh", return_value="refresh-secret"):
            with mock.patch.object(MODULE, "exchange_token", return_value="access-token"):
                with mock.patch.object(MODULE, "http_json", side_effect=fake_http):
                    with mock.patch.object(MODULE, "evidence_path", return_value=tmp):
                        with mock.patch("sys.stdout", new_callable=io.StringIO):
                            code = MODULE.main()
        self.assertEqual(code, 0)
        evidence = json.loads(tmp.read_text(encoding="utf-8"))
        self.assertEqual(evidence["status"], "SUCCESS")
        self.assertGreaterEqual(len(evidence["mutation"]["opened"]), 2)
        self.assertTrue(any(method == "POST" for method, _url, _has in calls))

    def test_exchange_token_does_not_call_details(self):
        import inspect

        source = inspect.getsource(MODULE.exchange_token)
        self.assertNotIn("/authentication/details", source)
        self.assertIn("/authentication/token", source)

    def test_script_does_not_reference_passwords(self):
        for name in (
            "beds24_open_booking_channel_rates.py",
            "beds24_v1_booking_rates.py",
        ):
            source = (SCRIPTS_DIR / name).read_text(encoding="utf-8")
            self.assertNotIn("BEDS24_PASSWORD", source)
            self.assertNotIn("BEDS24_USERNAME", source)

    def test_v1_absent_keys_do_not_call_network(self):
        v1 = MODULE.load_v1_module()
        with mock.patch.dict(
            os.environ, {"BEDS24_API_KEY": "", "BEDS24_PROP_KEY": ""}
        ):
            result = v1.run_v1(
                classify=MODULE.classify_plan,
                opener=lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")),
            )
        self.assertEqual(result["status"], "V1_KEYS_ABSENT")
        self.assertTrue(result["do_not_paste_api_keys"] if "do_not_paste_api_keys" in result else result["mobile_invite_nav"]["do_not_paste_api_keys"])
        self.assertIn("Generate invite code", result["mobile_invite_nav"]["right_page"]["must_see"])
        self.assertIn("API Key 1", result["mobile_invite_nav"]["wrong_page"]["signals"][0])

    def test_v1_opens_existing_weekly_and_flexible_rates(self):
        v1 = MODULE.load_v1_module()
        calls = []

        def opener(req, timeout=90):
            url = req.full_url
            payload = json.loads(req.data.decode("utf-8"))
            calls.append(url.rsplit("/", 1)[-1])
            auth = payload.get("authentication") or {}
            self.assertNotIn("password", json.dumps(auth).lower())
            if url.endswith("/getProperty"):
                body = {
                    "getProperty": [
                        {
                            "bookingComPropertyCode": "14953869",
                            "roomTypes": [
                                {
                                    "roomId": "674465",
                                    "name": "Chalet",
                                    "bookingComEnableInventory": 1,
                                    "bookingComEnableBooking": 1,
                                    "bookingComRateCode": "66887702",
                                    "dailyPriceCount": "1",
                                },
                                {
                                    "roomId": "674466",
                                    "name": "Superior Chalet",
                                    "bookingComEnableInventory": 1,
                                    "bookingComEnableBooking": 1,
                                    "bookingComRateCode": "66887702",
                                    "dailyPriceCount": "1",
                                },
                            ],
                        }
                    ]
                }
            elif url.endswith("/getRates"):
                body = {
                    "getRates": [
                        {
                            "rateId": "1",
                            "roomId": "674465",
                            "name": "Fully flexible",
                            "roomPriceEnable": "0",
                            "minNights": "1",
                            "bookingcomRateCode": "66887702",
                            "lastNight": "2025-01-01",
                        },
                        {
                            "rateId": "2",
                            "roomId": "674465",
                            "name": "Weekly",
                            "roomPriceEnable": "0",
                            "minNights": "7",
                            "bookingcomRateCode": "999",
                            "lastNight": "2025-01-01",
                        },
                        {
                            "rateId": "3",
                            "roomId": "674466",
                            "name": "Fully flexible",
                            "roomPriceEnable": "1",
                            "minNights": "1",
                            "bookingcomRateCode": "66887702",
                            "lastNight": "2028-12-31",
                        },
                        {
                            "rateId": "4",
                            "roomId": "674466",
                            "name": "Weekly",
                            "roomPriceEnable": "1",
                            "minNights": "7",
                            "bookingcomRateCode": "999",
                            "lastNight": "2028-12-31",
                        },
                    ]
                }
            elif url.endswith("/getDailyPriceSetup"):
                body = {
                    "dailyPrices": [
                        {
                            "dailyPriceNumber": "1",
                            "name": "Fully flexible",
                            "bookingComEnable": "0",
                            "minStay": "2",
                        }
                    ]
                }
            elif url.endswith("/getV2RefreshToken"):
                body = {"error": "not available"}
            elif url.endswith("/setRates"):
                body = {"success": True, "setRates": payload.get("setRates")}
            elif url.endswith("/setDailyPriceSetup"):
                body = {"success": True}
            elif url.endswith("/setRoomDates"):
                body = {"success": True}
            else:
                raise AssertionError(url)
            return FakeResponse(200, body)

        with mock.patch.dict(
            os.environ,
            {"BEDS24_API_KEY": "v1-api-secret", "BEDS24_PROP_KEY": "v1-prop-secret"},
        ):
            result = v1.run_v1(
                classify=MODULE.classify_plan,
                opener=opener,
                sleep_s=0,
                now=dt.datetime(2026, 9, 18, tzinfo=dt.timezone.utc),
            )
        dumped = json.dumps(result)
        self.assertNotIn("v1-api-secret", dumped)
        self.assertNotIn("v1-prop-secret", dumped)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertIn("setRates", calls)
        self.assertIn("setRoomDates", calls)
        self.assertCountEqual(result["opens"], ["fully_flexible", "weekly"])

    def test_v1_success_makes_missing_v2_scope_nonfatal(self):
        tmp = pathlib.Path(self.id().replace(".", "_") + "-evidence.json")
        self.addCleanup(lambda: tmp.exists() and tmp.unlink())

        def fake_http(method, url, token, body=None, raise_http=True):
            if url.rstrip("/").endswith("/authentication/details"):
                return 200, {"validToken": True, "scopes": ["inventory", "properties"]}
            if "/properties" in url:
                return 200, {"data": [{"id": 324882, "bookingComPropertyCode": "14953869"}]}
            raise AssertionError(f"unexpected {method} {url}")

        v1_ok = {
            "status": "SUCCESS",
            "opens": ["fully_flexible", "weekly"],
            "methods_tried": [],
            "mobile_invite_nav": {"do_not_paste_api_keys": True},
        }
        with mock.patch.object(MODULE, "load_v1_module") as load_v1:
            load_v1.return_value.run_v1.return_value = dict(v1_ok)
            load_v1.return_value.V1_CALL_GAP_SEC = 0
            load_v1.return_value.MOBILE_INVITE_NAV = v1_ok["mobile_invite_nav"]
            with mock.patch.object(MODULE, "load_refresh", return_value="refresh-secret"):
                with mock.patch.object(MODULE, "exchange_token", return_value="access-token"):
                    with mock.patch.object(MODULE, "http_json", side_effect=fake_http):
                        with mock.patch.object(MODULE, "evidence_path", return_value=tmp):
                            with mock.patch("sys.stdout", new_callable=io.StringIO):
                                code = MODULE.main()
        self.assertEqual(code, 0)
        evidence = json.loads(tmp.read_text(encoding="utf-8"))
        self.assertEqual(evidence["status"], "SUCCESS")
        self.assertEqual(evidence["opened_via"], "v1_json")
        self.assertNotIn("refresh-secret", json.dumps(evidence))


if __name__ == "__main__":
    unittest.main()
