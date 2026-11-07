"""Fonts: the first usable one from well-known places; drop a file in assets/fonts/ to override."""

from __future__ import annotations

import subprocess
from functools import cache, lru_cache

from PIL import ImageFont

from .paths import ROOT

_BOLD = ["DejaVuSans-Bold.ttf", "NotoSans-Bold.ttf", "LiberationSans-Bold.ttf", "Arial Bold.ttf"]
_MONO = ["DejaVuSansMono.ttf", "NotoSansMono-Regular.ttf", "LiberationMono-Regular.ttf"]
_MONO_BOLD = ["DejaVuSansMono-Bold.ttf", "NotoSansMono-Bold.ttf", "LiberationMono-Bold.ttf"]


@cache
def _find(names: tuple[str, ...]) -> str | None:
    for base in [ROOT / "assets" / "fonts"]:
        for name in names:
            if (base / name).exists():
                return str(base / name)
    for name in names:
        out = subprocess.run(["fc-match", "-f", "%{file}", name], capture_output=True, text=True, check=False).stdout
        if out and name.split(".")[0].lower().replace("-", "") in out.lower().replace("-", ""):
            return out
    return None


@lru_cache(maxsize=64)
def font(kind: str, size: int):
    names = {"bold": _BOLD, "mono": _MONO, "monobold": _MONO_BOLD}[kind]
    path = _find(tuple(names))
    return ImageFont.truetype(path, size) if path else ImageFont.load_default(size)
