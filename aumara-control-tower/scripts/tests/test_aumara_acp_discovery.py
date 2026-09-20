import json
import pathlib
import unittest

DOC = (
    pathlib.Path(__file__).resolve().parents[3]
    / "elcid-site"
    / ".well-known"
    / "aumara-acp.json"
)


class AumaraAcpDiscoveryTests(unittest.TestCase):
    def test_document_has_radar_required_fields(self):
        data = json.loads(DOC.read_text(encoding="utf-8"))
        self.assertEqual(data["protocol_name"], "acp")
        self.assertEqual(data["protocol"]["name"], "acp")
        self.assertRegex(data["protocol"]["version"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertTrue(data["protocol"]["supported_versions"])
        self.assertTrue(data["api_base_url"].startswith("https://"))
        self.assertIn("rest", data["transports"])
        self.assertIn("rest", data["supported_transports"])
        self.assertIsInstance(data["capabilities"]["services"], list)
        self.assertEqual(data["checkout_mode"], "human-mediated-only")
        self.assertFalse(data["payment_policy"]["agent_auto_charge"])
        self.assertIn("324882", data["continue_url"])
