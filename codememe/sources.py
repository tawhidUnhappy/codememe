"""Material pulled from free, key-less servers - so a lesson is written from sources, not from memory:

- official docs   docs.python.org pages mapped per area in topics/<language>.json ("docs"); the paragraphs that best
                  match the lesson's concepts
- Wikipedia       REST summary of the concept (context + correct terminology)
- Stack Overflow  the top real questions beginners ask about the concept (Stack Exchange API, 300 calls/day per IP)
                  - what people actually get stuck on is the best meme material
- JokeAPI         programming jokes (safe mode) for hook ideas
- Openverse       CC0 / public-domain music for the background (music-fetch)

Everything is cached in global/sources/ (gitignored) and every fetch fails soft: no network = an empty section."""

from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

from .paths import ROOT, TOPICS, read_json, write_json

CACHE = ROOT / "global" / "sources"
UA = {"User-Agent": "codememe/0.1 (educational video project)", "Accept-Encoding": "identity"}
TAGS = {"c++": "c%2B%2B", "cpp": "c%2B%2B", "c#": "c%23"}


def _get(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            import gzip
            data = gzip.decompress(data)
        return data


def cached(url: str, timeout: int = 25) -> bytes | None:
    path = CACHE / (hashlib.sha256(url.encode()).hexdigest()[:20] + ".bin")
    if path.exists():
        return path.read_bytes()
    try:
        data = _get(url, timeout)
    except Exception:
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def _text(markup: str) -> str:
    markup = re.sub(r"(?is)<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", markup)
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", markup))).strip()


def wikipedia(term: str, language: str) -> str:
    q = urllib.parse.quote(f"{term} {language} programming")
    raw = cached(f"https://en.wikipedia.org/w/rest.php/v1/search/page?q={q}&limit=1")
    try:
        key = json.loads(raw)["pages"][0]["key"]
        summary = json.loads(cached("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(key)))
        words = {w for w in re.findall(r"[a-z]{4,}", term.lower())} - {language.lower(), "programming", "language", "basics", "hello"}
        haystack = (summary["title"] + " " + summary["extract"]).lower()
        if not any(w in haystack for w in words):
            return ""
        return f"{summary['title']}: {summary['extract'][:500]}"
    except Exception:
        return ""


def stackoverflow(language: str, concept: str, n: int = 4) -> list[str]:
    tag = TAGS.get(language.lower(), urllib.parse.quote(language.lower()))
    q = urllib.parse.quote(concept)
    raw = cached(f"https://api.stackexchange.com/2.3/search/advanced?order=desc&sort=votes&q={q}&tagged={tag}&site=stackoverflow&pagesize={n}")
    try:
        return [f"{html.unescape(i['title'])} ({i['score']} votes)" for i in json.loads(raw)["items"]]
    except Exception:
        return []


def docs_snippets(language: str, area: str, concepts: list[str], n: int = 2) -> list[str]:
    path = TOPICS / f"{language.lower().replace('+', 'p')}.json"
    urls = (read_json(path).get("docs", {}) if path.exists() else {}).get(area) or []
    urls = [urls] if isinstance(urls, str) else urls
    out: list[str] = []
    for url in urls:
        out += _docs_page(url, language, concepts, n)
    return out[:n + 1]


def _docs_page(url: str, language: str, concepts: list[str], n: int) -> list[str]:
    raw = cached(url)
    if not raw:
        return []
    skip = {language.lower(), "the", "and", "with", "from", "for", "vs", "str", "int"}
    words = {w.lower() for c in concepts for w in re.findall(r"[A-Za-z_]{3,}", c)} - skip
    body = re.search(r'(?is)<div[^>]*role="main"[^>]*>(.*)', raw.decode("utf-8", "ignore"))
    paras = [_text(p) for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", body.group(1) if body else "")]
    scored = sorted((p for p in paras if len(p) > 80), key=lambda p: -sum(w in p.lower() for w in words))
    return [f"{p[:420]} [{url}]" for p in scored[:n] if sum(w in p.lower() for w in words) >= 2]


def jokes(n: int = 3) -> list[str]:
    out = []
    for i in range(n):
        raw = _get_uncached(f"https://v2.jokeapi.dev/joke/Programming?type=twopart&safe-mode&idRange={i * 40}-{i * 40 + 40}")
        try:
            j = json.loads(raw)
            out.append(f"{j['setup']} / {j['delivery']}")
        except Exception:
            pass
    return out


def _get_uncached(url: str) -> bytes | None:
    try:
        return _get(url)
    except Exception:
        return None


def research(meta: dict, lesson: dict) -> dict:
    """The reference pack for one planned lesson (cached on disk by the fetches themselves)."""
    lang, concepts = meta["language"], lesson["concepts"]
    return {
        "docs": [s for area in lesson["covers"] for s in docs_snippets(lang, area, concepts)][:3],
        "wikipedia": wikipedia(lesson["title"], lang),
        "beginner_questions": stackoverflow(lang, concepts[0]) if concepts else [],
    }


def pack_text(pack: dict) -> str:
    lines = []
    for d in pack["docs"]:
        lines.append(f"  - official docs: {d}")
    if pack["wikipedia"]:
        lines.append(f"  - wikipedia: {pack['wikipedia']}")
    for q in pack["beginner_questions"]:
        lines.append(f"  - real beginner question: {q}")
    return "\n".join(lines) or "  - (nothing fetched - offline)"


def music_search(query: str, minimum_seconds: int = 45) -> list[dict]:
    q = urllib.parse.quote(query)
    raw = _get_uncached(f"https://api.openverse.org/v1/audio/?q={q}&license=cc0,pdm&page_size=20")
    try:
        found = json.loads(raw)["results"]
    except Exception:
        return []
    return [r for r in found if (r.get("duration") or 0) >= minimum_seconds * 1000 and r.get("url")]


def music_fetch(query: str, minimum_seconds: int = 45) -> Path:
    hits = music_search(query, minimum_seconds) or music_search(query, 0)
    if not hits:
        raise SystemExit(f"No CC0/public-domain track found for {query!r} on Openverse.")
    hit = hits[0]
    folder = ROOT / "global" / "music"
    folder.mkdir(parents=True, exist_ok=True)
    ext = Path(urllib.parse.urlparse(hit["url"]).path).suffix or ".mp3"
    path = folder / (re.sub(r"[^a-z0-9]+", "-", hit["title"].lower()).strip("-")[:50] + ext)
    path.write_bytes(_get(hit["url"], 120))
    write_json(path.with_suffix(".license.json"), {k: hit.get(k) for k in ("title", "creator", "license", "license_url", "foreign_landing_url")})
    print(f"{hit['title']} - {hit.get('creator')} - license {hit['license']} (no attribution needed) -> {path}")
    return path
