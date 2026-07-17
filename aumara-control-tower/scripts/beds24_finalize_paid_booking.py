import argparse
import datetime as dt
import json
import os
import pathlib
import unicodedata
import urllib.error
import urllib.request

API_BASE = "https://api.beds24.com/v2"
ROOT = pathlib.Path(__file__).resolve().parents[1]
REQUEST_FILE = ROOT / "beds24-requests" / "AUMARA-MEDINA-20260718-660.json"
EVIDENCE_DIR = ROOT / "evidence"
BOOKING_EVIDENCE = EVIDENCE_DIR / "beds24-AUMARA-MEDINA-20260718-660.json"
EXECUTION_EVIDENCE = EVIDENCE_DIR / "beds24-finalize-status.json"
AUTH_PROBE_EVIDENCE = EVIDENCE_DIR / "beds24-auth-probe.json"


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def ensure_dirs():
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


def load_request_id():
    if not REQUEST_FILE.exists():
        return None
    try:
        payload = json.loads(REQUEST_FILE.read_text())
    except Exception:
        return None
    return payload.get("request_id")


def normalize_credential(value):
    """Strip accidental secret wrappers without ever logging the credential."""
    normalized = (value or "").strip()
    while (
        len(normalized) >= 2
        and normalized[0] == normalized[-1]
        and normalized[0] in {'"', "'"}
    ):
        normalized = normalized[1:-1].strip()
    return "".join(
        ch
        for ch in normalized
        if not ch.isspace() and unicodedata.category(ch) not in {"Cc", "Cf"}
    )


def resolve_refresh_token(env=None):
    env = env or os.environ
    refresh_token = normalize_credential(env.get("B24_TOKEN_CREDENTIAL", ""))
    if not refresh_token:
        raise SystemExit("Missing GitHub Actions secret B24_TOKEN_CREDENTIAL")
    return refresh_token


def request_json(method, path, headers=None):
    request = urllib.request.Request(
        f"{API_BASE}{path}",
        headers={"accept": "application/json", **(headers or {})},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = response.read().decode("utf-8", "replace")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw) if raw else {}
        except Exception:
            parsed = {"raw": raw[:500]}
        return exc.code, parsed


def safe(obj):
    if isinstance(obj, dict):
        return {
            key: (
                "[REDACTED]"
                if key.lower() in {"token", "refreshtoken", "code", "credential"}
                else safe(value)
            )
            for key, value in obj.items()
        }
    if isinstance(obj, list):
        return [safe(item) for item in obj[:20]]
    if isinstance(obj, str):
        return obj[:500]
    return obj


def exchange_refresh_token(refresh_token):
    status, payload = request_json(
        "GET",
        "/authentication/token",
        headers={"refreshToken": refresh_token},
    )
    access_token = payload.get("token") if isinstance(payload, dict) else None
    if not access_token or not (200 <= status < 300):
        raise RuntimeError(
            f"Beds24 refresh-token exchange failed HTTP {status}: {safe(payload)}"
        )
    return access_token


def fetch_properties(access_token):
    status, payload = request_json(
        "GET",
        "/properties",
        headers={"token": access_token},
    )
    if not (200 <= status < 300):
        raise RuntimeError(f"Beds24 GET /properties failed HTTP {status}: {safe(payload)}")
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, list):
        return data
    if isinstance(payload, list):
        return payload
    return []


def run_read_only_verification(env=None):
    refresh_token = resolve_refresh_token(env=env)
    access_token = exchange_refresh_token(refresh_token)
    properties = fetch_properties(access_token)
    return {
        "verified_at_utc": now(),
        "status": "READ_ONLY_AUTH_VERIFIED",
        "api_base": API_BASE,
        "request_id": load_request_id(),
        "credential_source": "B24_TOKEN_CREDENTIAL",
        "credential_type": "refresh_token",
        "checked_endpoint": "/properties",
        "property_count": len(properties),
        "property_ids": [item.get("id") for item in properties[:20] if isinstance(item, dict)],
        "live_booking_mutations": False,
        "plaintext_secret_committed": False,
    }


def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--auth-probe-only",
        action="store_true",
        help="Only validate refresh-token auth and a read-only /properties request.",
    )
    args = parser.parse_args(argv)

    ensure_dirs()
    summary = run_read_only_verification()

    if args.auth_probe_only:
        write_json(AUTH_PROBE_EVIDENCE, summary)
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "checked_endpoint": summary["checked_endpoint"],
                    "property_count": summary["property_count"],
                    "live_booking_mutations": False,
                }
            )
        )
        return 0

    booking_evidence = {
        **summary,
        "outcome": "read_only_verification_only",
        "booking_verification": False,
    }
    execution_evidence = {
        "verified_at_utc": summary["verified_at_utc"],
        "status": summary["status"],
        "checked_endpoint": summary["checked_endpoint"],
        "property_count": summary["property_count"],
        "live_booking_mutations": False,
    }
    write_json(BOOKING_EVIDENCE, booking_evidence)
    write_json(EXECUTION_EVIDENCE, execution_evidence)
    print(
        json.dumps(
            {
                "status": summary["status"],
                "outcome": "read_only_verification_only",
                "checked_endpoint": summary["checked_endpoint"],
                "property_count": summary["property_count"],
                "live_booking_mutations": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
