"""A lesson -> a vertical video: narration takes, caption-chunk stills, ffmpeg."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from .frames import render_frame
from .paths import Project, config, read_json
from .tts import Narrator, duration

CHUNK_WORDS = 4


def chunks(text: str) -> list[str]:
    words = text.split()
    out, i = [], 0
    while i < len(words):
        take = CHUNK_WORDS
        piece = words[i : i + take]
        # break after punctuation rather than mid-phrase
        for k, wd in enumerate(piece[:-1]):
            if wd[-1] in ",;:.!?" and k >= 1:
                piece = piece[: k + 1]
                break
        out.append(" ".join(piece))
        i += len(piece)
    return out


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def render_lesson(project: Project, n: int, engine: str = "kokoro", force: bool = False) -> Path:
    cfg = config()
    meta = project.meta
    lesson = {**read_json(project.lesson_path(n)), "_language": meta["language"]}
    plan = project.curriculum()
    out_path = project.video_path(n)
    if out_path.exists() and not force:
        return out_path
    w, h, fps, gap = cfg["width"], cfg["height"], cfg["fps"], cfg["gap_seconds"]
    work_dir = project.lesson_dir(n)
    series = meta.get("series_title") or meta["title"]

    segments: list[tuple[Path, float]] = []   # (still, seconds)
    audio_parts: list[Path] = []
    with Narrator(cfg, work_dir / "takes", engine) as narrator, tempfile.TemporaryDirectory(dir=work_dir) as tmp:
        tmpd = Path(tmp)
        for bi, beat in enumerate(lesson["beats"]):
            take = narrator.take(beat["say"])
            length = duration(take) + gap
            padded = tmpd / f"a{bi:02d}.wav"
            _ffmpeg("-i", str(take), "-af", f"apad=pad_dur={gap}", str(padded))
            audio_parts.append(padded)
            pieces = chunks(beat.get("caption") or beat["say"])
            weights = [max(1, len(p)) for p in pieces]
            for ci, piece in enumerate(pieces):
                still = tmpd / f"f{bi:02d}_{ci:02d}.png"
                render_frame(lesson, beat, piece, series, len(plan["lessons"]), w, h).save(still)
                segments.append((still, length * weights[ci] / sum(weights)))
            if bi == 0:
                render_frame(lesson, beat, pieces[0], series, len(plan["lessons"]), w, h).save(work_dir / "thumb.png")

        total = sum(s for _, s in segments)
        if total > cfg["max_seconds"]:
            raise SystemExit(f"Lesson {n} runs {total:.1f}s, over the {cfg['max_seconds']}s Shorts limit - shorten its narration.")
        listing = tmpd / "frames.txt"
        listing.write_text("".join(f"file '{p}'\nduration {s:.3f}\n" for p, s in segments) + f"file '{segments[-1][0]}'\n")
        alist = tmpd / "audio.txt"
        alist.write_text("".join(f"file '{p}'\n" for p in audio_parts))
        voice = tmpd / "voice.wav"
        _ffmpeg("-f", "concat", "-safe", "0", "-i", str(alist), str(voice))

        out_path.parent.mkdir(parents=True, exist_ok=True)
        part = out_path.with_name(out_path.stem + ".part.mp4")
        cmd = ["-f", "concat", "-safe", "0", "-i", str(listing), "-i", str(voice)]
        music = cfg.get("music")
        loud = f"loudnorm=I={cfg['loudness_lufs']}:TP=-1.5:LRA=11"
        if music and Path(music).exists():
            cmd += ["-stream_loop", "-1", "-i", str(music), "-filter_complex",
                    f"[2:a]volume={cfg['music_volume_db']}dB[m];[1:a][m]amix=inputs=2:duration=first:normalize=0[mix];[mix]{loud}[a]",
                    "-map", "0:v", "-map", "[a]"]
        else:
            cmd += ["-map", "0:v", "-map", "1:a", "-af", loud]
        cmd += ["-vf", f"fps={fps},format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(part)]
        _ffmpeg(*cmd)
        part.replace(out_path)
    return out_path
