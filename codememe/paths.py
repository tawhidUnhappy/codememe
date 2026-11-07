"""Where things live. Code is in git; everything personal sits in gitignored places."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "projects"
PROMPTS = ROOT / "prompts"
TOPICS = ROOT / "topics"
MEMES = ROOT / "assets" / "memes"

DEFAULTS = {
    "width": 1080, "height": 1920, "fps": 30, "voice": "af_heart", "engine": "kokoro", "speech_exe": None, "drama3_model": None, "voice_gguf": None,
    "drama3_headroom_gb": 1.5,
    "kokoro_python": None, "kokoro_model_dir": None,
    "music": None, "music_volume_db": -24, "loudness_lufs": -14, "gap_seconds": 0.35, "max_seconds": 59,
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def config() -> dict:
    cfg = dict(DEFAULTS)
    path = ROOT / "config.json"
    if path.exists():
        cfg.update(read_json(path))
    return cfg


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "course"


class Project:
    def __init__(self, name: str):
        self.name = name
        self.dir = PROJECTS / name

    @property
    def meta(self) -> dict:
        return read_json(self.dir / "project.json")

    def exists(self) -> bool:
        return (self.dir / "project.json").exists()

    @property
    def curriculum_path(self) -> Path:
        return self.dir / "curriculum.json"

    def curriculum(self) -> dict:
        return read_json(self.curriculum_path)

    def lesson_dir(self, n: int) -> Path:
        return self.dir / "lessons" / f"{n:03d}"

    def lesson_path(self, n: int) -> Path:
        return self.lesson_dir(n) / "lesson.json"

    def lessons_done(self) -> list[int]:
        return sorted(int(p.parent.name) for p in (self.dir / "lessons").glob("*/lesson.json"))

    def video_path(self, n: int) -> Path:
        return self.dir / "out" / f"{n:03d}.mp4"


def require(name: str) -> Project:
    project = Project(name)
    if not project.exists():
        raise SystemExit(f"No project '{name}'. Existing: {sorted(p.name for p in PROJECTS.glob('*')) or 'none'}")
    return project
