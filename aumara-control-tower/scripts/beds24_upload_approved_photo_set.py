#!/usr/bin/env python3
"""AUMARA Booking.com photo replace for Beds24 324882 (2026-09-08 pack).

Uses V1 setPropertyContent + Production BEDS24_API_KEY/BEDS24_PROP_KEY.
Photos already hosted at aumara-control-tower/public/booking-20260908/.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request

PROPERTY_ID = 324882
ROOM_CHALET = "674465"
ROOM_SUPERIOR = "674466"
REPO = "elcidspain/openai-cookbook"
PUBLIC_DIR = "aumara-control-tower/public/booking-20260908"
EVIDENCE = pathlib.Path("aumara-control-tower/evidence/beds24-booking-photo-replace-20260908.json")


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


def main() -> int:
    api = (os.environ.get("BEDS24_API_KEY") or "").strip()
    prop = (os.environ.get("BEDS24_PROP_KEY") or "").strip()
    refresh = (os.environ.get("BEDS24_REFRESH_CREDENTIAL") or os.environ.get("BEDS24_VAULT_KEK") or "").strip()
    for s in (api, prop, refresh):
        mask(s)
    if not api or not prop:
        raise SystemExit("BEDS24_API_KEY / BEDS24_PROP_KEY missing in environment")

    # Prefer commit that hosts the pack; fall back to HEAD
    asset_sha = (
        subprocess.check_output(["git", "rev-list", "-1", "HEAD", "--", PUBLIC_DIR], text=True).strip()
        or subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    )
    # List files from working tree (checkout)
    public = pathlib.Path(PUBLIC_DIR)
    files = sorted(public.glob("*.jpg"))
    if len(files) != 34:
        # try fetch from raw using known commit tip on main for that folder
        raise SystemExit(f"Expected 34 JPGs in {PUBLIC_DIR}, got {len(files)}")

    manifest = []
    for f in files:
        parts = f.name.split("-")
        category = parts[1] if len(parts) >= 3 else ""
        if category not in ("common", "chalet", "superior"):
            raise SystemExit(f"Bad filename category: {f.name}")
        url = f"https://raw.githubusercontent.com/{REPO}/{asset_sha}/{PUBLIC_DIR}/{f.name}"
        if len(url) > 250:
            raise SystemExit(f"URL too long: {url}")
        # prove fetchable
        last = None
        for _ in range(10):
            try:
                rq = urllib.request.Request(url, headers={"User-Agent": "AUMARA-photo-readback/1.0"})
                with urllib.request.urlopen(rq, timeout=30) as resp:
                    head = resp.read(64)
                    status = int(resp.status)
                    ctype = (resp.headers.get("Content-Type") or "").lower()
                if status == 200 and head.startswith(b"\xff\xd8\xff"):
                    break
                last = f"status={status} ctype={ctype}"
            except Exception as e:
                last = str(e)
            time.sleep(2)
        else:
            raise SystemExit(f"Not fetchable: {f.name}: {last}")
        manifest.append({"category": category, "filename": f.name, "url": url})

    external = {str(i): {"url": "", "map": []} for i in range(1, 101)}
    chalet_pos = 0
    superior_pos = 0
    for slot, item in enumerate(manifest, start=1):
        maps = []
        if item["category"] == "common":
            chalet_pos += 1
            superior_pos += 1
            maps = [
                {"propId": str(PROPERTY_ID), "roomId": ROOM_CHALET, "position": str(chalet_pos)},
                {"propId": str(PROPERTY_ID), "roomId": ROOM_SUPERIOR, "position": str(superior_pos)},
            ]
        elif item["category"] == "chalet":
            chalet_pos += 1
            maps = [{"propId": str(PROPERTY_ID), "roomId": ROOM_CHALET, "position": str(chalet_pos)}]
        else:
            superior_pos += 1
            maps = [{"propId": str(PROPERTY_ID), "roomId": ROOM_SUPERIOR, "position": str(superior_pos)}]
        external[str(slot)] = {"url": item["url"], "map": maps}

    wanted = {ROOM_CHALET: chalet_pos, ROOM_SUPERIOR: superior_pos}
    if wanted != {ROOM_CHALET: 21, ROOM_SUPERIOR: 25}:
        raise SystemExit(f"Unexpected counts: {wanted}")

    auth = {"apiKey": api, "propKey": prop}
    write_response = post_v1(
        "setPropertyContent",
        {"authentication": auth, "setPropertyContent": [{"action": "modify", "images": {"external": external}}]},
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
    got_external = ((data.get("images") or {}).get("external") or {})
    mismatches = []
    for slot in range(1, 35):
        key = str(slot)
        want = external[key]
        got = got_external.get(key) or {}
        if got.get("url") != want["url"]:
            mismatches.append({"slot": key, "field": "url", "wanted": want["url"], "got": got.get("url")})
        def norm_maps(value):
            return sorted(
                (str(x.get("propId", "")), str(x.get("roomId", "")), str(x.get("position", "")))
                for x in (value or [])
            )
        if norm_maps(got.get("map")) != norm_maps(want["map"]):
            mismatches.append({"slot": key, "field": "map", "wanted": want["map"], "got": got.get("map")})

    evidence = {
        "schema": "aumara.beds24-booking-photo-replace.v1",
        "checked_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "property_id": PROPERTY_ID,
        "asset_commit": asset_sha,
        "manifest": manifest,
        "wanted_room_photo_counts": wanted,
        "write_ok": True,
        "mismatches": mismatches,
        "status": "SUCCESS" if not mismatches else "FAILED_READBACK",
        "secret_exposed": False,
        "note": "Booking.com may need channel content sync after Beds24 picture replace",
    }
    text = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True)
    for s in (api, prop, refresh):
        if s:
            text = text.replace(s, "[REDACTED]")
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(text + "\n", encoding="utf-8")
    try:
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=False)
        subprocess.run(
            ["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"],
            check=False,
        )
        subprocess.run(["git", "add", str(EVIDENCE)], check=False)
        if subprocess.run(["git", "diff", "--cached", "--quiet"], check=False).returncode != 0:
            subprocess.run(
                ["git", "commit", "-m", f"Record Booking photo replace {evidence['status']} [skip ci]"],
                check=False,
            )
            subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=False)
            subprocess.run(["git", "push", "origin", "HEAD:main"], check=False)
    except Exception as e:
        print(f"evidence commit skipped: {e}", flush=True)

    print(json.dumps({"status": evidence["status"], "counts": wanted, "mismatches": len(mismatches)}, flush=True))
    if mismatches:
        raise SystemExit(f"Readback mismatches: {len(mismatches)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
