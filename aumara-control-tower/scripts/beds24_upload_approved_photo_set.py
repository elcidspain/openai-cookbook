#!/usr/bin/env python3
"""AUMARA Booking photo replace — all 34 as common on both rooms (V1 map-merge safe)."""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import subprocess
import time
import urllib.error
import urllib.request

PROPERTY_ID = "324882"
ROOM_CHALET = "674465"
ROOM_SUPERIOR = "674466"
REPO = "elcidspain/openai-cookbook"
PUBLIC_DIR = "aumara-control-tower/public/booking-20260908"
EVIDENCE = pathlib.Path("aumara-control-tower/evidence/beds24-booking-photo-replace-20260908.json")
SLOTS = list(range(35, 49)) + list(range(69, 89))
CONTAMINATED = [i for i in range(1, 101) if i not in SLOTS]


def mask(v: str) -> None:
    if v:
        print(f"::add-mask::{v}", flush=True)


def post_v1(path: str, payload: dict):
    req = urllib.request.Request(
        "https://api.beds24.com/json/" + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "AUMARA-Booking-Photo-Replace/2026-09-08",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read()
            status = int(r.status)
    except urllib.error.HTTPError as e:
        raw = e.read()
        status = int(e.code)
    try:
        body = json.loads(raw.decode("utf-8", "replace")) if raw else {}
    except Exception:
        body = {"non_json_bytes": len(raw or b"")}
    if not 200 <= status < 300:
        raise SystemExit(f"{path} HTTP {status}: {str(body)[:1500]}")
    return body


def norm_maps(value):
    return sorted(
        (str(x.get("propId", "")), str(x.get("roomId", "")), str(x.get("position", "")))
        for x in (value or [])
    )


def main() -> int:
    api = (os.environ.get("BEDS24_API_KEY") or "").strip()
    prop = (os.environ.get("BEDS24_PROP_KEY") or "").strip()
    refresh = (os.environ.get("BEDS24_REFRESH_CREDENTIAL") or os.environ.get("BEDS24_VAULT_KEK") or "").strip()
    for s in (api, prop, refresh):
        mask(s)
    if not api or not prop:
        raise SystemExit("BEDS24_API_KEY / BEDS24_PROP_KEY missing")

    asset_sha = (
        subprocess.check_output(["git", "rev-list", "-1", "HEAD", "--", PUBLIC_DIR], text=True).strip()
        or subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    )
    files = sorted(pathlib.Path(PUBLIC_DIR).glob("*.jpg"))
    if len(files) != 34 or len(SLOTS) != 34:
        raise SystemExit(f"Expected 34 files/slots, got {len(files)}/{len(SLOTS)}")

    # Prefer visual order: common exteriors first, then chalet, then superior (filename sort already does this)
    manifest = []
    for f in files:
        category = f.name.split("-")[1]
        url = f"https://raw.githubusercontent.com/{REPO}/{asset_sha}/{PUBLIC_DIR}/{f.name}"
        ok = False
        for _ in range(8):
            try:
                rq = urllib.request.Request(url, headers={"User-Agent": "AUMARA-photo-readback/1.0"})
                with urllib.request.urlopen(rq, timeout=30) as resp:
                    if int(resp.status) == 200 and resp.read(64).startswith(b"\xff\xd8\xff"):
                        ok = True
                        break
            except Exception:
                pass
            time.sleep(1)
        if not ok:
            raise SystemExit(f"Not fetchable {f.name}")
        manifest.append({"category": category, "filename": f.name, "url": url})

    auth = {"apiKey": api, "propKey": prop}
    blank = {str(i): {"url": ""} for i in CONTAMINATED}
    post_v1(
        "setPropertyContent",
        {"authentication": auth, "setPropertyContent": [{"action": "modify", "images": {"external": blank}}]},
    )
    time.sleep(3)

    desired = {}
    for pos, (slot, item) in enumerate(zip(SLOTS, manifest), start=1):
        maps = [
            {"propId": PROPERTY_ID, "roomId": ROOM_CHALET, "position": str(pos)},
            {"propId": PROPERTY_ID, "roomId": ROOM_SUPERIOR, "position": str(pos)},
        ]
        key = str(slot)
        desired[key] = {"url": item["url"], "map": maps}
        item["slot"] = key
        item["position"] = pos

    post_v1(
        "setPropertyContent",
        {"authentication": auth, "setPropertyContent": [{"action": "modify", "images": {"external": desired}}]},
    )
    time.sleep(4)
    readback = post_v1(
        "getPropertyContent",
        {
            "authentication": auth,
            "bookingData": False,
            "images": True,
            "roomIds": True,
            "texts": False,
            "includeAirbnb": True,
            "includeVrbo": False,
        },
    )
    data = (readback.get("getPropertyContent") or [{}])[0]
    ext = ((data.get("images") or {}).get("external") or {})

    mismatches = []
    for i in CONTAMINATED:
        got_url = (ext.get(str(i)) or {}).get("url")
        if got_url not in ("", None):
            mismatches.append({"slot": str(i), "field": "old_url_not_blank", "got": got_url})
    for key, want in desired.items():
        got = ext.get(key) or {}
        if got.get("url") != want["url"]:
            mismatches.append({"slot": key, "field": "url", "wanted": want["url"], "got": got.get("url")})
        # For common dual maps, require at least both room mappings (ignore extra stale entries)
        got_norm = norm_maps(got.get("map"))
        want_norm = norm_maps(want["map"])
        if not set(want_norm).issubset(set(got_norm)):
            mismatches.append({"slot": key, "field": "map", "wanted": want["map"], "got": got.get("map")})

    evidence = {
        "schema": "aumara.beds24-booking-photo-replace.v1",
        "mode": "all_common_both_rooms",
        "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "property_id": int(PROPERTY_ID),
        "asset_commit": asset_sha,
        "slots": SLOTS,
        "manifest": manifest,
        "wanted_room_photo_counts": {ROOM_CHALET: 34, ROOM_SUPERIOR: 34},
        "mismatches": mismatches,
        "status": "SUCCESS" if not mismatches else "FAILED_READBACK",
        "secret_exposed": False,
        "note": "All 34 photos mapped to both rooms (V1 cannot reliably clear room-only maps). Booking channel may need content sync.",
    }
    text = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True)
    for s in (api, prop, refresh):
        if s:
            text = text.replace(s, "[REDACTED]")
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(text + "\n", encoding="utf-8")
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=False)
    subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=False)
    subprocess.run(["git", "add", str(EVIDENCE)], check=False)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], check=False).returncode != 0:
        subprocess.run(["git", "commit", "-m", f"Record Booking photo replace {evidence['status']} [skip ci]"], check=False)
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=False)
        subprocess.run(["git", "push", "origin", "HEAD:main"], check=False)

    print(json.dumps({"status": evidence["status"], "mismatches": len(mismatches), "mode": "all_common_both_rooms"}), flush=True)
    if mismatches:
        raise SystemExit(f"Readback mismatches: {len(mismatches)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
