"""GIFs and short video clips for full-screen scenes.

Providers, tried in order for source "auto": Giphy (free key, reaction GIFs as mp4), Pexels (free key, real
stock video, portrait), Wikimedia Commons (no key, open-licensed video - small and random). Keys go in
config.json ("giphy_key", "pexels_key"); without them only Wikimedia is available, and a scene whose clip is not
found falls back to its own `text`. Downloads are cached in global/clips/ (gitignored)."""

from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path

from .paths import ROOT, config

CACHE = ROOT / "global" / "clips"
UA = {"User-Agent": "codememe/0.1 (educational video project)"}
MAX_BYTES = 40_000_000


def _json(url: str, headers: dict | None = None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _download(url: str, name: str) -> Path | None:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / name
    if path.exists() and path.stat().st_size > 1000:
        return path
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            return None
    except Exception:
        return None
    path.write_bytes(data)
    return path


def _giphy(query: str, key: str) -> list[str]:
    data = _json("https://api.giphy.com/v1/gifs/search?" + urllib.parse.urlencode({"api_key": key, "q": query, "limit": 8, "rating": "g"}))
    return [g["images"]["original_mp4"]["mp4"] for g in data.get("data", []) if g.get("images", {}).get("original_mp4", {}).get("mp4")]


def _pexels(query: str, key: str) -> list[str]:
    data = _json("https://api.pexels.com/videos/search?" + urllib.parse.urlencode({"query": query, "orientation": "portrait", "per_page": 6}),
                 {"Authorization": key})
    urls = []
    for v in data.get("videos", []):
        files = sorted((f for f in v["video_files"] if f.get("file_type") == "video/mp4" and 540 <= (f.get("width") or 0) <= 1100),
                       key=lambda f: -(f.get("width") or 0))
        if files:
            urls.append(files[0]["link"])
    return urls


def _wikimedia(query: str) -> list[str]:
    q = urllib.parse.urlencode({"action": "query", "generator": "search", "gsrsearch": f"filetype:video {query}", "gsrnamespace": 6,
                                "gsrlimit": 8, "prop": "imageinfo", "iiprop": "url|size|mime", "format": "json"})
    pages = _json("https://commons.wikimedia.org/w/api.php?" + q).get("query", {}).get("pages", {})
    return [p["imageinfo"][0]["url"] for p in pages.values() if p.get("imageinfo") and p["imageinfo"][0]["size"] < MAX_BYTES]


def resolve(query: str, source: str = "auto") -> Path | None:
    """A local video file for `query`, or None."""
    cfg = config()
    key = hashlib.sha256(f"{source}|{query}".encode()).hexdigest()[:16]
    for existing in CACHE.glob(key + ".*") if CACHE.exists() else []:
        return existing
    providers = []
    if source in ("auto", "giphy") and cfg.get("giphy_key"):
        providers.append(lambda: _giphy(query, cfg["giphy_key"]))
    if source in ("auto", "pexels") and cfg.get("pexels_key"):
        providers.append(lambda: _pexels(query, cfg["pexels_key"]))
    if source == "wikimedia":  # random, loosely matching - only when asked for explicitly
        providers.append(lambda: _wikimedia(query))
    for provider in providers:
        try:
            urls = provider()
        except Exception:
            continue
        for url in urls:
            got = _download(url, key + (Path(urllib.parse.urlparse(url).path).suffix or ".mp4"))
            if got:
                return got
    return None
