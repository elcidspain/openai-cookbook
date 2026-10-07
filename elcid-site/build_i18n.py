#!/usr/bin/env python3
"""Build the EL CID language pages from one template plus per-language JSON.

Language is chosen only by URL path: / (es), /en, /de, /fr, /nl, /ru, /it.
There is no browser-language or localStorage detection anywhere.

  python3 elcid-site/build_i18n.py          # write index.html, <lang>/index.html, sitemap.xml
  python3 elcid-site/build_i18n.py --check  # fail if generated files are stale
"""
from pathlib import Path
from urllib.parse import quote
import json
import re
import sys

ROOT = Path(__file__).resolve().parent
I18N = ROOT / "i18n"
ORIGIN = "https://www.elcidspain.com"
DEFAULT = "es"
LANGS = ["es", "en", "de", "fr", "nl", "ru", "it"]
LEGAL_PAGES = ["legal.html", "privacy.html", "cookies.html"]


def page_url(lang):
    return f"{ORIGIN}/" if lang == DEFAULT else f"{ORIGIN}/{lang}"


def page_path(lang):
    return "/" if lang == DEFAULT else f"/{lang}"


def out_file(lang):
    return ROOT / "index.html" if lang == DEFAULT else ROOT / lang / "index.html"


def esc(value):
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def load():
    data = {}
    for lang in LANGS:
        data[lang] = json.loads((I18N / f"{lang}.json").read_text(encoding="utf-8"))
        if data[lang]["_lang"] != lang:
            raise SystemExit(f"{lang}.json declares _lang={data[lang]['_lang']}")
    base_keys = set(data[DEFAULT])
    for lang in LANGS:
        missing = base_keys ^ set(data[lang])
        if missing:
            raise SystemExit(f"{lang}.json key mismatch: {sorted(missing)}")
    return data


def hreflang_links():
    lines = [f'  <link rel="alternate" hreflang="{lang}" href="{page_url(lang)}">' for lang in LANGS]
    lines.append(f'  <link rel="alternate" hreflang="x-default" href="{page_url(DEFAULT)}">')
    return "\n".join(lines)


def switcher(lang, data):
    current = data[lang]
    items = []
    for other in LANGS:
        attrs = f'href="{page_path(other)}" hreflang="{other}" lang="{other}"'
        if other == lang:
            attrs += ' aria-current="page"'
        items.append(f'        <a {attrs}><b>{other.upper()}</b>{esc(data[other]["_name"])}</a>')
    return (
        '    <details id="languageMenu" class="lang">\n'
        f'      <summary class="utility lang-btn" aria-label="{esc(current["languageLabel"])}: {esc(current["_name"])}">{lang.upper()}</summary>\n'
        f'      <nav class="lang-menu" aria-label="{esc(current["languageLabel"])}">\n'
        + "\n".join(items)
        + "\n      </nav>\n    </details>"
    )


def json_ld(lang, t):
    hotel = {
        "@type": "Hotel",
        "@id": f"{ORIGIN}/#hotel",
        "name": "EL CID Country Club",
        "url": f"{ORIGIN}/",
        "description": t["metaDescription"],
        "address": {"@type": "PostalAddress", "streetAddress": "Carrer Rincón del Silencio, 3", "postalCode": "03759", "addressLocality": "Benidoleig", "addressRegion": "Alicante", "addressCountry": "ES"},
        "telephone": "+34 622 914 323",
        "email": "elcidspain@gmail.com",
        "contactPoint": {"@type": "ContactPoint", "telephone": "+34 622 914 323", "contactType": "customer service", "url": "https://wa.me/34622914323", "description": "WhatsApp and text only, no calls"},
    }
    website = {"@type": "WebSite", "@id": f"{ORIGIN}/#website", "url": f"{ORIGIN}/", "name": "EL CID Country Club", "inLanguage": LANGS}
    webpage = {
        "@type": "WebPage",
        "@id": f"{page_url(lang)}#webpage",
        "url": page_url(lang),
        "name": t["title"],
        "description": t["metaDescription"],
        "inLanguage": lang,
        "isPartOf": {"@id": f"{ORIGIN}/#website"},
        "about": {"@id": f"{ORIGIN}/#hotel"},
    }
    doc = {"@context": "https://schema.org", "@graph": [hotel, website, webpage]}
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def render(lang, data, template):
    t = data[lang]
    special = {
        "htmlLang": lang,
        "canonical": page_url(lang),
        "hreflangLinks": hreflang_links(),
        "ogLocale": t["_ogLocale"],
        "ogLocaleAlternates": "\n".join(f'  <meta property="og:locale:alternate" content="{data[o]["_ogLocale"]}">' for o in LANGS if o != lang),
        "base": "" if lang == DEFAULT else "../",
        "jsonLd": json_ld(lang, t),
        "languageSwitcher": switcher(lang, data),
        "legalHreflang": "" if lang == DEFAULT else ' hreflang="es"',
        "legalLanguageNote": "" if not t["legalLanguageNote"] else f'<br><span lang="{lang}">{esc(t["legalLanguageNote"])}</span>',
    }

    def sub(match):
        key = match.group(1)
        if key.startswith("u:"):
            return quote(t[key[2:]], safe="")
        if key in special:
            return special[key]
        if key not in t:
            raise SystemExit(f"template key missing in {lang}.json: {key}")
        return esc(t[key])

    html = re.sub(r"\{\{([A-Za-z:]+)\}\}", sub, template)
    if "{{" in html:
        raise SystemExit(f"unresolved placeholder in {lang}")
    return html


def sitemap():
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for lang in LANGS:
        lines.append("  <url>")
        lines.append(f"    <loc>{page_url(lang)}</loc>")
        for other in LANGS:
            lines.append(f'    <xhtml:link rel="alternate" hreflang="{other}" href="{page_url(other)}"/>')
        lines.append(f'    <xhtml:link rel="alternate" hreflang="x-default" href="{page_url(DEFAULT)}"/>')
        lines.append("  </url>")
    for page in LEGAL_PAGES:
        lines.append("  <url>")
        lines.append(f"    <loc>{ORIGIN}/{page}</loc>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def outputs():
    data = load()
    template = (I18N / "template.html").read_text(encoding="utf-8")
    files = {out_file(lang): render(lang, data, template) for lang in LANGS}
    files[ROOT / "sitemap.xml"] = sitemap()
    return files


def main():
    check = "--check" in sys.argv[1:]
    stale = []
    for path, content in outputs().items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != content:
            if check:
                stale.append(str(path.relative_to(ROOT)))
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                print("wrote", path.relative_to(ROOT))
    if stale:
        print("FAIL: generated language files are stale; run python3 elcid-site/build_i18n.py:", ", ".join(stale))
        sys.exit(1)
    if check:
        print("i18n build up to date:", ", ".join(LANGS))


if __name__ == "__main__":
    main()
