from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
import zipfile
from urllib.parse import parse_qsl, urljoin, urlsplit, urlunsplit

import gdown
from PIL import Image, ImageOps
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from playwright.sync_api import TimeoutError as PwTimeout
from playwright.sync_api import sync_playwright

PROPERTY_ID = 324882
EXPECTED = {"common": 14, "chalet": 3, "superior": 1}
ZIP_MANIFEST = [
    ("common", "AUMARA_COMMON_14.zip", "1nKYEWf7wt-dKyMSqn7cGBZY1Fsqfnh5j"),
    ("chalet", "AUMARA_CHALET_3.zip", "1q2EgyxM0jaGdoIrZMHRFIRmU4Z53CDgg"),
    ("superior", "AUMARA_SUPERIOR_1.zip", "1Det-7VAFrXW47F2zO8sh87De3unKRz49"),
]
EXPECTED_TOTAL = sum(EXPECTED.values())

ROOT = pathlib.Path.cwd()
HS = ROOT / "aumara-control-tower/evidence/beds24-ui-handshake"
EVIDENCE = ROOT / "aumara-control-tower/evidence/beds24-photo-set-20260823"
SOURCE = ROOT / "source-photo-set-20260823"
UPLOAD = ROOT / "upload-photo-set-20260823"
for path in (EVIDENCE, SOURCE, UPLOAD):
    path.mkdir(parents=True, exist_ok=True)

KEK = (os.environ.get("BEDS24_VAULT_KEK") or "").strip()
USER = (
    (os.environ.get("BEDS24_USERNAME") or "").strip()
    or (os.environ.get("BEDS24_USER") or "").strip()
    or (os.environ.get("BEDS24_LOGIN") or "").strip()
    or "EL CID / AUMARA"
)
if not KEK:
    raise SystemExit("Production handshake KEK missing")
print(f"::add-mask::{KEK}", flush=True)
print(f"::add-mask::{USER}", flush=True)


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def fkey(value: str) -> bytes:
    material = "AUMARA_BEDS24_UI_HANDSHAKE_V1\0" + value
    return base64.urlsafe_b64encode(hashlib.sha256(material.encode()).digest())


def safe_url(value: str) -> str:
    parts = urlsplit(value)
    keys = sorted({key for key, _ in parse_qsl(parts.query, keep_blank_values=True)})
    query = "&".join(f"{key}=[REDACTED]" for key in keys)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))[:500]


def git_push(paths: list[pathlib.Path], message: str) -> None:
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
    subprocess.run(
        ["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"],
        check=True,
    )
    subprocess.run(["git", "add", *map(str, paths)], check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet"], check=False).returncode != 0:
        subprocess.run(["git", "commit", "-m", message], check=True)
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=True)
        subprocess.run(["git", "push", "origin", "HEAD:main"], check=True)


def write_state(status: str, **extra: object) -> None:
    state = {
        "status": status,
        "updated_at_utc": now(),
        "property_id": PROPERTY_ID,
        "expected_total": EXPECTED_TOTAL,
        "expected_by_category": EXPECTED,
        "secret_exposed": False,
        **extra,
    }
    target = EVIDENCE / "state.json"
    target.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    git_push([target], f"Beds24 approved photo set state {status} [skip ci]")


result: dict[str, object] = {
    "property_id": PROPERTY_ID,
    "expected_total": EXPECTED_TOTAL,
    "expected_by_category": EXPECTED,
    "status": "STARTING",
    "started_at_utc": now(),
    "secret_exposed": False,
}


def fail(stage: str, message: str, page=None) -> None:
    result.update(status="FAILED", stage=stage, diagnostic=message, finished_at_utc=now())
    target = EVIDENCE / "result.json"
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_state("FAILED", stage=stage, diagnostic=message[:500])
    raise SystemExit(1)


write_state("STARTING")


def download_and_prepare() -> list[dict[str, object]]:
    for old in SOURCE.iterdir():
        if old.is_dir():
            shutil.rmtree(old)
        else:
            old.unlink()
    for old in UPLOAD.iterdir():
        old.unlink()

    prepared: list[dict[str, object]] = []
    seq = 0
    for category, zip_name, file_id in ZIP_MANIFEST:
        archive = SOURCE / zip_name
        if not gdown.download(id=file_id, output=str(archive), quiet=False):
            raise RuntimeError(f"Drive download failed: {zip_name}")
        with zipfile.ZipFile(archive) as zf:
            unsafe = [name for name in zf.namelist() if name.startswith("/") or ".." in pathlib.PurePosixPath(name).parts]
            if unsafe:
                raise RuntimeError(f"Unsafe ZIP members in {zip_name}")
            members = [name for name in zf.namelist() if not name.endswith("/")]
            if len(members) != EXPECTED[category]:
                raise RuntimeError(
                    f"{zip_name}: expected {EXPECTED[category]} files, got {len(members)}"
                )
            category_dir = SOURCE / category
            category_dir.mkdir(parents=True, exist_ok=True)
            zf.extractall(category_dir)

        files = sorted(
            p
            for p in category_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        )
        if len(files) != EXPECTED[category]:
            raise RuntimeError(
                f"{category}: expected {EXPECTED[category]} images, got {len(files)}"
            )
        for src in files:
            seq += 1
            raw = src.read_bytes()
            if len(raw) < 50_000:
                raise RuntimeError(f"Image too small: {src.name}")
            with Image.open(src) as opened:
                image = ImageOps.exif_transpose(opened).convert("RGB")
                original_size = image.size
            if max(image.size) > 2560:
                image.thumbnail((2560, 2560), Image.Resampling.LANCZOS)
            safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", src.stem)[:80]
            target = UPLOAD / f"{seq:02d}_{category}_{safe_stem}.png"
            while True:
                image.save(target, "PNG", optimize=True, compress_level=9)
                if target.stat().st_size <= 4_800_000:
                    break
                if min(image.size) <= 900:
                    raise RuntimeError(f"PNG too large after resize: {src.name}")
                image = image.resize(
                    (int(image.width * 0.9), int(image.height * 0.9)),
                    Image.Resampling.LANCZOS,
                )
            prepared.append(
                {
                    "category": category,
                    "source": src.name,
                    "upload": target.name,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "source_size": list(original_size),
                    "upload_size": list(image.size),
                    "crop": False,
                }
            )
    if len(prepared) != EXPECTED_TOTAL:
        raise RuntimeError(f"Expected {EXPECTED_TOTAL} prepared photos, got {len(prepared)}")
    (EVIDENCE / "manifest.json").write_text(
        json.dumps(prepared, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return prepared


try:
    records = download_and_prepare()
except Exception as exc:
    fail("prepare", str(exc))

private_pem = Fernet(fkey(KEK)).decrypt((HS / "private.enc").read_text().strip().encode())
private = serialization.load_pem_private_key(private_pem, password=None)
pwd_ct = base64.b64decode((HS / "password.enc").read_text().strip())
password = (os.environ.get("BEDS24_PASSWORD") or "").strip()
if not password:
    password = private.decrypt(
        pwd_ct,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    ).decode().strip()
if not password:
    raise SystemExit("Beds24 password empty")
print(f"::add-mask::{password}", flush=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1440, "height": 1100})
    page = context.new_page()
    page.set_default_timeout(30_000)
    writes: list[dict[str, object]] = []

    def on_response(response) -> None:
        if response.request.method in ("POST", "PUT", "PATCH"):
            writes.append(
                {
                    "method": response.request.method,
                    "status": response.status,
                    "url": safe_url(response.url),
                }
            )

    page.on("response", on_response)
    try:
        page.goto("https://beds24.com/control2.php", wait_until="domcontentloaded", timeout=60_000)
        user = page.locator(
            "input[name='username'], input[name='user'], input[autocomplete='username'], input[type='email']"
        ).first
        if not user.count():
            user = page.locator("input[type='text']").first
        secret = page.locator(
            "input[name='password'], input[autocomplete='current-password'], input[type='password']"
        ).first
        if not user.count() or not secret.count():
            fail("login_form", "Login fields not found", page)
        user.fill(USER)
        secret.fill(password)
        submit = page.locator(
            "button[type='submit'], input[type='submit'], #loginButton, button:has-text('Log in'), button:has-text('Login'), button:has-text('Sign in')"
        ).first
        if not submit.count():
            fail("login_form", "Login button not found", page)
        submit.click()
        page.wait_for_timeout(5_000)

        body = (page.locator("body").inner_text() or "").lower()
        otp = page.locator(
            "input[name*='code' i], input[name*='two' i], input[autocomplete='one-time-code'], input[inputmode='numeric']"
        ).first
        challenged = bool(otp.count()) or any(
            marker in body
            for marker in (
                "two factor",
                "2 factor",
                "login code",
                "verification code",
                "email code",
                "check your email",
                "login link",
            )
        )
        still_password = bool(page.locator("input[type='password']").count())
        if challenged:
            subprocess.run(["git", "fetch", "origin", "main"], check=True)
            baseline = subprocess.run(
                [
                    "git",
                    "show",
                    "origin/main:aumara-control-tower/evidence/beds24-ui-handshake/second-factor.enc",
                ],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            write_state("AWAITING_SECOND_FACTOR", challenge_detected=True, login_url=safe_url(page.url))
            deadline = time.time() + 600
            second = ""
            while time.time() < deadline:
                subprocess.run(
                    ["git", "fetch", "origin", "main"],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                show = subprocess.run(
                    [
                        "git",
                        "show",
                        "origin/main:aumara-control-tower/evidence/beds24-ui-handshake/second-factor.enc",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                current = show.stdout.strip() if show.returncode == 0 else ""
                if current and current != baseline:
                    try:
                        ct = base64.b64decode(current)
                        second = private.decrypt(
                            ct,
                            padding.OAEP(
                                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                                algorithm=hashes.SHA256(),
                                label=None,
                            ),
                        ).decode().strip()
                        if second:
                            break
                    except Exception:
                        pass
                page.wait_for_timeout(5_000)
            if not second:
                fail("second_factor", "Timed out waiting for a fresh encrypted second factor", page)
            print(f"::add-mask::{second}", flush=True)
            if second.startswith("http://") or second.startswith("https://"):
                page.goto(second, wait_until="domcontentloaded", timeout=60_000)
                page.wait_for_timeout(4_000)
            else:
                otp = page.locator(
                    "input[name*='code' i], input[name*='two' i], input[autocomplete='one-time-code'], input[inputmode='numeric']"
                ).first
                if not otp.count():
                    fail("second_factor", "Second-factor field not found", page)
                otp.fill(second)
                verify = page.locator(
                    "button[type='submit'], input[type='submit'], button:has-text('Verify'), button:has-text('Login'), button:has-text('Continue')"
                ).first
                if not verify.count():
                    fail("second_factor", "Second-factor submit not found", page)
                verify.click()
                page.wait_for_timeout(5_000)
        elif still_password:
            fail("login", "Beds24 rejected username/password before second factor", page)

        page.goto(
            f"https://beds24.com/control3.php?pagetype=propcontent&propid={PROPERTY_ID}",
            wait_until="domcontentloaded",
            timeout=60_000,
        )
        page.wait_for_timeout(2_000)
        if page.locator("input[type='password']").count():
            fail("session", "Control-panel session was not established", page)
        result["login"] = True

        links = page.locator("a").evaluate_all(
            "els => els.map(a => ({text:(a.innerText||'').trim(), href:a.href||''}))"
        )
        picture = next(
            (
                item["href"]
                for item in links
                if any(key in item["text"].lower() for key in ("picture", "photo", "image"))
            ),
            None,
        )
        candidates = ([urljoin(page.url, picture)] if picture else []) + [
            f"https://beds24.com/control2.php?pagetype=pictures&propid={PROPERTY_ID}",
            f"https://beds24.com/control2.php?pagetype=picture&propid={PROPERTY_ID}",
            f"https://beds24.com/control3.php?pagetype=pictures&propid={PROPERTY_ID}",
            f"https://beds24.com/control3.php?pagetype=propcontent&propid={PROPERTY_ID}",
        ]
        for candidate in dict.fromkeys(candidates):
            page.goto(candidate, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(1_500)
            if page.locator("input[type='file']").count():
                break
        else:
            fail("pictures_page", "Pictures upload input not found", page)

        selector = "img[src*='picture' i], img[src*='image' i], .picture img, .pictures img"
        before = page.locator(selector).count()
        before_sources = set(
            page.locator(selector).evaluate_all("els => els.map(e => e.currentSrc || e.src || '').filter(Boolean)")
        )
        writes.clear()
        photos = sorted(UPLOAD.glob("*.png"))
        if len(photos) != EXPECTED_TOTAL:
            fail("prepare", f"Expected {EXPECTED_TOTAL} upload files, got {len(photos)}", page)

        upload_button = "button:has-text('Upload'), input[value*='Upload' i], button:has-text('Save'), input[value*='Save' i]"
        file_input = page.locator("input[type='file']").first
        multiple = file_input.get_attribute("multiple") is not None
        if multiple:
            for start in range(0, len(photos), 10):
                batch = photos[start : start + 10]
                page.locator("input[type='file']").first.set_input_files([str(x) for x in batch])
                button = page.locator(upload_button).first
                if button.count() and button.is_visible():
                    button.click()
                page.wait_for_timeout(max(10_000, len(batch) * 1_500))
        else:
            for photo in photos:
                page.locator("input[type='file']").first.set_input_files(str(photo))
                button = page.locator(upload_button).first
                if button.count() and button.is_visible():
                    button.click()
                page.wait_for_timeout(5_000)

        try:
            page.reload(wait_until="domcontentloaded", timeout=60_000)
        except PwTimeout:
            pass
        page.wait_for_timeout(3_000)
        after = page.locator(selector).count()
        after_sources = set(
            page.locator(selector).evaluate_all("els => els.map(e => e.currentSrc || e.src || '').filter(Boolean)")
        )
        new_sources = sorted(after_sources - before_sources)
        text = (page.locator("body").inner_text() or "").lower()
        hits = [photo.name for photo in photos if photo.name.lower() in text]
        success_writes = [item for item in writes if 200 <= int(item["status"]) < 400]
        failed_writes = [item for item in writes if int(item["status"]) >= 400]
        result.update(
            images_before=before,
            images_after=after,
            new_image_sources_count=len(new_sources),
            successful_writes=success_writes,
            failed_writes=failed_writes,
            filename_hits=hits,
            multiple_upload=multiple,
        )
        verified = (
            after >= before + EXPECTED_TOTAL
            or len(new_sources) >= EXPECTED_TOTAL
            or len(hits) == EXPECTED_TOTAL
        )
        if not verified:
            fail(
                "verify",
                f"Upload not proven: before={before} after={after} new_sources={len(new_sources)} filename_hits={len(hits)}",
                page,
            )
        result.update(status="SUCCESS", uploaded=EXPECTED_TOTAL, finished_at_utc=now())
        result_path = EVIDENCE / "result.json"
        result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        write_state(
            "SUCCESS",
            uploaded=EXPECTED_TOTAL,
            images_before=before,
            images_after=after,
            new_image_sources_count=len(new_sources),
        )
        git_push(
            [EVIDENCE / "manifest.json", result_path],
            "Record verified Beds24 approved photo set upload [skip ci]",
        )
    except PwTimeout as exc:
        fail("timeout", str(exc), page)
    finally:
        try:
            browser.close()
        except Exception:
            pass
