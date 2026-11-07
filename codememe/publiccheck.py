"""This repo is public. Scan every tracked and staged file for what must never be in it: API keys, OAuth
secrets and tokens, emails, absolute home paths. (Gitignored files - config.json, global/, projects/ - are
the user's and are never scanned or committed.)"""

from __future__ import annotations

import re
import subprocess

from .paths import ROOT

PATTERNS = {
    "Google OAuth client secret": r"GOCSPX-[A-Za-z0-9_-]{10,}",
    "Google OAuth client id": r"\d{8,}-[a-z0-9]{20,}\.apps\.googleusercontent\.com",
    "Google access/refresh token": r"\b(ya29\.[A-Za-z0-9_-]{20,}|1//[A-Za-z0-9_-]{30,})",
    "API key": r"\b(AIza[0-9A-Za-z_-]{30,}|sk-[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}|github_pat_\w{30,})",
    "private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "e-mail address": r"[A-Za-z0-9._%+-]+@(?!users\.noreply\.github\.com|anthropic\.com)[A-Za-z0-9.-]+\.[a-z]{2,}",
    "absolute home/mount path": r"(/home/[a-z][\w.-]*/|/mnt/[a-z]+/|/Users/[A-Za-z][\w.-]*/)(?!path|to/)",
    "secret assigned in a file": r"[\"']?(client_secret|refresh_token|access_token|api_key)[\"']?\s*[:=]\s*[\"'][A-Za-z0-9_./-]{16,}[\"']",
}
SKIP = {"codememe/publiccheck.py"}


def _git(*args: str) -> list[str]:
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [x for x in out.split("\0") if x]


def scan() -> list[str]:
    files = set(_git("ls-files", "-z")) | set(_git("diff", "--cached", "--name-only", "-z"))
    problems = []
    for name in sorted(files - SKIP):
        path = ROOT / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in PATTERNS.items():
            for m in re.finditer(pattern, text):
                line = text.count("\n", 0, m.start()) + 1
                problems.append(f"{name}:{line}: {label}")
    # tracked files that should only ever be local
    for name in files:
        if re.search(r"(client_secret|token)[^/]*\.json$|^config\.json$|^global/|^projects/", name):
            problems.append(f"{name}: a local-only file is tracked")
    return problems
