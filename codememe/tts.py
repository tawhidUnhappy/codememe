"""Narration takes. Kokoro-82M runs in its own Python (config "kokoro_python") as a long-lived
worker (codememe/scripts/kokoro_worker.py); a take is kept by the hash of voice + text, so
re-rendering never speaks the same line twice. engine "silent" makes quiet takes of the right length,
for testing a layout without a voice."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from .paths import ROOT

WORKER = ROOT / "codememe" / "scripts" / "kokoro_worker.py"


def take_name(voice: str, text: str) -> str:
    return hashlib.sha256(f"{voice}\n{text}".encode()).hexdigest()[:16] + ".wav"


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(out.strip())


def _silent(text: str, path: Path) -> None:
    seconds = max(0.8, len(text.split()) / 2.6)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", f"{seconds:.2f}", str(path)],
        check=True,
    )


class Narrator:
    def __init__(self, cfg: dict, takes_dir: Path, engine: str = "kokoro"):
        self.cfg, self.dir, self.engine = cfg, takes_dir, engine
        self.proc: subprocess.Popen | None = None
        takes_dir.mkdir(parents=True, exist_ok=True)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if self.proc:
            try:
                self.proc.stdin.write(json.dumps({"cmd": "shutdown"}) + "\n")
                self.proc.stdin.flush()
                self.proc.wait(timeout=20)
            except Exception:
                self.proc.kill()

    def _start(self) -> None:
        py, model = self.cfg.get("kokoro_python"), self.cfg.get("kokoro_model_dir")
        if not py or not model:
            raise SystemExit('Kokoro is not configured: set "kokoro_python" and "kokoro_model_dir" in config.json '
                             "(see config.example.json), or render with --silent to test the layout.")
        self.proc = subprocess.Popen(
            [py, str(WORKER), "--model_dir", model], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=sys.stderr, text=True, bufsize=1,
        )
        first = json.loads(self.proc.stdout.readline() or "{}")
        if first.get("event") != "ready":
            raise SystemExit(f"Kokoro did not start: {first}")

    def take(self, text: str) -> Path:
        voice = self.cfg["voice"] if self.engine == "kokoro" else "silent"
        path = self.dir / take_name(voice, text)
        if path.exists() and path.stat().st_size > 1000:
            return path
        part = path.with_name(path.stem + ".part.wav")
        if self.engine == "silent":
            _silent(text, part)
        else:
            if not self.proc:
                self._start()
            self.proc.stdin.write(json.dumps({"cmd": "synthesize", "voice": voice, "text": text, "output_path": str(part)}) + "\n")
            self.proc.stdin.flush()
            reply = json.loads(self.proc.stdout.readline() or "{}")
            if not reply.get("ok"):
                raise SystemExit(f"Kokoro failed on {text[:40]!r}: {reply.get('error')}")
        part.replace(path)
        return path
