"""Real meme templates (Drake, Distracted Boyfriend, Galaxy Brain, ...) from the open-source memegen project
(github.com/jacebrowning/memegen, MIT; ~200 templates). No account and no key: the template list comes from
api.memegen.link, and each template's clean background picture and text-box positions from the project's
repository. The captions are drawn here, locally - so there is no watermark, and after the first download a
template works offline. Downloads are cached in global/memegen/ (gitignored).

The template pictures belong to their original owners (memes are used under fair use, like on any meme page)."""

from __future__ import annotations

import re
import time
import urllib.error
import urllib.request
from functools import lru_cache

from PIL import Image, ImageDraw

from .fonts import font
from .memecards import wrap
from .paths import ROOT, read_json, write_json

CACHE = ROOT / "global" / "memegen"
CATALOG_URL = "https://api.memegen.link/templates/"
RAW = "https://raw.githubusercontent.com/jacebrowning/memegen/main/templates/{id}/{file}"
CURATED = ROOT / "assets" / "memegen_curated.json"
MAX_AGE = 30 * 86400


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "codememe"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def catalog() -> dict[str, dict]:
    """id -> {"name", "lines"} for every template (cached for 30 days; a stale cache is used if offline)."""
    path = CACHE / "templates.json"
    if not path.exists() or time.time() - path.stat().st_mtime > MAX_AGE:
        try:
            import json
            data = json.loads(_get(CATALOG_URL))
            write_json(path, [{"id": t["id"], "name": t["name"], "lines": t["lines"]} for t in data])
        except (urllib.error.URLError, OSError, ValueError):
            if not path.exists():
                return {}
    return {t["id"]: t for t in read_json(path)}


def curated() -> dict[str, str]:
    return read_json(CURATED) if CURATED.exists() else {}


def _parse_boxes(yml: str) -> list[dict]:
    """The `text:` list of a template's config.yml (flat `key: value` items - no YAML library needed)."""
    block = re.search(r"^text:\n(.*?)(?=^\S)", yml + "\nend:", re.S | re.M)
    boxes: list[dict] = []
    for line in (block.group(1) if block else "").splitlines():
        m = re.match(r"\s*(- )?(\w+):\s*(.*)$", line)
        if not m:
            continue
        if m.group(1):
            boxes.append({})
        key, val = m.group(2), m.group(3).strip()
        try:
            boxes[-1][key] = float(val)
        except ValueError:
            boxes[-1][key] = val
    return boxes


@lru_cache(maxsize=64)
def template(tid: str) -> tuple[Image.Image, list[dict]]:
    folder = CACHE / tid
    folder.mkdir(parents=True, exist_ok=True)
    cfg = folder / "config.yml"
    if not cfg.exists():
        cfg.write_bytes(_get(RAW.format(id=tid, file="config.yml")))
    pic = next(iter(folder.glob("default.*")), None)
    if pic is None:
        for ext in ("jpg", "png"):
            try:
                data = _get(RAW.format(id=tid, file=f"default.{ext}"))
            except urllib.error.HTTPError:
                continue
            pic = folder / f"default.{ext}"
            pic.write_bytes(data)
            break
    if pic is None:
        raise RuntimeError(f"no picture for meme template {tid}")
    return Image.open(pic).convert("RGB"), _parse_boxes(cfg.read_text())


def _draw(d: ImageDraw.ImageDraw, text: str, box: tuple[int, int, int, int], dark: bool, upper: bool) -> None:
    x, y, w, h = box
    text = text.upper() if upper else text
    size = max(18, int(h * 0.9))
    while size > 14:
        fnt = font("bold", size)
        lines = wrap(d, text, fnt, w)
        if len(lines) * size * 1.15 <= h and all(d.textlength(ln, font=fnt) <= w for ln in lines):
            break
        size -= 2
    top = y + (h - len(lines) * size * 1.15) / 2
    fill, stroke = ((20, 20, 20), None) if dark else ((255, 255, 255), (0, 0, 0))
    for ln in lines:
        d.text((x + (w - d.textlength(ln, font=fnt)) / 2, top), ln, font=fnt, fill=fill,
               stroke_width=max(2, size // 9) if stroke else 0, stroke_fill=stroke)
        top += size * 1.15


def render_meme(tid: str, captions: list[str], width: int = 1000) -> Image.Image:
    base, boxes = template(tid)
    img = base.resize((width, round(base.height * width / base.width)))
    d = ImageDraw.Draw(img)
    for box, text in zip(boxes, captions, strict=False):
        if not str(text).strip():
            continue
        W, H = img.size
        _draw(d, str(text), (round(box.get("anchor_x", 0) * W), round(box.get("anchor_y", 0) * H),
                             round(box.get("scale_x", 1) * W), round(box.get("scale_y", 0.2) * H)),
              box.get("color") == "black", box.get("style") == "upper")
    return img
