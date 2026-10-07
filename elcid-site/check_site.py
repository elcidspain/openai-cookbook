#!/usr/bin/env python3
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
import json
import re
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent


class Audit(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.links = []
        self.images = []
        self.scripts = []
        self.styles = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            if a["id"] in self.ids:
                raise ValueError(f"duplicate id: {a['id']}")
            self.ids.add(a["id"])
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag == "img" and a.get("src"):
            self.images.append(a["src"])
        if tag == "script" and a.get("src"):
            self.scripts.append(a["src"])
        if tag == "link" and a.get("rel") == "stylesheet" and a.get("href"):
            self.styles.append(a["href"])


def fail(msg):
    print("FAIL:", msg)
    sys.exit(1)


def contains_external_host(text, host):
    for url in re.findall(r"https?://[^\"')\s]+", text):
        if urlparse(url).hostname == host:
            return True
    return False


html = (ROOT / "index.html").read_text(encoding="utf-8")
css = (ROOT / "styles.css").read_text(encoding="utf-8")
js = (ROOT / "site.js").read_text(encoding="utf-8")
p = Audit()
p.feed(html)

if "AUMARA_Explore" in html or "08_AUMARA_Domes" in html:
    fail("AUMARA primary image assets leaked into EL CID page")
if 'name="robots" content="index,follow' not in html:
    fail("production EL CID page must be indexable")
if 'rel="canonical" href="https://www.elcidspain.com/"' not in html:
    fail("production canonical must be https://www.elcidspain.com/")
if contains_external_host(html, "cf.bstatic.com") or contains_external_host(css, "cf.bstatic.com"):
    fail("Booking CDN image hotlink remains")
if "official-logo" not in html or "official-logo" not in css:
    fail("official EL CID logo missing")
if "Wabi-Sabi" in html or "Wabi-Sabi" in js or "Wabi‑Sabi" in html or "Wabi‑Sabi" in js:
    fail("retired restaurant working name remains")
if "reservas@elcidspain.com" in html or "reservas@elcidspain.com" in js:
    fail("broken domain mailbox remains in guest-facing page")
if "elcidspain@gmail.com" not in html:
    fail("operational email fallback missing")

for required in ("stay", "restaurant", "place", "events", "contact"):
    if required not in p.ids:
        fail(f"missing section #{required}")
for required in ("bookingDrawer", "bookingBackdrop", "bookingNudge", "whatsappBooking"):
    if required not in p.ids:
        fail(f"missing conversion element #{required}")

for path in p.links + p.scripts + p.styles:
    if path.startswith(("http://", "https://", "mailto:", "tel:", "#", "/")):
        continue
    if not (ROOT / path).exists():
        fail(f"missing local target {path}")

for href in p.links:
    if href.startswith("#") and href != "#" and href[1:] not in p.ids:
        fail(f"broken anchor {href}")

if not any("booking.com/hotel/es/el-cid-country-club" in x for x in p.links):
    fail("missing EL CID Booking CTA")
if any("beds24" in x.lower() for x in p.links):
    fail("unverified EL CID Beds24 CTA present")
if "https://wa.me/34622914323?text=" not in html:
    fail("WhatsApp CTA missing")
if "34622914323" not in html or "tel:" in html:
    fail("verified WhatsApp number is not explicit (and tel: links are not allowed)")
if "data-open-booking" not in html or "booking-drawer" not in css:
    fail("booking drawer trigger or styling missing")

studio_assets = (
    "1sNBC9u1rsO0CiOksJ93RqkzWeZF7tLBF",
    "1G3pNSIQbQR8oLtgpyC9qXkXxAHG7V-AH",
    "1fZjB7E5wNfaurAu0AWlfaHjuEx6BuKVn",
    "1MjonXzcIpvqPn4jNnyPjYUBiPFj8it_o",
)
for asset_id in studio_assets:
    if asset_id not in html:
        fail(f"verified studio asset missing: {asset_id}")

# Multilingual pages: generated from i18n/template.html + i18n/<lang>.json.
# Language comes only from the URL path; never from navigator.language or storage.
import subprocess
build = subprocess.run([sys.executable, str(ROOT / "build_i18n.py"), "--check"], capture_output=True, text=True)
if build.returncode != 0:
    fail("i18n build stale or broken: " + (build.stdout + build.stderr).strip())
LANGS = ["es", "en", "de", "fr", "nl", "ru", "it"]
if re.search(r"navigator\.languages?\b|localStorage\.(getItem|setItem)|elcid-language'\)\|\|", js):
    fail("site.js must not choose language from the browser or stored preferences")
if "data-i18n" in html or "languageToggle" in js:
    fail("runtime language switching remains")
sitemap_xml = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
for lang in LANGS:
    page_file = ROOT / "index.html" if lang == "es" else ROOT / lang / "index.html"
    if not page_file.exists():
        fail(f"missing language page: {lang}")
    page = page_file.read_text(encoding="utf-8")
    url = "https://www.elcidspain.com/" if lang == "es" else f"https://www.elcidspain.com/{lang}"
    if f'<html lang="{lang}"' not in page:
        fail(f"{lang}: html lang mismatch")
    if f'<link rel="canonical" href="{url}">' not in page:
        fail(f"{lang}: self-canonical missing")
    hreflangs = re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)">', page)
    if sorted(h for h, _ in hreflangs) != sorted(LANGS + ["x-default"]):
        fail(f"{lang}: hreflang set incomplete: {hreflangs}")
    if dict(hreflangs).get("x-default") != "https://www.elcidspain.com/":
        fail(f"{lang}: x-default must point to the Spanish root")
    if f'"inLanguage":"{lang}"' not in page:
        fail(f"{lang}: JSON-LD inLanguage missing")
    if 'id="languageMenu"' not in page or page.count('hreflang="') < 2 * len(LANGS) + 1:
        fail(f"{lang}: language switcher missing")
    if "https://wa.me/34622914323?text=" not in page or "tel:" in page:
        fail(f"{lang}: WhatsApp link missing or tel: link present")
    if "booking.com/hotel/es/el-cid-country-club" not in page or "official-logo" not in page:
        fail(f"{lang}: Booking CTA or logo missing")
    if "CV H01453 A" not in page:
        fail(f"{lang}: published registration line changed")
    if f"<loc>{url}</loc>" not in sitemap_xml:
        fail(f"sitemap missing {url}")
    lp = Audit()
    lp.feed(page)
    for path in lp.links + lp.scripts + lp.styles:
        if path.startswith(("http://", "https://", "mailto:", "#", "/")):
            continue
        if not (page_file.parent / path).resolve().exists():
            fail(f"{lang}: missing local target {path}")
    for href in lp.links:
        if href.startswith("#") and href != "#" and href[1:] not in lp.ids:
            fail(f"{lang}: broken anchor {href}")
    for required in ("stay", "restaurant", "place", "events", "contact", "bookingDrawer", "whatsappBooking"):
        if required not in lp.ids:
            fail(f"{lang}: missing #{required}")
if sitemap_xml.count("<url>") != len(LANGS) + 3 or 'xmlns:xhtml="http://www.w3.org/1999/xhtml"' not in sitemap_xml:
    fail("sitemap must list 7 language pages with xhtml alternates plus 3 policy pages")

for required_file in ("robots.txt", "sitemap.xml", "llms.txt", "index.md", "legal.html", "privacy.html", "cookies.html"):
    if not (ROOT / required_file).exists():
        fail(f"missing production public file: {required_file}")
skill_index = ROOT / ".well-known" / "agent-skills" / "index.json"
skill_md = ROOT / ".well-known" / "agent-skills" / "plan-elcid-stay" / "SKILL.md"
if not skill_index.exists() or not skill_md.exists():
    fail("Agent Skills discovery files missing")
if "elcid_guest_guide" not in js or "elcid_booking_options" not in js or "registerTool" not in js:
    fail("EL CID WebMCP read-only tools missing")

# Product-routing guardrail: repository fallback and deployed root are EL CID;
# AUMARA is redirected to its separate canonical production site.
root_html = (REPO / "index.html").read_text(encoding="utf-8")
if "./elcid-site/" not in root_html:
    fail("repository root fallback does not point to EL CID")
if "aumara-site" in root_html.lower():
    fail("repository root fallback still points to AUMARA")

vercel = json.loads((REPO / "vercel.json").read_text(encoding="utf-8"))
routes = vercel.get("routes", [])
root_route = next((item for item in routes if item.get("src") == "^/$" and item.get("dest") == "/elcid-site/index.html"), None)
if not root_route:
    fail("production HTML root / does not resolve to EL CID")
markdown_route = next((item for item in routes if item.get("src") == "^/$" and item.get("dest") == "/elcid-site/index.md"), None)
if not markdown_route:
    fail("Markdown content-negotiation route missing")
has = markdown_route.get("has", [])
if not any(item.get("type") == "header" and item.get("key", "").lower() == "accept" and "text/markdown" in item.get("value", "") for item in has):
    fail("Markdown route does not negotiate Accept: text/markdown")
if not markdown_route.get("headers", {}).get("Content-Type", "").startswith("text/markdown"):
    fail("Markdown route does not declare text/markdown")
if "redirects" in vercel:
    fail("top-level redirects cannot be combined with routes; keep the /aumara 308 in routes")
if not any(item.get("src") == "^/aumara(/.*)?$" and item.get("status") == 308 and item.get("headers", {}).get("Location") == "https://www.aumara.me/" for item in routes):
    fail("AUMARA canonical redirect missing")
staff_route = next((item for item in routes if item.get("src") == "^/staff/?$"), None)
if not staff_route or "noindex" not in staff_route.get("headers", {}).get("X-Robots-Tag", ""):
    fail("/staff must send X-Robots-Tag noindex")
if not any(item.get("src") == "^/.*$" and item.get("status") == 404 for item in routes):
    fail("production routing does not fail closed for unrelated repository files")
if "trailingSlash" in vercel:
    fail("trailingSlash must stay unset so stale WordPress paths can return 410 before slash redirects")

gone_routes = [item for item in routes if item.get("status") == 410 and item.get("dest") == "/elcid-site/gone.txt"]
if len(gone_routes) != 3:
    fail("expected three stale WordPress 410 routes")
slash_route = next((item for item in routes if item.get("src") == "^/(.*)/$" and item.get("status") == 308), None)
if not slash_route or slash_route.get("headers", {}).get("Location") != "/$1":
    fail("non-stale trailing-slash 308 missing")
gone_indexes = [routes.index(item) for item in gone_routes]
slash_index = routes.index(slash_route)
catch_all_index = next(i for i, item in enumerate(routes) if item.get("src") == "^/.*$" and item.get("status") == 404)
if max(gone_indexes) >= slash_index or slash_index >= catch_all_index:
    fail("410 routes must run before the trailing-slash 308 and the 404 catch-all")
if not (ROOT / "gone.txt").is_file():
    fail("410 response body missing")

def first_route(path):
    for item in routes:
        if item.get("continue"):
            continue  # header-only pass-through routes (e.g. staff host noindex)
        if re.search(item.get("src", ""), path):
            return item
    return None

gone_paths = [
    "/about-us",
    "/about-us/",
    "/terms-conditions",
    "/terms-conditions/",
    "/shop",
    "/shop/",
    "/shop/cart",
    "/shop/cart/",
    "/en-gb/rooms",
    "/en-gb/rooms/",
    "/ru-ru",
    "/ru-ru/",
    "/ru-ru/rooms",
    "/ru-ru/privacy-policy",
    "/experiences",
    "/experiences/",
    "/experiences/wine-tasting",
    "/wine-club",
    "/wine-club/",
    "/terroirs",
    "/terroirs/",
    "/demo-design-system",
    "/demo-design-system/",
    "/demo-design-system/typography",
    "/nuestra-historia",
    "/nuestra-historia/",
    "/restaurant-menu",
    "/restaurant-menu/",
    "/es-es/booking",
    "/es-es/booking/",
    "/product/seven-case-2",
    "/product/seven-case-2/",
    "/product-category/uncategorized",
    "/product-category/uncategorized/",
    "/hello-world",
    "/hello-world/",
    "/2025/07/31/hello-world",
    "/2025/07/31/hello-world/",
    "/2021/05/02/post001",
    "/2021/05/02/post002",
    "/2021/05/02/post003/",
    "/2021/05/03/post008",
]
for path in gone_paths:
    match = first_route(path)
    if not match or match.get("status") != 410:
        fail(f"stale path is not 410 in one hop: {path}")

kept_paths = {
    "/": 200,
    "/legal.html": 200,
    "/privacy.html": 200,
    "/cookies.html": 200,
    "/styles.css": 200,
    "/robots.txt": 200,
    "/sitemap.xml": 200,
    "/llms.txt": 200,
    "/auth.md": 200,
    "/mcp": 200,
    "/a2a": 200,
    "/legal/": 308,
    "/privacy.html/": 308,
    "/aumara/": 308,
    "/en": 200,
    "/de": 200,
    "/fr": 200,
    "/nl": 200,
    "/ru": 200,
    "/it": 200,
    "/en/": 308,
    "/ru/": 308,
    "/en/index.html": 404,
    "/pt": 404,
    "/es": 404,
    "/privacy": 404,
    "/privacy-policy": 404,
    "/contact": 404,
    "/contact/": 308,
    "/heart-and-blood-vessels/alcohol-and-blood-pressure-medicine-m04cbq": 404,
    "/products": 404,
    "/shopping": 404,
    "/ru-rules": 404,
    "/en-gb": 404,
    "/es-es": 404,
}
for path, expected in kept_paths.items():
    match = first_route(path)
    if expected == 410:
        status = 410 if match and match.get("status") == 410 else None
    elif expected == 308:
        status = match.get("status") if match else None
        location = None
        if match:
            found = re.search(match.get("src", ""), path)
            location_template = match.get("headers", {}).get("Location", "")
            location = location_template
            if found:
                for group_index, group in enumerate(found.groups(), start=1):
                    location = location.replace(f"${group_index}", group or "")
        if location != "/" + path.strip("/"):
            fail(f"trailing slash redirect changed: {path} -> {location}")
    elif expected == 404:
        status = match.get("status") if match else None
    else:
        status = 200 if match and match.get("status") != 410 and match.get("src") != "^/(.*)/$" and match.get("src") != "^/.*$" else (match.get("status") if match else None)
    if status != expected:
        fail(f"unrelated path changed: {path} expected {expected} got {status} via {match.get('src') if match else None}")

aumara = first_route("/aumara")
if not aumara or aumara.get("status") != 308 or aumara.get("headers", {}).get("Location") != "https://www.aumara.me/":
    fail("AUMARA path redirect changed")
aumara_nested = first_route("/aumara/explore")
if not aumara_nested or aumara_nested.get("headers", {}).get("Location") != "https://www.aumara.me/":
    fail("AUMARA nested redirect changed")
header_route = next((item for item in routes if item.get("src") == "^/$" and item.get("headers") and item.get("continue")), None)
if not header_route or "Content-Signal" not in header_route.get("headers", {}) or "Link" not in header_route.get("headers", {}):
    fail("production discovery headers missing")

hosts = sorted({urlparse(x).netloc for x in p.links if x.startswith("http")})
print(f"ids={len(p.ids)} links={len(p.links)} images={len(p.images)} scripts={len(p.scripts)} styles={len(p.styles)}")
print("external_hosts=" + ",".join(hosts))
print("conversion=booking drawer + Booking.com + verified WhatsApp")
print("studio=verified kitchen + living area + bedroom + bathroom")
print("discovery=robots + sitemap + llms + Markdown negotiation + Agent Skills + WebMCP + Link headers")
print("policies=legal + privacy + cookies")
print("languages=/ (es) + /en /de /fr /nl /ru /it, path-only, hreflang x-default=/")
print("routes=/->EL CID HTML/Markdown, /aumara/->www.aumara.me, stale WordPress paths->410")
print("EL CID production static site checks: PASS")
