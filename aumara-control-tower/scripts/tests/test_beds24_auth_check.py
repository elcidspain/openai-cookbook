import importlib.util
import io
import json
import pathlib
import stat
import sys
import tempfile
import unittest
from unittest import mock


SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))
SPEC = importlib.util.spec_from_file_location(
    "beds24_auth_check",
    SCRIPTS_DIR / "beds24_auth_check.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class Beds24AuthCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp_dir.name)
        self.evidence_path = self.root / "beds24-auth-check.json"
        self.token_path = self.root / "beds24-access-token"
        self.patches = [
            mock.patch.object(MODULE, "EVIDENCE_PATH", self.evidence_path),
            mock.patch.object(MODULE, "ACCESS_TOKEN_FILE", self.token_path),
        ]
        for patcher in self.patches:
            patcher.start()
        self.addCleanup(self.stop_patches)
        self.addCleanup(self.temp_dir.cleanup)

    def stop_patches(self):
        for patcher in reversed(self.patches):
            patcher.stop()

    def load_evidence(self):
        return json.loads(self.evidence_path.read_text(encoding="utf-8"))

    @mock.patch.dict("os.environ", {"BEDS24_TOKEN_CREDENTIAL": " refresh-secret \n"})
    def test_validate_records_refresh_credential_presence(self):
        result = MODULE.command_validate()
        evidence = self.load_evidence()
        self.assertEqual(result, 0)
        self.assertEqual(evidence["status"], "CREDENTIAL_PRESENT")
        self.assertEqual(evidence["credential_source"], "BEDS24_TOKEN_CREDENTIAL")
        self.assertTrue(evidence["secret_present"])
        self.assertEqual(evidence["secret_length"], len("refresh-secret"))

    def test_validate_fails_closed_when_secret_is_missing(self):
        with (
            mock.patch.dict("os.environ", {}, clear=True),
            mock.patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            result = MODULE.command_validate()
        evidence = self.load_evidence()
        self.assertEqual(result, 1)
        self.assertEqual(evidence["failure_stage"], "validate")
        self.assertIn("BEDS24_TOKEN_CREDENTIAL", stderr.getvalue())

    @mock.patch.dict("os.environ", {"BEDS24_TOKEN_CREDENTIAL": "refresh-secret"})
    def test_exchange_and_probe_use_refresh_then_access_token(self):
        observed_headers = []

        class FakeResponse:
            def __init__(self, status, payload):
                self.status = status
                self.payload = payload

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(self.payload).encode("utf-8")

        def fake_urlopen(request, timeout=45):
            self.assertEqual(timeout, 45)
            headers = {key.lower(): value for key, value in request.header_items()}
            observed_headers.append(headers)
            if request.full_url.endswith("/authentication/token"):
                self.assertEqual(headers["refreshtoken"], "refresh-secret")
                self.assertNotIn("token", headers)
                return FakeResponse(200, {"token": "access-secret", "expiresIn": 3600})
            self.assertEqual(
                request.full_url,
                f"{MODULE.API_BASE}/authentication/details",
            )
            self.assertEqual(headers["token"], "access-secret")
            self.assertNotIn("refreshtoken", headers)
            return FakeResponse(200, {"status": "ok"})

        with mock.patch.object(MODULE.urllib.request, "urlopen", side_effect=fake_urlopen):
            self.assertEqual(MODULE.command_exchange(), 0)
            self.assertTrue(self.token_path.exists())
            self.assertEqual(
                stat.S_IMODE(self.token_path.stat().st_mode),
                stat.S_IRUSR | stat.S_IWUSR,
            )
            self.assertEqual(MODULE.command_probe(), 0)

        evidence = self.load_evidence()
        self.assertEqual(len(observed_headers), 2)
        self.assertEqual(evidence["status"], "AUTH_OK")
        self.assertEqual(evidence["token_exchange_http_status"], 200)
        self.assertEqual(evidence["readonly_probe_http_status"], 200)
        self.assertFalse(self.token_path.exists())
        self.assertNotIn("refresh-secret", json.dumps(evidence))
        self.assertNotIn("access-secret", json.dumps(evidence))

    @mock.patch.dict("os.environ", {"BEDS24_TOKEN_CREDENTIAL": "bad-refresh"})
    @mock.patch.object(
        MODULE,
        "request_json",
        return_value=(401, {"message": "Token bad-refresh not valid", "code": 401}),
    )
    def test_exchange_failure_is_redacted(self, request_json):
        with mock.patch("sys.stderr", new_callable=io.StringIO) as stderr:
            result = MODULE.command_exchange()
        evidence = self.load_evidence()
        self.assertEqual(result, 1)
        self.assertEqual(evidence["failure_stage"], "exchange")
        self.assertEqual(evidence["token_exchange_http_status"], 401)
        self.assertNotIn("bad-refresh", json.dumps(evidence))
        self.assertIn(MODULE.REDACTED, json.dumps(evidence))
        self.assertIn("HTTP status 401", stderr.getvalue())
        request_json.assert_called_once_with(
            f"{MODULE.API_BASE}/authentication/token",
            {"refreshToken": "bad-refresh"},
            secrets=("bad-refresh",),
            redact=False,
        )

    def test_probe_requires_temporary_access_token(self):
        with mock.patch("sys.stderr", new_callable=io.StringIO) as stderr:
            result = MODULE.command_probe()
        evidence = self.load_evidence()
        self.assertEqual(result, 1)
        self.assertEqual(evidence["failure_stage"], "probe")
        self.assertIn("access token file is missing", stderr.getvalue())

    def test_probe_failure_is_redacted_and_token_file_is_removed(self):
        self.token_path.write_text("access-secret", encoding="utf-8")
        with mock.patch.object(
            MODULE,
            "request_json",
            return_value=(403, {"detail": "Access token access-secret rejected"}),
        ):
            with mock.patch("sys.stderr", new_callable=io.StringIO):
                result = MODULE.command_probe()
        evidence = self.load_evidence()
        self.assertEqual(result, 1)
        self.assertEqual(evidence["failure_stage"], "probe")
        self.assertNotIn("access-secret", json.dumps(evidence))
        self.assertFalse(self.token_path.exists())

    def test_request_json_redacts_http_error_body(self):
        response = mock.Mock()
        response.read.return_value = b'{"message":"Denied refresh-secret","status":401}'
        error = MODULE.urllib.error.HTTPError(
            url="https://example.test",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=response,
        )
        with mock.patch.object(MODULE.urllib.request, "urlopen", side_effect=error):
            status, body = MODULE.request_json(
                "https://example.test",
                {"refreshToken": "refresh-secret"},
                secrets=("refresh-secret",),
            )
        self.assertEqual(status, 401)
        self.assertEqual(body["message"], "Denied [REDACTED]")

    def test_parse_args_supports_exchange_flow(self):
        for command in ("validate", "exchange", "probe", "report"):
            with self.subTest(command=command):
                with mock.patch.object(sys, "argv", ["beds24_auth_check.py", command]):
                    self.assertEqual(MODULE.parse_args().command, command)

    def test_report_summarizes_exchange_failure(self):
        MODULE.save_evidence(
            {
                "status": "AUTH_FAILED",
                "failure_stage": "exchange",
                "token_exchange_http_status": 401,
                "token_exchange_diagnostics": {
                    "message": "Token not valid",
                    "code": 401,
                },
                "readonly_probe_http_status": None,
                "readonly_probe_diagnostics": {},
                "credential_source": "BEDS24_TOKEN_CREDENTIAL",
                "secret_present": True,
                "secret_length": 16,
                "secret_exposed": False,
            }
        )
        with mock.patch("sys.stderr", new_callable=io.StringIO) as stderr:
            result = MODULE.command_report()
        self.assertEqual(result, 1)
        self.assertIn("failed during exchange", stderr.getvalue())
        self.assertIn("HTTP status: 401", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
