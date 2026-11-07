"""A lesson -> a vertical video. Narration takes set the clock; every beat is cut into ~2 s scenes (full-screen
animated frames, see scenes.py) that are rendered frame by frame at 30 fps and streamed to ffmpeg."""

from __future__ import annotations

import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from . import scenes
from .paths import Project, config, read_json
from .tts import Narrator, duration

CHUNK_WORDS = 4


def chunks(text: str) -> list[str]:
    words = text.split()
    out, i = [], 0
    while i < len(words):
        piece = words[i : i + CHUNK_WORDS]
        for k, wd in enumerate(piece[:-1]):  # break after punctuation rather than mid-phrase
            if wd[-1] in ",;:.!?" and k >= 1:
                piece = piece[: k + 1]
                break
        out.append(" ".join(piece))
        i += len(piece)
    return out


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


@lru_cache(maxsize=1)
def video_encoder() -> list[str]:
    """NVENC when this ffmpeg has it and it works, else x264."""
    probe = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=black:s=256x256:d=0.1", "-c:v", "h264_nvenc", "-f", "null", "-"],
                           capture_output=True, check=False)
    if probe.returncode == 0:
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "18", "-b:v", "0"]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"]


def render_lesson(project: Project, n: int, engine: str = "kokoro", force: bool = False) -> Path:
    cfg = config()
    meta = project.meta
    lesson = read_json(project.lesson_path(n))
    plan = project.curriculum()
    out_path = project.video_path(n)
    if out_path.exists() and not force:
        return out_path
    fps, gap = cfg["fps"], cfg["gap_seconds"]
    work_dir = project.lesson_dir(n)
    ctx = {"lesson": lesson, "language": meta["language"], "series": meta.get("series_title") or meta["title"],
           "n": n, "total": len(plan["lessons"]), "fps": fps}

    timeline: list[dict] = []          # one entry per scene: start, end, scene, caption chunks of its beat
    caption_track: list[tuple[float, float, str]] = []
    audio_parts: list[Path] = []
    clock = 0.0
    with Narrator(cfg, work_dir / "takes", engine) as narrator, tempfile.TemporaryDirectory(dir=work_dir) as tmp:
        tmpd = Path(tmp)
        for bi, beat in enumerate(lesson["beats"]):
            take = narrator.take(beat["say"])
            length = duration(take) + gap
            padded = tmpd / f"a{bi:02d}.wav"
            _ffmpeg("-i", str(take), "-af", f"apad=pad_dur={gap}", str(padded))
            audio_parts.append(padded)
            specs = beat["scenes"]
            for si, spec in enumerate(specs):
                timeline.append({"start": clock + length * si / len(specs), "end": clock + length * (si + 1) / len(specs), "spec": spec})
            pieces = chunks(beat.get("caption") or beat["say"])
            weights = [max(1, len(p)) for p in pieces]
            at = clock
            for piece, wgt in zip(pieces, weights, strict=True):
                caption_track.append((at, at + length * wgt / sum(weights), piece))
                at += length * wgt / sum(weights)
            clock += length
        total = clock
        if total > cfg["max_seconds"]:
            raise SystemExit(f"Lesson {n} runs {total:.1f}s, over the {cfg['max_seconds']}s Shorts limit - shorten its narration.")

        alist = tmpd / "audio.txt"
        alist.write_text("".join(f"file '{p}'\n" for p in audio_parts))
        voice = tmpd / "voice.wav"
        _ffmpeg("-f", "concat", "-safe", "0", "-i", str(alist), str(voice))

        out_path.parent.mkdir(parents=True, exist_ok=True)
        part = out_path.with_name(out_path.stem + ".part.mp4")
        loud = f"loudnorm=I={cfg['loudness_lufs']}:TP=-1.5:LRA=11"
        cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{scenes.W}x{scenes.H}", "-framerate", str(fps),
               "-i", "-", "-i", str(voice)]
        music = cfg.get("music")
        if music and Path(music).exists():
            cmd += ["-stream_loop", "-1", "-i", str(music), "-filter_complex",
                    f"[2:a]volume={cfg['music_volume_db']}dB[m];[1:a][m]amix=inputs=2:duration=first:normalize=0[mix];[mix]{loud}[a]",
                    "-map", "0:v", "-map", "[a]"]
        else:
            cmd += ["-map", "0:v", "-map", "1:a", "-af", loud]
        cmd += [*video_encoder(), "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(part)]
        enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        frames = round(total * fps)
        current: dict | None = None
        scene = None
        try:
            for f in range(frames):
                t = f / fps
                if current is None or t >= current["end"]:
                    if scene:
                        scene.close()
                    current = next(s for s in timeline if t < s["end"] or s is timeline[-1])
                    scene = scenes.make(current["spec"], ctx)
                    scene.prepare(current["end"] - current["start"])
                img = scene.frame(max(0.0, t - current["start"]))
                cap = next((c for a, b, c in caption_track if a <= t < b), "")
                img = scenes.overlay(img.convert("RGB"), ctx, cap, t / total)
                if f == round(0.6 * fps):
                    img.save(work_dir / "thumb.png")
                enc.stdin.write(img.tobytes())
        finally:
            if scene:
                scene.close()
            enc.stdin.close()
            enc.wait()
        if enc.returncode != 0:
            raise SystemExit("ffmpeg failed while encoding")
        part.replace(out_path)
    return out_path
