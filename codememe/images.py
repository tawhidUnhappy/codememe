"""Real pictures from the internet for full-screen scenes.

screenshot  a real page, rendered by headless Chrome (python.org, docs, a store page, a Stack Overflow question ...)
commons     an openly licensed picture from Wikimedia Commons (screenshots of software, logos, photos)
openverse   an openly licensed picture from Openverse (Flickr and others), commercial use allowed

Commons / Openverse pictures need attribution (CC BY ...): `credit` strings are collected and added to the video's
description. Everything is cached in global/images/ (gitignored)."""

from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

from .paths import ROOT, config, read_json, write_json

CACHE = ROOT / "global" / "images"
UA = {"User-Agent": "codememe/0.1 (educational video project)"}
OK_LICENSE = re.compile(r"^(cc0|pdm|public domain|cc[ -]by(?!-nc)|cc[ -]by-sa|mit|bsd|gpl|apache|attribution)", re.I)


def _key(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def chrome() -> str:
    cfg = config().get("chrome")
    found = cfg or next((shutil.which(n) for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser") if shutil.which(n)), None)
    if not found:
        raise RuntimeError("no Chrome/Chromium found for screenshots (set \"chrome\" in config.json)")
    return found


def screenshot(url: str, css_width: int = 720, height: int = 3200) -> Path:
    """A 1080-px-wide PNG of `url` from the top of the page: laid out `css_width` CSS pixels wide and scaled up, so
    text is big enough to read on a phone."""
    path = CACHE / f"shot2-{_key(url, str(css_width), str(height))}.png"
    if path.exists() and path.stat().st_size > 5000:
        return path
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part.png")
    subprocess.run([chrome(), "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", f"--window-size={css_width},{round(height * css_width / 1080)}",
                    f"--force-device-scale-factor={1080 / css_width:.4f}", "--virtual-time-budget=9000", f"--screenshot={tmp}", url], capture_output=True, timeout=90, check=False)
    if not tmp.exists() or tmp.stat().st_size < 5000:
        raise RuntimeError(f"screenshot of {url} failed")
    tmp.replace(path)
    return path


def _get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
        return r.read()


def _strip(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


def commons(query: str) -> tuple[Path, str]:
    """(picture, credit line) for the best openly licensed bitmap on Wikimedia Commons."""
    meta = CACHE / f"commons-{_key(query)}.json"
    if meta.exists():
        info = read_json(meta)
        if Path(info["path"]).exists():
            return Path(info["path"]), info["credit"]
    q = urllib.parse.urlencode({"action": "query", "generator": "search", "gsrsearch": f"filetype:bitmap {query}", "gsrnamespace": 6, "gsrlimit": 10,
                                "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1080, "format": "json"})
    pages = json.loads(_get("https://commons.wikimedia.org/w/api.php?" + q)).get("query", {}).get("pages", {})
    for page in sorted(pages.values(), key=lambda p: p.get("index", 0)):
        i = page["imageinfo"][0]
        m = i["extmetadata"]
        lic = m.get("LicenseShortName", {}).get("value", "")
        if not OK_LICENSE.match(lic) or i["width"] < 500 or not i.get("thumburl"):
            continue
        path = CACHE / f"commons-{_key(query)}{Path(urllib.parse.urlparse(i['thumburl']).path).suffix or '.png'}"
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_get(i["thumburl"]))
        author = _strip(m.get("Artist", {}).get("value", "")) or "unknown author"
        credit = f"{page['title'].removeprefix('File:')} - {author[:60]}, {lic}, {i['descriptionurl']}"
        write_json(meta, {"path": str(path), "credit": credit})
        return path, credit
    raise RuntimeError(f"no openly licensed picture on Commons for {query!r}")


def openverse(query: str) -> tuple[Path, str]:
    meta = CACHE / f"openverse-{_key(query)}.json"
    if meta.exists():
        info = read_json(meta)
        if Path(info["path"]).exists():
            return Path(info["path"]), info["credit"]
    q = urllib.parse.urlencode({"q": query, "license_type": "commercial", "page_size": 8})
    for r in json.loads(_get("https://api.openverse.org/v1/images/?" + q)).get("results", []):
        if (r.get("width") or 0) < 600 or not r.get("url"):
            continue
        try:
            data = _get(r["url"])
        except Exception:
            continue
        path = CACHE / f"openverse-{_key(query)}{Path(urllib.parse.urlparse(r['url']).path).suffix or '.jpg'}"
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        credit = f"{r['title'][:70]} - {r.get('creator') or 'unknown'}, {r['license'].upper()} {r.get('license_version') or ''}, {r.get('foreign_landing_url')}"
        write_json(meta, {"path": str(path), "credit": credit.strip()})
        return path, credit.strip()
    raise RuntimeError(f"no openly licensed picture on Openverse for {query!r}")
