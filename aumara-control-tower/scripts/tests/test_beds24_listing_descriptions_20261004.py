from __future__ import annotations

import json
import pathlib
import sys
import unittest


SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import beds24_listing_descriptions_20261004 as listing  # noqa: E402


SOURCE = (SCRIPTS / "beds24_listing_descriptions_20261004.py").read_text(encoding="utf-8")


class ListingDescriptionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = listing.load_source()
        self.body = listing.build_write_body(self.document)

    def test_source_hash_and_guard(self) -> None:
        listing.assert_texts_allowed(self.body, "write-body")
        self.assertEqual(listing.sha256_file(listing.SOURCE_PATH), listing.SOURCE_SHA256)
        self.assertNotIn("aumara.me", json.dumps(self.body).lower())
        self.assertNotIn("directa", json.dumps(self.body).lower())

    def test_write_body_is_text_only(self) -> None:
        self.assertEqual(list(self.body[0]), ["id", "texts", "roomTypes"])
        self.assertEqual(self.body[0]["id"], 324882)
        self.assertEqual(
            [room["id"] for room in self.body[0]["roomTypes"]],
            [674465, 674466],
        )
        property_fields = set()
        languages = []
        for row in self.body[0]["texts"]:
            languages.append(row["language"])
            property_fields.update(key for key in row if key != "language")
        self.assertEqual(languages, ["es", "en", "ru", "de", "fr", "it", "pt", "nl"])
        self.assertEqual(
            property_fields,
            {
                "headline",
                "propertyDescription",
                "propertyDescription1",
                "propertyDescriptionBookingPage1",
                "locationDescription",
                "houseRules",
            },
        )
        for room in self.body[0]["roomTypes"]:
            self.assertEqual(list(room), ["id", "texts"])
            room_fields = set()
            room_languages = []
            for row in room["texts"]:
                room_languages.append(row["language"])
                room_fields.update(key for key in row if key != "language")
            self.assertEqual(room_languages, languages)
            self.assertEqual(room_fields, {"roomDescription", "contentDescription"})
        encoded = json.dumps(self.body)
        for forbidden in ("featureCodes", "airbnb", "price", "picture", "minStay"):
            self.assertNotIn(forbidden, encoded)

    def test_german_rows_keep_the_english_overwrite(self) -> None:
        german = next(row for row in self.body[0]["texts"] if row["language"] == "de")
        english = next(row for row in self.body[0]["texts"] if row["language"] == "en")
        self.assertEqual(german["propertyDescription1"], english["propertyDescription1"])
        self.assertIn("6 independent houses", german["headline"])

    def test_camping_only_as_negation_and_banned_words_fail(self) -> None:
        spanish = next(row for row in self.body[0]["texts"] if row["language"] == "es")
        self.assertIn("No es un camping", spanish["propertyDescription1"])
        self.assertEqual(listing.text_violations("No es un camping"), [])
        self.assertIn("aumara.me", listing.text_violations("see aumara.me"))
        self.assertIn("directa", listing.text_violations("reserva directa"))
        self.assertIn("URL", listing.text_violations("https://example.com"))
        self.assertIn("camping", listing.text_violations("there is camping nearby"))
        self.assertIn("piscina/pool", listing.text_violations("shared pool"))
        self.assertIn("playa", listing.text_violations("cerca de la playa"))

    def test_readback_comparison(self) -> None:
        expected = listing.expected_index(self.body)
        property_texts = self.body[0]["texts"]
        room_texts = {
            room["id"]: room["texts"] for room in self.body[0]["roomTypes"]
        }
        self.assertEqual(listing.compare_readback(expected, property_texts, room_texts), [])
        broken = json.loads(json.dumps(property_texts))
        broken[0]["headline"] = "shared pool"
        mismatches = listing.compare_readback(expected, broken, room_texts)
        self.assertEqual(mismatches, ["property.es.headline"])

    def test_script_does_not_call_v1(self) -> None:
        self.assertNotIn("BEDS24_API_KEY", SOURCE)
        self.assertNotIn("BEDS24_PROP_KEY", SOURCE)
        self.assertNotIn("api.beds24.com/json", SOURCE)
        self.assertIn("BEDS24_REFRESH_CREDENTIAL", SOURCE)
        self.assertIn("/authentication/token", SOURCE)


if __name__ == "__main__":
    unittest.main()
