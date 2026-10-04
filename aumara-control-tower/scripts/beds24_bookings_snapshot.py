#!/usr/bin/env python3
"""Read-only daily Beds24 bookings snapshot for AUMARA and the rest of the account.

The script exchanges BEDS24_REFRESH_CREDENTIAL for a short-lived access token,
then issues GET requests only. It writes a short Russian markdown report.
Guest lines use a first name and, for booking rows, a surname initial.
Phone numbers, email addresses, and full surnames are not printed.
Manual stays come from bookings/manual.json and are marked «не в Beds24».
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


MADRID = ZoneInfo("Europe/Madrid")
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANUAL = REPO_ROOT / "bookings" / "manual.json"
API_BASES = (
    "https://api.beds24.com/v2",
    "https://beds24.com/api/v2",
)
WINDOW_NIGHTS = 30
WEEK_DAYS = 7
INACTIVE = {"cancelled", "canceled", "black", "inquiry", "no_show"}
CANCELLED = {"cancelled", "canceled"}
HOST_SOURCES = {"host", "property", "owner"}
EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+\s*\d[\d\s().-]{7,}\d)|(?:\b\d{9,}\b)")
CHANNEL_NAMES = {
    "booking": "Booking.com",
    "booking.com": "Booking.com",
    "bookingcom": "Booking.com",
    "airbnb": "Airbnb",
    "airbnb.com": "Airbnb",
    "expedia": "Expedia",
    "agoda": "Agoda",
    "direct": "direct",
    "manual": "direct",
    "api": "direct",
    "beds24": "direct",
    "ical": "iCal",
    "vrbo": "Vrbo",
    "homeaway": "Vrbo",
}
SOURCE_CODES = {"0": "direct", "19": "Booking.com", "46": "Airbnb"}
NAME_TO_ID = {"aumara": 324882, "el cid": 324903, "elcid": 324903}


class SnapshotError(RuntimeError):
    """The read-only snapshot cannot produce a reliable report."""


class MessagesScopeError(RuntimeError):
    """GET /bookings/messages was refused because the token lacks that scope."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


@dataclass(frozen=True)
class Room:
    property_id: int
    room_id: int
    name: str
    units: int


@dataclass(frozen=True)
class Property:
    property_id: int
    name: str
    rooms: tuple[Room, ...]


@dataclass(frozen=True)
class Stay:
    booking_id: int | None
    property_id: int
    property_name: str
    room_id: int | None
    room_qty: int
    status: str
    arrival: dt.date
    departure: dt.date
    adults: int
    children: int
    dogs: int
    guest_label: str
    channel: str
    price: float
    currency: str
    paid: bool | None
    created_at: dt.datetime | None
    modified_at: dt.datetime | None
    cancelled_at: dt.datetime | None
    manual: bool


@dataclass(frozen=True)
class BookingFace:
    booking_id: int
    property_id: int | None
    first_name: str
    channel: str


@dataclass(frozen=True)
class GuestMessage:
    booking_id: int
    property_id: int | None
    guest_label: str
    channel: str
    sent_at: dt.datetime
    excerpt: str


def _fallback_properties() -> list[Property]:
    return [
        Property(
            324882,
            "AUMARA",
            (
                Room(324882, 674465, "Chalet", 4),
                Room(324882, 674466, "Superior Chalet", 2),
            ),
        ),
        Property(
            324903,
            "EL CID",
            (
                Room(324903, 674484, "Triple Room", 1),
                Room(324903, 674485, "Twin Room with Terrace", 4),
                Room(324903, 674486, "Studio", 1),
            ),
        ),
    ]


FALLBACK_PROPERTIES = _fallback_properties()
FALLBACK_BY_ID = {item.property_id: item for item in FALLBACK_PROPERTIES}


def mask(value: str) -> None:
    if value:
        print(f"::add-mask::{value}", flush=True)


def redact(text: str, secrets: tuple[str, ...]) -> str:
    cleaned = text
    for secret in secrets:
        if secret:
            cleaned = cleaned.replace(secret, "[REDACTED]")
    return cleaned


def one_line(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def excerpt(text: str, limit: int = 200) -> str:
    flat = EMAIL_RE.sub("[скрыто]", one_line(text))
    flat = PHONE_RE.sub("[скрыто]", flat)
    return flat[:limit]


def plural(number: int, one: str, few: str, many: str) -> str:
    value = abs(int(number))
    if value % 10 == 1 and value % 100 != 11:
        return one
    if 2 <= (value % 10) <= 4 and not 12 <= (value % 100) <= 14:
        return few
    return many


def ru_nights(number: int) -> str:
    return f"{number} {plural(number, 'ночь', 'ночи', 'ночей')}"


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_id(value: Any) -> int | None:
    number = as_int(value, 0)
    return number or None


def as_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def parse_date(value: Any) -> dt.date | None:
    text = str(value or "").strip()
    if len(text) < 10:
        return None
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def parse_ts(value: Any) -> dt.datetime | None:
    text = str(value or "").strip()
    if not text or text.startswith("0000"):
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed: dt.datetime | None
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        parsed = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = dt.datetime.strptime(text, fmt)
                break
            except ValueError:
                parsed = None
        if parsed is None:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def first_name_only(value: str) -> str:
    token = one_line(value).split(" ")[0] if one_line(value) else ""
    letters = "".join(ch for ch in token if ch.isalpha() or ch in "-'")
    if not letters or "@" in token:
        return "Гость"
    return letters


def guest_label(first: str, last: str) -> str:
    name = first_name_only(first)
    if name == "Гость" and not one_line(first):
        name = "Гость"
    initial = next((ch.upper() for ch in one_line(last) if ch.isalpha()), "")
    if name != "Гость" and initial:
        return f"{name} {initial}."
    return name


def label_from_guest_field(value: str) -> str:
    parts = [part for part in one_line(value).replace(".", " ").split(" ") if part]
    if not parts:
        return "Гость"
    first = first_name_only(parts[0])
    if len(parts) == 1:
        return first
    initial = next((ch.upper() for ch in parts[1] if ch.isalpha()), "")
    if initial and first != "Гость":
        return f"{first} {initial}."
    return first


def map_channel_text(value: str) -> str | None:
    text = one_line(value)
    if not text or "@" in text or len(text) > 40 or re.search(r"\d{6,}", text):
        return None
    if text.isdigit():
        return None
    mapped = CHANNEL_NAMES.get(text.casefold())
    return mapped or text


def channel_label(row: dict[str, Any]) -> str:
    channel = str(row.get("channel") or "").strip()
    referer = str(row.get("referer") or row.get("bookingSource") or "").strip()
    api_source = str(row.get("apiSource") or "").strip()
    for candidate in (channel, referer):
        mapped = map_channel_text(candidate)
        if mapped:
            return mapped
    if api_source in SOURCE_CODES:
        return SOURCE_CODES[api_source]
    mapped = map_channel_text(api_source)
    if mapped:
        return mapped
    if api_source:
        return f"канал {api_source}"
    return "direct"


def build_get_request(url: str, headers: dict[str, str]) -> urllib.request.Request:
    return urllib.request.Request(url, data=None, headers=headers, method="GET")


def public_error(body: Any) -> str:
    return verbatim_body(body)


_SECRET_KEYS = {"token", "refreshtoken", "accesstoken", "secret"}
_SECRET_FIELD = re.compile(
    r'("(?:token|refreshToken|accessToken|secret)"\s*:\s*")((?:[^"\\]|\\.)*)(")',
    re.IGNORECASE,
)


def scrub_value(value: Any, secrets: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in _SECRET_KEYS:
                cleaned[str(key)] = "[REDACTED]"
            else:
                cleaned[str(key)] = scrub_value(item, secrets)
        return cleaned
    if isinstance(value, list):
        return [scrub_value(item, secrets) for item in value]
    if isinstance(value, str):
        return redact(value, secrets)
    return value


def scrub_raw(text: str, secrets: tuple[str, ...] = ()) -> str:
    """Keep the response bytes aside from credential fields and known secret strings."""
    cleaned = redact(text, secrets)
    return _SECRET_FIELD.sub(lambda match: match.group(1) + "[REDACTED]" + match.group(3), cleaned)


def verbatim_body(body: Any, secrets: tuple[str, ...] = (), raw: str | None = None) -> str:
    """Return an API body with credential fields removed and the rest unchanged."""
    if raw is not None:
        return scrub_raw(raw, secrets)
    if isinstance(body, (dict, list)):
        return json.dumps(scrub_value(body, secrets), ensure_ascii=False)
    return redact(str(body), secrets)


def log_api_call(
    url: str,
    status: int,
    body: Any,
    secrets: tuple[str, ...] = (),
    raw: str | None = None,
) -> None:
    """Print status for every GET. Error and auth bodies are verbatim, with secrets removed."""
    path = url.split("?", 1)[0]
    failed = not 200 <= status < 300 or (isinstance(body, dict) and body.get("success") is False)
    if failed or "/authentication/" in path:
        print(
            f"beds24_api GET {path} HTTP {status} {verbatim_body(body, secrets, raw)}",
            file=sys.stderr,
        )
        return
    rows = body.get("data") if isinstance(body, dict) else None
    count = len(rows) if isinstance(rows, list) else None
    print(f"beds24_api GET {path} HTTP {status} rows={count}", file=sys.stderr)


def http_failure(
    path: str,
    status: int,
    body: Any,
    secrets: tuple[str, ...] = (),
    raw: str | None = None,
) -> str:
    return f"GET {path.split('?', 1)[0]} HTTP {status}: {verbatim_body(body, secrets, raw)}"


class GetClient:
    """Beds24 client that can only perform GET requests."""

    def __init__(
        self,
        api_base: str,
        token: str,
        opener: Any = urllib.request.urlopen,
        secrets: tuple[str, ...] = (),
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.token = token
        self.opener = opener
        self.secrets = secrets

    def get_json(self, path: str) -> tuple[int, Any]:
        base_path = path.split("?", 1)[0]
        if not base_path.startswith("/"):
            raise SnapshotError("Refusing a non-relative Beds24 path")
        request = build_get_request(
            self.api_base + path,
            {
                "Accept": "application/json",
                "token": self.token,
                "User-Agent": "AUMARA-BookingsSnapshot/1",
            },
        )
        try:
            with self.opener(request, timeout=60) as response:
                status = int(getattr(response, "status", 200))
                raw = response.read()
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            raw = exc.read()
        except urllib.error.URLError as exc:
            raise SnapshotError(f"GET {base_path} failed: {exc.reason}") from exc
        decoded = raw.decode("utf-8", "replace")
        text = scrub_raw(decoded, self.secrets)
        self.last_raw = text
        if not decoded:
            body: Any = {}
        else:
            try:
                body = json.loads(decoded)
            except json.JSONDecodeError:
                body = {"error": text}
        log_api_call(self.api_base + path, status, body, self.secrets, text)
        return status, body


def raw_get(
    opener: Any,
    url: str,
    headers: dict[str, str],
    secrets: tuple[str, ...],
) -> tuple[int, Any]:
    request = build_get_request(
        url,
        {
            "Accept": "application/json",
            "User-Agent": "AUMARA-BookingsSnapshot/1",
            **headers,
        },
    )
    try:
        with opener(request, timeout=60) as response:
            status = int(getattr(response, "status", 200))
            raw = response.read()
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        raw = exc.read()
    except urllib.error.URLError as exc:
        raise SnapshotError(f"GET {url} failed: {exc.reason}") from exc
    decoded = raw.decode("utf-8", "replace")
    text = scrub_raw(decoded, secrets)
    if not decoded:
        body: Any = {}
    else:
        try:
            body = json.loads(decoded)
        except json.JSONDecodeError:
            body = {"error": text}
    log_api_call(url, status, body, secrets, text)
    return status, body, text


def credential_from_env() -> tuple[str, str]:
    primary = "".join((os.environ.get("BEDS24_REFRESH_CREDENTIAL") or "").split())
    primary = primary.strip('"').strip("'")
    if primary:
        return primary, "BEDS24_REFRESH_CREDENTIAL"
    legacy = "".join((os.environ.get("BEDS24_REFRESH_TOKEN") or "").split())
    legacy = legacy.strip('"').strip("'")
    if legacy:
        return legacy, "BEDS24_REFRESH_TOKEN"
    return "", "BEDS24_REFRESH_CREDENTIAL"


def exchange_token(opener: Any, credential: str) -> tuple[str, str]:
    """Reuse the repo auth flow: details probe, then refresh-token exchange."""
    mask(credential)
    errors: list[str] = []
    for base in API_BASES:
        status, body, raw = raw_get(
            opener,
            base + "/authentication/details",
            {"token": credential},
            (credential,),
        )
        if (
            200 <= status < 300
            and isinstance(body, dict)
            and body.get("validToken") is True
        ):
            return credential, base
        details_failure = http_failure(
            base + "/authentication/details",
            status,
            body,
            (credential,),
            raw,
        )
        status, body, raw = raw_get(
            opener,
            base + "/authentication/token",
            {"refreshToken": credential},
            (credential,),
        )
        token = ""
        rotated = ""
        if isinstance(body, dict):
            token = str(body.get("token") or "").strip()
            rotated = str(body.get("refreshToken") or "").strip()
        mask(token)
        mask(rotated)
        if 200 <= status < 300 and token:
            return token, base
        errors.append(details_failure)
        errors.append(
            http_failure(
                base + "/authentication/token",
                status,
                body,
                (credential, token, rotated),
                raw,
            )
        )
    raise SnapshotError(" || ".join(errors))


def interpret_get(client: GetClient, path: str, *, messages: bool = False) -> Any:
    status, body = client.get_json(path)
    failed = not 200 <= status < 300 or (
        isinstance(body, dict) and body.get("success") is False
    )
    if not failed:
        return body
    detail = http_failure(path, status, body, raw=getattr(client, "last_raw", None))
    if messages and (status in (401, 403) or "scope" in detail.casefold()):
        raise MessagesScopeError(status, detail)
    raise SnapshotError(detail)


def data_rows(body: Any, path: str) -> list[dict[str, Any]]:
    if isinstance(body, dict) and isinstance(body.get("data"), list):
        rows = body["data"]
    elif isinstance(body, list):
        rows = body
    else:
        raise SnapshotError(f"GET {path} response did not contain a data array")
    return [row for row in rows if isinstance(row, dict)]


def paged(
    client: GetClient,
    path: str,
    params: list[tuple[str, str]],
    *,
    messages: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[Any] = set()
    for page in range(1, 51):
        query = list(params)
        if page > 1:
            query.append(("page", str(page)))
        full = path + "?" + urllib.parse.urlencode(query)
        body = interpret_get(client, full, messages=messages)
        fresh = 0
        for row in data_rows(body, path):
            key = row.get("id")
            if key is not None:
                if key in seen:
                    continue
                seen.add(key)
            rows.append(row)
            fresh += 1
        pages = body.get("pages") if isinstance(body, dict) else None
        if not (isinstance(pages, dict) and pages.get("nextPageExists")):
            return rows
        if fresh == 0:
            return rows
    raise SnapshotError(f"GET {path} exceeded 50 pages")


def sort_properties(properties: list[Property]) -> list[Property]:
    return sorted(
        properties,
        key=lambda item: (
            0 if item.property_id == 324882 else 1,
            item.name.casefold(),
            item.property_id,
        ),
    )


def parse_property(row: dict[str, Any]) -> Property | None:
    property_id = as_id(row.get("id") or row.get("propertyId"))
    if property_id is None:
        return None
    name = one_line(str(row.get("name") or f"Объект {property_id}")) or f"Объект {property_id}"
    rooms: list[Room] = []
    raw_rooms = row.get("roomTypes") or row.get("rooms") or []
    if isinstance(raw_rooms, list):
        for room in raw_rooms:
            if not isinstance(room, dict):
                continue
            room_id = as_id(room.get("id") or room.get("roomId"))
            if room_id is None:
                continue
            units = as_int(room.get("qty") or room.get("physicalUnits") or room.get("units") or 1, 1)
            if units < 1:
                units = 1
            room_name = one_line(str(room.get("name") or f"комната {room_id}"))
            rooms.append(Room(property_id, room_id, room_name, units))
    rooms.sort(key=lambda item: (item.name.casefold(), item.room_id))
    return Property(property_id, name, tuple(rooms))


def fill_known_rooms(properties: list[Property]) -> list[Property]:
    filled: list[Property] = []
    for prop in properties:
        if prop.rooms:
            filled.append(prop)
            continue
        fallback = FALLBACK_BY_ID.get(prop.property_id)
        if fallback is None:
            filled.append(prop)
            continue
        filled.append(Property(prop.property_id, prop.name or fallback.name, fallback.rooms))
    return sort_properties(filled)


def fetch_properties(client: GetClient) -> list[Property]:
    try:
        rows = paged(client, "/properties", [("includeAllRooms", "true")])
    except SnapshotError as exc:
        if "HTTP 400" not in str(exc):
            raise
        rows = paged(client, "/properties", [])
    properties = [parsed for row in rows if (parsed := parse_property(row)) is not None]
    if not properties:
        raise SnapshotError("GET /properties returned no properties")
    return fill_known_rooms(properties)


def project_booking(row: dict[str, Any]) -> tuple[Stay, BookingFace] | None:
    booking_id = as_id(row.get("id"))
    property_id = as_id(row.get("propertyId"))
    arrival = parse_date(row.get("arrival"))
    departure = parse_date(row.get("departure"))
    if not booking_id or not property_id or not arrival or not departure or departure <= arrival:
        return None
    first = str(row.get("firstName") or "")
    room_qty = as_int(row.get("roomQty") or row.get("qty") or 1, 1)
    if room_qty < 1:
        room_qty = 1
    stay = Stay(
        booking_id=booking_id,
        property_id=property_id,
        property_name="",
        room_id=as_id(row.get("roomId")),
        room_qty=room_qty,
        status=str(row.get("status") or "").strip().lower(),
        arrival=arrival,
        departure=departure,
        adults=as_int(row.get("numAdult") if row.get("numAdult") is not None else row.get("adults"), 0),
        children=as_int(row.get("numChild") if row.get("numChild") is not None else row.get("children"), 0),
        dogs=0,
        guest_label=guest_label(first, str(row.get("lastName") or "")),
        channel=channel_label(row),
        price=as_float(row.get("price")),
        currency=one_line(str(row.get("currency") or "EUR")) or "EUR",
        paid=None,
        created_at=parse_ts(row.get("bookingTime") or row.get("bookingDate") or row.get("createdTime")),
        modified_at=parse_ts(row.get("modifiedTime") or row.get("modified") or row.get("lastModified")),
        cancelled_at=parse_ts(row.get("cancelTime") or row.get("cancelledTime")),
        manual=False,
    )
    face = BookingFace(
        booking_id=booking_id,
        property_id=property_id,
        first_name=first_name_only(first),
        channel=stay.channel,
    )
    return stay, face


def face_from_row(row: dict[str, Any]) -> BookingFace | None:
    booking_id = as_id(row.get("id"))
    if booking_id is None:
        return None
    return BookingFace(
        booking_id=booking_id,
        property_id=as_id(row.get("propertyId")),
        first_name=first_name_only(str(row.get("firstName") or "")),
        channel=channel_label(row),
    )


def manual_stay(row: dict[str, Any], index: int) -> Stay:
    property_id = as_id(row.get("propertyId"))
    property_name = one_line(str(row.get("property") or ""))
    if property_id is None:
        property_id = NAME_TO_ID.get(property_name.casefold())
    if property_id is None:
        raise SnapshotError(f"manual booking {index} has no propertyId")
    arrival = parse_date(row.get("arrival"))
    departure = parse_date(row.get("departure"))
    if not arrival or not departure or departure <= arrival:
        raise SnapshotError(f"manual booking {index} has invalid dates")
    paid_value = row.get("paid")
    paid = paid_value if isinstance(paid_value, bool) else None
    return Stay(
        booking_id=None,
        property_id=property_id,
        property_name=property_name,
        room_id=as_id(row.get("roomId")),
        room_qty=1,
        status="confirmed",
        arrival=arrival,
        departure=departure,
        adults=as_int(row.get("adults"), 0),
        children=as_int(row.get("children"), 0),
        dogs=as_int(row.get("dogs"), 0),
        guest_label=label_from_guest_field(str(row.get("guest") or row.get("firstName") or "")),
        channel=channel_label({"channel": row.get("channel"), "referer": row.get("referer")}),
        price=as_float(row.get("price")),
        currency=one_line(str(row.get("currency") or "EUR")) or "EUR",
        paid=paid,
        created_at=None,
        modified_at=None,
        cancelled_at=None,
        manual=True,
    )


def load_manual(path: Path) -> list[Stay]:
    if not path.exists():
        raise SnapshotError(f"Manual bookings file is missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SnapshotError(f"Manual bookings file is invalid JSON: {exc}") from exc
    rows = payload.get("bookings") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise SnapshotError("bookings/manual.json must contain a bookings array")
    stays: list[Stay] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise SnapshotError(f"manual booking {index} is not an object")
        stays.append(manual_stay(row, index))
    return stays


def with_manual_properties(properties: list[Property], manual: list[Stay]) -> list[Property]:
    known = {item.property_id for item in properties}
    extra: list[Property] = []
    for stay in manual:
        if stay.property_id in known:
            continue
        known.add(stay.property_id)
        extra.append(
            Property(
                stay.property_id,
                stay.property_name or f"Объект {stay.property_id}",
                (),
            )
        )
    return sort_properties(list(properties) + extra)


def fetch_modified(
    client: GetClient,
    property_id: int,
    since: dt.datetime,
) -> list[dict[str, Any]]:
    attempts = (
        since.strftime("%Y-%m-%d %H:%M:%S"),
        since.strftime("%Y-%m-%dT%H:%M:%SZ"),
        since.date().isoformat(),
    )
    errors: list[str] = []
    for value in attempts:
        try:
            return paged(
                client,
                "/bookings",
                [("propertyId", str(property_id)), ("modifiedFrom", value)],
            )
        except SnapshotError as exc:
            errors.append(str(exc))
            if "HTTP 400" not in str(exc):
                raise
    raise SnapshotError("modifiedFrom rejected: " + " | ".join(errors))


def fetch_messages(
    client: GetClient,
    properties: list[Property],
    source: str,
) -> list[dict[str, Any]]:
    params = [("maxAge", "3"), ("source", source)]
    try:
        return paged(client, "/bookings/messages", params, messages=True)
    except SnapshotError as exc:
        if "HTTP 400" not in str(exc):
            raise
        rows: list[dict[str, Any]] = []
        for prop in properties:
            rows.extend(
                paged(
                    client,
                    "/bookings/messages",
                    [
                        ("propertyId", str(prop.property_id)),
                        ("maxAge", "3"),
                        ("source", source),
                    ],
                    messages=True,
                )
            )
        return rows


def fetch_by_ids(client: GetClient, booking_ids: list[int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    unique = sorted({int(item) for item in booking_ids if int(item)})
    for start in range(0, len(unique), 50):
        chunk = unique[start : start + 50]
        params = [("id", str(booking_id)) for booking_id in chunk]
        rows.extend(paged(client, "/bookings", params))
    return rows


def message_time(row: dict[str, Any]) -> dt.datetime | None:
    return parse_ts(row.get("time") or row.get("createdAt") or row.get("dateTime"))


def message_text(row: dict[str, Any]) -> str:
    return str(row.get("message") or row.get("text") or row.get("body") or "")


def select_unanswered(
    guest_rows: list[dict[str, Any]],
    host_rows: list[dict[str, Any]],
    faces: dict[int, BookingFace],
    now: dt.datetime,
) -> list[GuestMessage]:
    cutoff = now.astimezone(dt.timezone.utc) - dt.timedelta(hours=72)
    host_times: dict[int, list[dt.datetime]] = {}
    for row in host_rows:
        source = str(row.get("source") or "").strip().lower()
        if source not in HOST_SOURCES:
            continue
        booking_id = as_id(row.get("bookingId") or row.get("booking_id"))
        sent_at = message_time(row)
        if booking_id is None or sent_at is None:
            continue
        host_times.setdefault(booking_id, []).append(sent_at)

    selected: list[GuestMessage] = []
    seen: set[tuple[int, str]] = set()
    for row in guest_rows:
        source = str(row.get("source") or "").strip().lower()
        if source != "guest":
            continue
        booking_id = as_id(row.get("bookingId") or row.get("booking_id"))
        sent_at = message_time(row)
        if booking_id is None or sent_at is None or sent_at < cutoff:
            continue
        if any(host_at >= sent_at for host_at in host_times.get(booking_id, [])):
            continue
        key = (booking_id, sent_at.isoformat())
        if key in seen:
            continue
        seen.add(key)
        face = faces.get(booking_id)
        selected.append(
            GuestMessage(
                booking_id=booking_id,
                property_id=face.property_id if face else as_id(row.get("propertyId")),
                guest_label=face.first_name if face else "Гость",
                channel=face.channel if face else "—",
                sent_at=sent_at,
                excerpt=excerpt(message_text(row)) or "(пусто)",
            )
        )
    selected.sort(key=lambda item: item.sent_at, reverse=True)
    return selected


def scope_text(exc: MessagesScopeError) -> str:
    return (
        "Токен не имеет scope для чтения сообщений: "
        f"GET /bookings/messages вернул HTTP {exc.status}: {exc.detail}. "
        "Нужен scope bookings-personal. Сообщения не отправлялись."
    )


def is_active(stay: Stay) -> bool:
    return stay.status not in INACTIVE


def overlap_nights(
    arrival: dt.date,
    departure: dt.date,
    start: dt.date,
    end: dt.date,
) -> int:
    left = max(arrival, start)
    right = min(departure, end)
    if right <= left:
        return 0
    return (right - left).days


def revenue_in_window(stay: Stay, start: dt.date, end: dt.date) -> float:
    total = (stay.departure - stay.arrival).days
    if total <= 0:
        return 0.0
    inside = overlap_nights(stay.arrival, stay.departure, start, end)
    return stay.price * inside / total


def recent_kind(stay: Stay, cutoff: dt.datetime) -> str | None:
    if stay.manual:
        return None
    created = stay.created_at is not None and stay.created_at >= cutoff
    modified = stay.modified_at is not None and stay.modified_at >= cutoff
    cancelled = stay.cancelled_at is not None and stay.cancelled_at >= cutoff
    if stay.status in CANCELLED and (cancelled or modified or created):
        return "cancel"
    if stay.status in INACTIVE:
        return None
    if created:
        return "new"
    if modified:
        return "modified"
    return None


def people(stay: Stay) -> str:
    parts = [f"{stay.adults} взр."]
    if stay.children:
        parts.append(f"{stay.children} дет.")
    if stay.dogs:
        parts.append(f"{stay.dogs} соб.")
    return " + ".join(parts)


def price_text(stay: Stay) -> str:
    text = f"{stay.price:.2f} {stay.currency}"
    if stay.paid is True:
        text += ", оплачено"
    elif stay.paid is False:
        text += ", не оплачено"
    return text


def room_name(properties: list[Property], stay: Stay) -> str:
    if stay.room_id is None:
        return "не указана"
    for prop in properties:
        if prop.property_id != stay.property_id:
            continue
        for room in prop.rooms:
            if room.room_id == stay.room_id:
                return room.name
    return f"комната {stay.room_id}"


def property_name(properties: list[Property], property_id: int | None, fallback: str = "") -> str:
    if property_id is None:
        return fallback or "—"
    for prop in properties:
        if prop.property_id == property_id:
            return prop.name
    return fallback or f"Объект {property_id}"


def stay_line(properties: list[Property], stay: Stay, *tags: str) -> str:
    bits = [tag for tag in tags if tag]
    if stay.manual:
        bits.append("не в Beds24")
    suffix = (" · " + " · ".join(bits)) if bits else ""
    nights = (stay.departure - stay.arrival).days
    return (
        f"- {stay.guest_label} · {room_name(properties, stay)} · "
        f"{stay.arrival.isoformat()}—{stay.departure.isoformat()} · {ru_nights(nights)} · "
        f"{people(stay)} · {stay.channel} · {price_text(stay)}{suffix}"
    )


def lines_or_empty(lines: list[str]) -> list[str]:
    return lines or ["нет"]


def percent(nights: int, capacity: int) -> str:
    if capacity <= 0:
        return "0%"
    return f"{round(100 * nights / capacity)}%"


def occupancy_lines(
    prop: Property,
    stays: list[Stay],
    start: dt.date,
    end: dt.date,
) -> list[str]:
    buckets: dict[int | None, dict[str, Any]] = {}
    for room in prop.rooms:
        buckets[room.room_id] = {
            "name": room.name,
            "units": room.units,
            "nights": 0,
            "manual_nights": 0,
        }
    for stay in stays:
        if stay.property_id != prop.property_id or not is_active(stay):
            continue
        nights = overlap_nights(stay.arrival, stay.departure, start, end) * stay.room_qty
        if nights <= 0:
            continue
        bucket = buckets.get(stay.room_id)
        if bucket is None:
            bucket = {"name": "не указана", "units": 1, "nights": 0, "manual_nights": 0}
            buckets[stay.room_id] = bucket
        bucket["nights"] += nights
        if stay.manual:
            bucket["manual_nights"] += nights
    ordered = [buckets[room.room_id] for room in prop.rooms if room.room_id in buckets]
    ordered.extend(
        bucket
        for room_id, bucket in buckets.items()
        if room_id not in {room.room_id for room in prop.rooms} and bucket["nights"]
    )
    rendered: list[str] = []
    total_nights = 0
    total_capacity = 0
    for bucket in ordered:
        capacity = WINDOW_NIGHTS * int(bucket["units"])
        total_nights += int(bucket["nights"])
        total_capacity += capacity
        marker = ""
        if bucket["manual_nights"] and bucket["manual_nights"] == bucket["nights"]:
            marker = " · не в Beds24"
        elif bucket["manual_nights"]:
            marker = " · включая брони не в Beds24"
        units = int(bucket["units"])
        rendered.append(
            f"- {bucket['name']} ({units} {plural(units, 'номер', 'номера', 'номеров')}): "
            f"{bucket['nights']}/{capacity} ({percent(int(bucket['nights']), capacity)}){marker}"
        )
    if not rendered:
        rendered.append("нет")
    rendered.append(
        f"- Итого: {total_nights}/{total_capacity} ({percent(total_nights, total_capacity)})"
    )
    return rendered


def money(amount: float) -> str:
    return f"{amount:.2f} EUR"


def render_report(
    *,
    now: dt.datetime,
    properties: list[Property],
    stays: list[Stay],
    messages: list[GuestMessage],
    messages_note: str | None,
    header_notes: list[str],
    api_warning: str | None = None,
) -> str:
    local = now.astimezone(MADRID)
    today = local.date()
    week_end = today + dt.timedelta(days=WEEK_DAYS - 1)
    window_end = today + dt.timedelta(days=WINDOW_NIGHTS)
    last_night = window_end - dt.timedelta(days=1)
    cutoff = now.astimezone(dt.timezone.utc) - dt.timedelta(hours=24)
    message_cutoff = local - dt.timedelta(hours=72)
    lines = [
        "# Снимок бронирований",
        "",
        f"Сформирован: {local.strftime('%Y-%m-%d %H:%M')} Europe/Madrid",
        f"24 часа: с {cutoff.astimezone(MADRID).strftime('%Y-%m-%d %H:%M')} Europe/Madrid",
        f"72 часа (сообщения): с {message_cutoff.strftime('%Y-%m-%d %H:%M')} Europe/Madrid",
        f"7 дней: {today.isoformat()} — {week_end.isoformat()}",
        f"30 ночей: {today.isoformat()} — {last_night.isoformat()}",
        "Режим: только чтение, запросы GET к Beds24 API v2. Сообщения не отправляются.",
        "Имена гостей из Beds24: имя и инициал фамилии. Телефоны, почта и полные фамилии не печатаются.",
    ]
    if api_warning:
        lines.append(api_warning)
    if header_notes:
        lines.append("Примечания:")
        lines.extend(f"- {note}" for note in header_notes)
    lines.extend(["", "## Прямые брони вне Beds24", "", "Источник: `bookings/manual.json`."])
    manual_future = [
        stay for stay in stays if stay.manual and stay.departure >= today and is_active(stay)
    ]
    if not manual_future:
        lines.append("нет")
    else:
        for prop in properties:
            group = [stay for stay in manual_future if stay.property_id == prop.property_id]
            if not group:
                continue
            lines.append("")
            lines.append(f"### {prop.name}")
            for stay in sorted(group, key=lambda item: (item.arrival, item.guest_label)):
                lines.append(stay_line(properties, stay))
    active = [stay for stay in stays if is_active(stay) and stay.departure >= today]
    for prop in properties:
        prop_stays = [stay for stay in stays if stay.property_id == prop.property_id]
        lines.extend(["", f"## {prop.name} ({prop.property_id})", ""])
        lines.append("### Новые и изменённые за 24 часа")
        changed = []
        for stay in prop_stays:
            kind = recent_kind(stay, cutoff)
            if kind in {"new", "modified"}:
                changed.append((0 if kind == "new" else 1, stay.arrival, stay.guest_label, stay, kind))
        changed.sort()
        lines.extend(
            lines_or_empty(
                [
                    stay_line(properties, stay, "новая" if kind == "new" else "изменена")
                    for _, _, _, stay, kind in changed
                ]
            )
        )
        lines.extend(["", "### Отмены за 24 часа"])
        cancelled = [
            stay
            for stay in prop_stays
            if recent_kind(stay, cutoff) == "cancel"
        ]
        cancelled.sort(key=lambda item: (item.arrival, item.guest_label))
        lines.extend(
            lines_or_empty([stay_line(properties, stay, "отмена") for stay in cancelled])
        )
        lines.extend(["", "### Заезды на 7 дней"])
        arrivals = [
            stay
            for stay in prop_stays
            if is_active(stay) and today <= stay.arrival <= week_end
        ]
        arrivals.sort(key=lambda item: (item.arrival, item.guest_label))
        lines.extend(lines_or_empty([stay_line(properties, stay) for stay in arrivals]))
        lines.extend(["", "### Выезды на 7 дней"])
        departures = [
            stay
            for stay in prop_stays
            if is_active(stay) and today <= stay.departure <= week_end
        ]
        departures.sort(key=lambda item: (item.departure, item.guest_label))
        lines.extend(lines_or_empty([stay_line(properties, stay) for stay in departures]))
        lines.extend(
            [
                "",
                "### Загрузка на 30 дней",
                "",
                "Загрузка = занятые номеро-ночи / (30 × число номеров). Для одного номера это ночи / 30.",
            ]
        )
        lines.extend(occupancy_lines(prop, prop_stays, today, window_end))
        prop_active = [stay for stay in active if stay.property_id == prop.property_id]
        prop_revenue = sum(revenue_in_window(stay, today, window_end) for stay in prop_active)
        manual_revenue = sum(
            revenue_in_window(stay, today, window_end)
            for stay in prop_active
            if stay.manual
        )
        lines.extend(["", "### Итоги"])
        lines.append(f"- Активных будущих бронирований: {len(prop_active)}")
        revenue_line = f"- Выручка на книгах за 30 дней: {money(prop_revenue)}"
        if manual_revenue:
            revenue_line += f" (включая {money(manual_revenue)} не в Beds24)"
        lines.append(revenue_line)

    lines.extend(["", "## Сообщения гостей", ""])
    if messages_note:
        lines.append(messages_note)
    elif not messages:
        lines.append("Нет неотвеченных сообщений гостей за последние 72 часа.")
    else:
        for item in messages:
            when = item.sent_at.astimezone(MADRID).strftime("%Y-%m-%d %H:%M")
            prop = property_name(properties, item.property_id)
            lines.append(
                f"- {item.booking_id} · {item.guest_label} · {item.channel} · {when} Europe/Madrid · {prop} · {item.excerpt}"
            )

    account_revenue = sum(revenue_in_window(stay, today, window_end) for stay in active)
    account_manual = sum(
        revenue_in_window(stay, today, window_end) for stay in active if stay.manual
    )
    lines.extend(["", "## Всего по аккаунту", ""])
    lines.append(f"- Активных будущих бронирований: {len(active)}")
    account_line = f"- Выручка на книгах за 30 дней: {money(account_revenue)}"
    if account_manual:
        account_line += f" (включая {money(account_manual)} не в Beds24)"
    lines.append(account_line)
    footer = run_footer()
    if footer:
        lines.extend(["", footer])
    return "\n".join(lines).rstrip() + "\n"


def run_footer() -> str | None:
    server = (os.environ.get("GITHUB_SERVER_URL") or "").rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY") or ""
    run_id = os.environ.get("GITHUB_RUN_ID") or ""
    if server and repo and run_id:
        return f"Запуск: {server}/{repo}/actions/runs/{run_id}"
    return None


def pause_line(error: str) -> str:
    return f"⚠️ Beds24 аккаунт на паузе / API: {error}"


def blocked_report(now: dt.datetime, manual_path: Path, error: str) -> str:
    """Manual stays still render when Beds24 refuses the read."""
    manual = load_manual(manual_path)
    properties = with_manual_properties(list(FALLBACK_PROPERTIES), manual)
    return render_report(
        now=now,
        properties=properties,
        stays=manual,
        messages=[],
        messages_note="Сообщения не прочитаны: Beds24 API недоступен. Сообщения не отправлялись.",
        header_notes=[],
        api_warning=pause_line(error),
    )


def build_from_client(client: GetClient, now: dt.datetime, manual_path: Path) -> str:
    manual = load_manual(manual_path)
    header_notes: list[str] = []
    api_errors: list[str] = []
    try:
        properties = fetch_properties(client)
    except SnapshotError as exc:
        properties = list(FALLBACK_PROPERTIES)
        api_errors.append(str(exc))
    today = now.astimezone(MADRID).date()
    since = now.astimezone(dt.timezone.utc) - dt.timedelta(hours=24)
    by_id: dict[int, tuple[Stay, BookingFace]] = {}
    recent_errors: list[str] = []
    for prop in properties:
        try:
            departure_rows = paged(
                client,
                "/bookings",
                [("propertyId", str(prop.property_id)), ("departureFrom", today.isoformat())],
            )
        except SnapshotError as exc:
            api_errors.append(str(exc))
            continue
        try:
            modified_rows = fetch_modified(client, prop.property_id, since)
        except SnapshotError as exc:
            modified_rows = []
            recent_errors.append(f"{prop.name}: {exc}")
        for row in departure_rows + modified_rows:
            projected = project_booking(row)
            if projected is None:
                continue
            stay, face = projected
            by_id[stay.booking_id or 0] = (stay, face)
    if recent_errors:
        header_notes.append(
            "Фильтр modifiedFrom не принят, окно 24 часов посчитано по уже загруженным броням "
            "с выездом сегодня или позже. " + " | ".join(recent_errors)
        )
    faces = {booking_id: face for booking_id, (_, face) in by_id.items()}
    stays = [stay for stay, _ in by_id.values()] + manual
    properties = with_manual_properties(properties, manual)
    messages_note: str | None
    try:
        guest_rows = fetch_messages(client, properties, "guest")
        host_rows = fetch_messages(client, properties, "host")
        missing = sorted(
            {
                booking_id
                for row in guest_rows
                if (booking_id := as_id(row.get("bookingId") or row.get("booking_id")))
                and booking_id not in faces
            }
        )
        if missing:
            for row in fetch_by_ids(client, missing):
                face = face_from_row(row)
                if face is not None:
                    faces[face.booking_id] = face
        messages = select_unanswered(guest_rows, host_rows, faces, now)
        messages_note = None
    except MessagesScopeError as exc:
        messages = []
        messages_note = scope_text(exc)
        print("messages=scope_missing", file=sys.stderr)
    except SnapshotError as exc:
        messages = []
        messages_note = f"Не удалось прочитать сообщения: {exc} Сообщения не отправлялись."
        print(messages_note, file=sys.stderr)
    print(
        f"properties={len(properties)} bookings={len(by_id)} manual={len(manual)} "
        f"unanswered_messages={len(messages)}",
        file=sys.stderr,
    )
    return render_report(
        now=now,
        properties=properties,
        stays=stays,
        messages=messages,
        messages_note=messages_note,
        header_notes=header_notes,
        api_warning=pause_line(" || ".join(api_errors)) if api_errors else None,
    )


def build_live(now: dt.datetime, manual_path: Path, opener: Any = urllib.request.urlopen) -> str:
    credential, source = credential_from_env()
    if not credential:
        print("beds24_api credential missing BEDS24_REFRESH_CREDENTIAL", file=sys.stderr)
        return blocked_report(now, manual_path, "BEDS24_REFRESH_CREDENTIAL is missing")
    try:
        token, base = exchange_token(opener, credential)
    except SnapshotError as exc:
        print(str(exc), file=sys.stderr)
        return blocked_report(now, manual_path, str(exc))
    client = GetClient(base, token, opener, secrets=(credential, token))
    print(f"auth_source={source} api_base={base}", file=sys.stderr)
    try:
        return build_from_client(client, now, manual_path)
    except SnapshotError as exc:
        print(str(exc), file=sys.stderr)
        return blocked_report(now, manual_path, str(exc))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Beds24 bookings snapshot")
    parser.add_argument("--output", default="")
    parser.add_argument("--manual", default=str(DEFAULT_MANUAL))
    parser.add_argument("--now", default="", help="ISO timestamp override for tests")
    args = parser.parse_args(argv)
    if args.now:
        now = parse_ts(args.now)
        if now is None:
            print("Invalid --now value", file=sys.stderr)
            return 2
    else:
        now = dt.datetime.now(dt.timezone.utc)
    try:
        report = build_live(now, Path(args.manual))
    except SnapshotError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.output:
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(report, encoding="utf-8")
    sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
