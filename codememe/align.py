"""Word-level timing of a narration take, so scenes and captions change exactly when their words are spoken.

faster-whisper runs in its own Python (config "whisper_python" + "whisper_model_dir"); the spoken words it hears are
matched to the words of the script (difflib), and any script word it missed gets an interpolated time. Without
whisper the words are spread over the take by length (rougher, but never wrong in order). Cached beside each take."""

from __future__ import annotations

import difflib
import json
import re
import subprocess
from pathlib import Path

from .paths import ROOT, read_json, write_json

WORKER = ROOT / "codememe" / "scripts" / "align_worker.py"


def norm(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", word.lower())


def heard_words(takes: list[Path], cfg: dict) -> dict[str, list]:
    """{take path: [[word, start, end], ...]} for takes without a cache file; runs whisper once for all."""
    out: dict[str, list] = {}
    todo = []
    for t in takes:
        cache = t.with_suffix(".words.json")
        if cache.exists():
            out[str(t)] = read_json(cache)
        else:
            todo.append(t)
    if todo and cfg.get("whisper_python") and cfg.get("whisper_model_dir"):
        proc = subprocess.run([cfg["whisper_python"], str(WORKER), "--model", cfg["whisper_model_dir"], *map(str, todo)],
                              capture_output=True, text=True, check=False)
        if proc.returncode == 0:
            for path, words in json.loads(proc.stdout).items():
                write_json(Path(path).with_suffix(".words.json"), words)
                out[path] = words
        else:
            print("warning: whisper alignment failed, using proportional timing:", proc.stderr.strip()[-200:])
    return out


def align(script_words: list[str], heard: list | None, take_seconds: float) -> list[tuple[float, float]]:
    """(start, end) seconds for each script word."""
    n = len(script_words)
    if not heard:
        total = sum(max(1, len(w)) for w in script_words)
        at, out = 0.0, []
        for w in script_words:
            span = take_seconds * max(1, len(w)) / total
            out.append((at, at + span))
            at += span
        return out
    a = [norm(w) for w in script_words]
    b = [norm(h[0]) for h in heard]
    times: list[tuple[float, float] | None] = [None] * n
    for block in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(block.size):
            times[block.a + k] = (heard[block.b + k][1], heard[block.b + k][2])
    # interpolate the words whisper did not give a time to (heard differently, e.g. "p y" vs "py")
    known = [i for i, t in enumerate(times) if t]
    if not known:
        return align(script_words, None, take_seconds)
    for i in range(n):
        if times[i]:
            continue
        left = max((k for k in known if k < i), default=None)
        right = min((k for k in known if k > i), default=None)
        lo = times[left][1] if left is not None else 0.0
        hi = times[right][0] if right is not None else take_seconds
        gap = [j for j in range(n) if times[j] is None and (left is None or j > left) and (right is None or j < right)]
        step = (hi - lo) / (len(gap) + 1 if len(gap) else 1)
        pos = gap.index(i)
        times[i] = (lo + step * pos, lo + step * (pos + 1))
    return times  # type: ignore[return-value]
