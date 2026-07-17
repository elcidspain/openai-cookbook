import importlib.util
import pathlib
import unittest
from unittest import mock


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "beds24_finalize_paid_booking.py"
SPEC = importlib.util.spec_from_file_location("beds24_finalize_paid_booking", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class FinalizePaidBookingTests(unittest.TestCase):
    def test_normalize_credential_strips_quotes_whitespace_and_control_chars(self):
        value = '  "  refresh-123\n\t\u200b  "  '
        self.assertEqual(MODULE.normalize_credential(value), "refresh-123")

    def test_resolve_refresh_token_requires_secret(self):
        with self.assertRaisesRegex(
            SystemExit, "Missing GitHub Actions secret B24_TOKEN_CREDENTIAL"
        ):
            MODULE.resolve_refresh_token(env={})

    @mock.patch.object(MODULE, "request_json")
    def test_run_read_only_verification_uses_refresh_exchange_then_properties(
        self, request_json
    ):
        request_json.side_effect = [
            (200, {"token": "access-123"}),
            (200, {"data": [{"id": 11}, {"id": 22}]}),
        ]

        result = MODULE.run_read_only_verification(
            env={"B24_TOKEN_CREDENTIAL": "  'refresh-123\n'  "}
        )

        self.assertEqual(result["status"], "READ_ONLY_AUTH_VERIFIED")
        self.assertEqual(result["credential_source"], "B24_TOKEN_CREDENTIAL")
        self.assertEqual(result["credential_type"], "refresh_token")
        self.assertEqual(result["checked_endpoint"], "/properties")
        self.assertEqual(result["property_count"], 2)
        self.assertEqual(result["property_ids"], [11, 22])
        self.assertFalse(result["live_booking_mutations"])
        self.assertEqual(
            request_json.call_args_list,
            [
                mock.call(
                    "GET",
                    "/authentication/token",
                    headers={"refreshToken": "refresh-123"},
                ),
                mock.call("GET", "/properties", headers={"token": "access-123"}),
            ],
        )


if __name__ == "__main__":
    unittest.main()
