"""Live facts, fetched at prompt time so lessons never state a stale version or URL."""

from __future__ import annotations

import re

from .sources import cached


def latest_version(language: str) -> str:
    lang = language.lower()
    try:
        if lang == "python":
            page = cached("https://www.python.org/downloads/")
            if page:
                m = re.search(r"Download Python (\d+\.\d+\.\d+)", page.decode("utf-8", "ignore"))
                return f"Latest stable Python: {m.group(1)} (python.org/downloads) - use this number in any version output" if m else ""
        if lang == "rust":
            page = cached("https://static.rust-lang.org/dist/channel-rust-stable.toml")
            m = re.search(r'\[pkg\.rust\]\s*version = "(\d+\.\d+\.\d+)', page.decode()) if page else None
            return f"Latest stable Rust: {m.group(1)} (rust-lang.org)" if m else ""
    except Exception:
        return ""
    return ""
