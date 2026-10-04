#!/usr/bin/env python3
"""Write AUMARA listing descriptions for property 324882 via Beds24 API V2.

Reads the pinned content file from commit 7637d743 and updates only property
and room description texts. Prices, photos, availability, rates, feature
codes, and channel settings are not sent.

The access token comes from BEDS24_REFRESH_CREDENTIAL, using the same
GET /authentication/details then GET /authentication/token exchange as
the bookings snapshot. V1 JSON keys are never used.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = (
    REPO_ROOT
    / "aumara-control-tower"
    / "content"
    / "beds24-standard-content-20261004.json"
)
SOURCE_SHA256 = "7af95f0e4acfb9679c2a19bb8c0db4f20cf46469da5a5970d013d0e1c4868b25"
SOURCE_COMMIT = "7637d743f4d20001870be07b1811ea7868046bf1"
PROPERTY_ID = 324882
ROOM_IDS = (674465, 674466)
API_BASES = (
    "https://api.beds24.com/v2",
    "https://beds24.com/api/v2",
)
LANGUAGES = ("ES", "EN", "RU", "DE", "FR", "IT", "PT", "NL")
LANGUAGE_CODES = {
    "ES": "es",
    "EN": "en",
    "RU": "ru",
    "DE": "de",
    "FR": "fr",
    "IT": "it",
    "PT": "pt",
    "NL": "nl",
}
PROPERTY_FIELDS = {
    "headlineText": "headline",
    "propertyDescriptionText": "propertyDescription",
    "propertyDescription1": "propertyDescription1",
    "propertyDescriptionBookingPage1": "propertyDescriptionBookingPage1",
    "locationDescription": "locationDescription",
    "houseRules": "houseRules",
}
ROOM_FIELDS = {
    "roomDescription1": "roomDescription",
    "contentDescriptionText": "contentDescription",
}
ALLOWED_NEGATIONS = (
    "No es un camping",
    "Not a campsite",
    "Это не кемпинг",
)
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
CAMPING_RE = re.compile(r"camping|campsite|кемпинг", re.IGNORECASE)
BANNED = (
    (re.compile(r"aumara\.me", re.IGNORECASE), "aumara.me"),
    (re.compile(r"directa", re.IGNORECASE), "directa"),
    (re.compile(r"CV H01453", re.IGNORECASE), "CV H01453"),
    (re.compile(r"piscina|piscine|zwembad|бассейн", re.IGNORECASE), "piscina/pool"),
    (re.compile(r"\bpool\b", re.IGNORECASE), "piscina/pool"),
    (re.compile(r"tenis|tennis|теннис", re.IGNORECASE), "tenis"),
    (re.compile(r"\bplaya\b|\bbeach\b", re.IGNORECASE), "playa"),
)


class ListingError(RuntimeError):
    """The listing-text write cannot continue."""


def mask(value: str) -> None:
    if value:
        print(f"::add-mask::{value}", flush=True)


def redact(text: str, secrets: tuple[str, ...]) -> str:
    cleaned = text
    for secret in secrets:
        if secret:
            cleaned = cleaned.replace(secret, "[REDACTED]")
    return cleaned


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def load_source(path: Path = SOURCE_PATH) -> dict[str, Any]:
    if sha256_file(path) != SOURCE_SHA256:
        raise ListingError(
            f"Refusing to write: {path} is not the file from commit {SOURCE_COMMIT}"
        )
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ListingError("Content file is not a JSON object")
    if int(document.get("property_id") or 0) != PROPERTY_ID:
        raise ListingError("Content file property_id is not 324882")
    return document


def content_change(document: dict[str, Any]) -> dict[str, Any]:
    rows = document.get("setPropertyContent")
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        raise ListingError("Content file has no setPropertyContent object")
    return rows[0]


def iter_strings(node: Any) -> list[str]:
    found: list[str] = []
    if isinstance(node, dict):
        for value in node.values():
            found.extend(iter_strings(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(iter_strings(value))
    elif isinstance(node, str):
        found.append(node)
    return found


def text_violations(text: str) -> list[str]:
    hits: list[str] = []
    if URL_RE.search(text):
        hits.append("URL")
    for pattern, label in BANNED:
        if pattern.search(text):
            hits.append(label)
    stripped = text
    for allowed in ALLOWED_NEGATIONS:
        stripped = re.sub(re.escape(allowed), "", stripped, flags=re.IGNORECASE)
    if CAMPING_RE.search(stripped):
        hits.append("camping")
    return hits


def assert_texts_allowed(node: Any, label: str) -> None:
    violations: list[str] = []
    for text in iter_strings(node):
        hits = text_violations(text)
        if hits:
            violations.append(f"{label}: {sorted(set(hits))} in {text[:160]!r}")
    if violations:
        raise ListingError("Text guard failed: " + " | ".join(violations[:8]))


def language_rows(field_map: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    by_code: dict[str, dict[str, str]] = {}
    for source_name, languages in field_map.items():
        if set(languages) != set(LANGUAGES):
            raise ListingError(
                f"{source_name} languages are {sorted(languages)}, expected {list(LANGUAGES)}"
            )
        for source_code in LANGUAGES:
            value = languages[source_code]
            if not isinstance(value, str) or not value.strip():
                raise ListingError(f"{source_name}.{source_code} is empty")
            code = LANGUAGE_CODES[source_code]
            by_code.setdefault(code, {"language": code})[source_name] = value
    return [by_code[LANGUAGE_CODES[code]] for code in LANGUAGES]


def mapped_fields(
    source_fields: dict[str, Any],
    mapping: dict[str, str],
) -> dict[str, dict[str, str]]:
    mapped: dict[str, dict[str, str]] = {}
    for source_name, api_name in mapping.items():
        value = source_fields.get(source_name)
        if not isinstance(value, dict):
            raise ListingError(f"Missing text field {source_name}")
        mapped[api_name] = value
    return mapped


def build_write_body(document: dict[str, Any]) -> list[dict[str, Any]]:
    change = content_change(document)
    property_texts = change.get("texts")
    rooms = change.get("roomIds")
    if not isinstance(property_texts, dict) or not isinstance(rooms, dict):
        raise ListingError("Content change is missing texts or roomIds")
    if set(rooms) != {str(room_id) for room_id in ROOM_IDS}:
        raise ListingError(f"Content rooms are {sorted(rooms)}, expected {list(ROOM_IDS)}")
    assert_texts_allowed(property_texts, "property")
    assert_texts_allowed(rooms, "rooms")
    room_types: list[dict[str, Any]] = []
    for room_id in ROOM_IDS:
        room = rooms[str(room_id)]
        if not isinstance(room, dict) or not isinstance(room.get("texts"), dict):
            raise ListingError(f"Room {room_id} is missing texts")
        room_types.append(
            {
                "id": room_id,
                "texts": language_rows(mapped_fields(room["texts"], ROOM_FIELDS)),
            }
        )
    return [
        {
            "id": PROPERTY_ID,
            "texts": language_rows(mapped_fields(property_texts, PROPERTY_FIELDS)),
            "roomTypes": room_types,
        }
    ]


def expected_index(body: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, str]]]:
    prop = body[0]
    rooms: dict[str, dict[str, dict[str, str]]] = {}
    for room in prop["roomTypes"]:
        rooms[str(room["id"])] = {
            row["language"]: {key: value for key, value in row.items() if key != "language"}
            for row in room["texts"]
        }
    return {
        "property": {
            row["language"]: {key: value for key, value in row.items() if key != "language"}
            for row in prop["texts"]
        },
        "rooms": rooms,
    }


def index_texts(rows: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        raise ListingError("Beds24 texts value is not a list")
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        language = str(row.get("language") or "").strip().lower()
        if language:
            indexed[language] = row
    return indexed


def compare_readback(
    expected: dict[str, Any],
    property_texts: Any,
    room_texts: dict[int, Any],
) -> list[str]:
    mismatches: list[str] = []
    actual_property = index_texts(property_texts)
    for language, fields in expected["property"].items():
        row = actual_property.get(language)
        if row is None:
            mismatches.append(f"property.{language} missing")
            continue
        for field, want in fields.items():
            if row.get(field) != want:
                mismatches.append(f"property.{language}.{field}")
    for room_id in ROOM_IDS:
        actual_room = index_texts(room_texts.get(room_id))
        for language, fields in expected["rooms"][str(room_id)].items():
            row = actual_room.get(language)
            if row is None:
                mismatches.append(f"room.{room_id}.{language} missing")
                continue
            for field, want in fields.items():
                if row.get(field) != want:
                    mismatches.append(f"room.{room_id}.{language}.{field}")
    return mismatches


def credential_from_env() -> str:
    primary = "".join((os.environ.get("BEDS24_REFRESH_CREDENTIAL") or "").split())
    primary = primary.strip('"').strip("'")
    if primary:
        return primary
    legacy = "".join((os.environ.get("BEDS24_REFRESH_TOKEN") or "").split())
    return legacy.strip('"').strip("'")


def request_json(
    method: str,
    url: str,
    headers: dict[str, str],
    payload: Any = None,
    secrets: tuple[str, ...] = (),
) -> tuple[int, Any, str]:
    data = None
    sent_headers = {"Accept": "application/json", "User-Agent": "AUMARA-ListingDescriptions/1", **headers}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        sent_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=sent_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            status = int(response.status)
            raw = response.read()
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        raw = exc.read()
    except urllib.error.URLError as exc:
        raise ListingError(f"{method} {url} failed: {exc.reason}") from exc
    decoded = raw.decode("utf-8", "replace")
    redacted = redact(decoded, secrets)
    if not decoded:
        body: Any = {}
    else:
        try:
            body = json.loads(decoded)
        except json.JSONDecodeError:
            body = {"error": redacted[:800]}
    return status, body, redacted


def failure_text(method: str, url: str, status: int, body: Any, raw: str) -> str:
    if isinstance(body, dict):
        public = {key: value for key, value in body.items() if "token" not in key.lower()}
        detail = json.dumps(public, ensure_ascii=False)
    else:
        detail = raw
    return f"{method} {url} HTTP {status}: {detail[:1200]}"


def exchange_token(credential: str) -> tuple[str, str, tuple[str, ...]]:
    mask(credential)
    secrets = [credential]
    errors: list[str] = []
    for base in API_BASES:
        status, body, raw = request_json(
            "GET",
            base + "/authentication/details",
            {"token": credential},
            secrets=tuple(secrets),
        )
        if 200 <= status < 300 and isinstance(body, dict) and body.get("validToken") is True:
            return credential, base, tuple(secrets)
        errors.append(failure_text("GET", base + "/authentication/details", status, body, raw))
        status, body, raw = request_json(
            "GET",
            base + "/authentication/token",
            {"refreshToken": credential},
            secrets=tuple(secrets),
        )
        token = ""
        rotated = ""
        if isinstance(body, dict):
            token = str(body.get("token") or "").strip()
            rotated = str(body.get("refreshToken") or "").strip()
        mask(token)
        mask(rotated)
        if token:
            secrets.append(token)
        if rotated:
            secrets.append(rotated)
        if 200 <= status < 300 and token:
            return token, base, tuple(secrets)
        errors.append(failure_text("GET", base + "/authentication/token", status, body, raw))
    raise ListingError(" || ".join(errors))


def property_url(base: str) -> str:
    query = urllib.parse.urlencode(
        {
            "id": str(PROPERTY_ID),
            "includeAllRooms": "true",
            "includeTexts": "all",
            "includeLanguages": "all",
        }
    )
    return f"{base}/properties?{query}"


def fetch_property(token: str, base: str, secrets: tuple[str, ...]) -> dict[str, Any]:
    url = property_url(base)
    status, body, raw = request_json("GET", url, {"token": token}, secrets=secrets)
    if not 200 <= status < 300 or (isinstance(body, dict) and body.get("success") is False):
        raise ListingError(failure_text("GET", url, status, body, raw))
    rows = body.get("data") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        raise ListingError("GET /properties response did not contain a data array")
    matches = [row for row in rows if isinstance(row, dict) and int(row.get("id") or 0) == PROPERTY_ID]
    if len(matches) != 1:
        raise ListingError(f"GET /properties returned {len(matches)} rows for {PROPERTY_ID}")
    return matches[0]


def room_map(prop: dict[str, Any]) -> dict[int, dict[str, Any]]:
    rooms = prop.get("roomTypes")
    if not isinstance(rooms, list):
        raise ListingError("Property response has no roomTypes list")
    found: dict[int, dict[str, Any]] = {}
    for room in rooms:
        if isinstance(room, dict) and room.get("id") is not None:
            found[int(room["id"])] = room
    missing = [room_id for room_id in ROOM_IDS if room_id not in found]
    if missing:
        raise ListingError(f"Property {PROPERTY_ID} is missing rooms {missing}")
    return found


def text_snapshot(prop: dict[str, Any]) -> dict[str, Any]:
    rooms = room_map(prop)
    return {
        "schema": "aumara.beds24-content-backup.v1",
        "property_id": PROPERTY_ID,
        "room_ids": list(ROOM_IDS),
        "fetched_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_commit": SOURCE_COMMIT,
        "source_sha256": SOURCE_SHA256,
        "property_texts": prop.get("texts") if isinstance(prop.get("texts"), list) else [],
        "rooms": {
            str(room_id): rooms[room_id].get("texts")
            if isinstance(rooms[room_id].get("texts"), list)
            else []
            for room_id in ROOM_IDS
        },
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def require_backup(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ListingError(f"Refusing to write before backup exists: {path}")
    backup = json.loads(path.read_text(encoding="utf-8"))
    if int(backup.get("property_id") or 0) != PROPERTY_ID:
        raise ListingError("Backup property_id is not 324882")
    rooms = backup.get("rooms")
    if not isinstance(rooms, dict) or any(str(room_id) not in rooms for room_id in ROOM_IDS):
        raise ListingError("Backup is missing one of the room text arrays")
    if not isinstance(backup.get("property_texts"), list):
        raise ListingError("Backup is missing the property text array")
    return backup


def post_texts(
    token: str,
    base: str,
    secrets: tuple[str, ...],
    body: list[dict[str, Any]],
) -> Any:
    url = base + "/properties"
    status, response, raw = request_json(
        "POST",
        url,
        {"token": token},
        body,
        secrets,
    )
    detail = failure_text("POST", url, status, response, raw)
    if status in (401, 403) or (isinstance(response, dict) and response.get("code") in (401, 403)):
        raise ListingError(detail)
    if isinstance(response, dict) and response.get("success") is False:
        raise ListingError(detail)
    if not 200 <= status < 300:
        raise ListingError(detail)
    rows = response if isinstance(response, list) else [response]
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("success") is False or row.get("errors"):
            raise ListingError(detail)
    return response


def run_guard() -> None:
    document = load_source()
    body = build_write_body(document)
    print(json.dumps({"status": "GUARDED", "languages": list(LANGUAGES), "rooms": list(ROOM_IDS)}))
    assert_texts_allowed(body, "write-body")


def run_backup(output: Path) -> None:
    document = load_source()
    build_write_body(document)
    credential = credential_from_env()
    if not credential:
        raise ListingError("BEDS24_REFRESH_CREDENTIAL is missing")
    token, base, secrets = exchange_token(credential)
    prop = fetch_property(token, base, secrets)
    snapshot = text_snapshot(prop)
    snapshot["api_base"] = base
    write_json(output, snapshot)
    print(
        json.dumps(
            {
                "status": "BACKUP_SAVED",
                "path": str(output),
                "property_text_rows": len(snapshot["property_texts"]),
                "room_text_rows": {
                    room_id: len(snapshot["rooms"][room_id]) for room_id in snapshot["rooms"]
                },
            }
        )
    )


def run_apply(backup_path: Path, verify_path: Path) -> None:
    require_backup(backup_path)
    document = load_source()
    body = build_write_body(document)
    expected = expected_index(body)
    credential = credential_from_env()
    if not credential:
        raise ListingError("BEDS24_REFRESH_CREDENTIAL is missing")
    token, base, secrets = exchange_token(credential)
    response = post_texts(token, base, secrets, body)
    time.sleep(4)
    prop = fetch_property(token, base, secrets)
    rooms = room_map(prop)
    mismatches = compare_readback(
        expected,
        prop.get("texts"),
        {room_id: rooms[room_id].get("texts") for room_id in ROOM_IDS},
    )
    written = {
        "property": {
            language: sorted(fields)
            for language, fields in expected["property"].items()
        },
        "rooms": {
            room_id: {
                language: sorted(fields)
                for language, fields in expected["rooms"][room_id].items()
            }
            for room_id in expected["rooms"]
        },
    }
    evidence = {
        "schema": "aumara.beds24-listing-descriptions-verify.v1",
        "property_id": PROPERTY_ID,
        "room_ids": list(ROOM_IDS),
        "verified_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_commit": SOURCE_COMMIT,
        "source_sha256": SOURCE_SHA256,
        "backup_path": str(backup_path),
        "api_base": base,
        "fields_written": written,
        "not_written": ["feature_codes", "airbnb", "prices", "pictures", "availability", "rates"],
        "mismatches": mismatches,
        "post_success_flags": [
            row.get("success") for row in response if isinstance(row, dict)
        ] if isinstance(response, list) else None,
        "status": "SUCCESS" if not mismatches else "FAILED_READBACK",
        "secret_exposed": False,
    }
    write_json(verify_path, evidence)
    print(json.dumps({"status": evidence["status"], "mismatches": mismatches[:30]}))
    if mismatches:
        raise ListingError("Read-back did not match the written descriptions: " + ", ".join(mismatches[:30]))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("guard")
    backup = sub.add_parser("backup")
    backup.add_argument("--output", type=Path, required=True)
    apply = sub.add_parser("apply")
    apply.add_argument("--backup", type=Path, required=True)
    apply.add_argument("--verify", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.command == "guard":
        run_guard()
    elif args.command == "backup":
        run_backup(args.output)
    elif args.command == "apply":
        run_apply(args.backup, args.verify)
    else:
        raise ListingError(f"Unknown command {args.command}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ListingError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
