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
DRAMA_WORKER = ROOT / "codememe" / "scripts" / "drama3_worker.py"


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

    def _start_drama3(self) -> None:
        c = self.cfg
        need = ("speech_exe", "drama3_model", "voice_gguf")
        if not all(c.get(k) for k in need):
            raise SystemExit(f"Drama 3 needs {', '.join(need)} in config.json (see config.example.json).")
        self.proc = subprocess.Popen(
            [sys.executable, str(DRAMA_WORKER), "--speech", c["speech_exe"], "--model", c["drama3_model"],
             "--voices_dir", str(Path(c["voice_gguf"]).parent), "--headroom_gb", str(c.get("drama3_headroom_gb", 1.5))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr, text=True, bufsize=1)
        first = json.loads(self.proc.stdout.readline() or "{}")
        if first.get("event") != "ready":
            raise SystemExit(f"Drama 3 did not start: {first}")

    def _voice_id(self) -> str:
        if self.engine == "kokoro":
            return self.cfg["voice"]
        if self.engine == "drama3":
            f = Path(self.cfg.get("voice_gguf") or "")
            return f"drama3:{f.name}:{f.stat().st_mtime_ns if f.exists() else 0}"
        return "silent"

    def take(self, text: str) -> Path:
        voice = self._voice_id()
        path = self.dir / take_name(voice, text)
        if path.exists() and path.stat().st_size > 1000:
            return path
        part = path.with_name(path.stem + ".part.wav")
        if self.engine == "silent":
            _silent(text, part)
        else:
            if not self.proc:
                self._start_drama3() if self.engine == "drama3" else self._start()
            request = {"cmd": "synthesize", "voice": voice, "text": text, "output_path": str(part)}
            if self.engine == "drama3":
                request["voice_gguf"] = str(Path(self.cfg["voice_gguf"]).resolve())
            self.proc.stdin.write(json.dumps(request) + "\n")
            self.proc.stdin.flush()
            reply = json.loads(self.proc.stdout.readline() or "{}")
            if not reply.get("ok"):
                raise SystemExit(f"{self.engine} failed on {text[:40]!r}: {reply.get('error')}")
        part.replace(path)
        return path
