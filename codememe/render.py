"""A lesson -> a vertical video. Narration takes set the clock; every beat is cut into ~2 s scenes (full-screen
animated frames, see scenes.py) that are rendered frame by frame at 30 fps and streamed to ffmpeg."""

from __future__ import annotations

import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from . import scenes
from .align import align, heard_words
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


def _caption_chunks(words: list[str], times: list[tuple[float, float]], scene_end: float) -> list[tuple[float, float, str]]:
    """Caption chunks of the actual words, each on screen from when its first word is spoken."""
    out, i = [], 0
    while i < len(words):
        piece = words[i : i + CHUNK_WORDS]
        for k, wd in enumerate(piece[:-1]):
            if wd[-1] in ",;:.!?" and k >= 1:
                piece = piece[: k + 1]
                break
        out.append([times[i][0], 0.0, " ".join(piece)])
        i += len(piece)
    for k, c in enumerate(out):
        c[1] = out[k + 1][0] if k + 1 < len(out) else scene_end
    return [tuple(c) for c in out]


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
           "n": n, "total": len(plan["lessons"]), "fps": fps, "credits": set()}

    # 1. narration takes (one per beat = one spoken passage)
    beat_say = [" ".join(sc["say"].strip() for sc in beat["scenes"]) for beat in lesson["beats"]]
    with Narrator(cfg, work_dir / "takes", engine) as narrator:
        takes = [narrator.take(text) for text in beat_say]
    lengths = [duration(t) for t in takes]
    # 2. when each word is actually spoken
    heard = heard_words(takes, cfg)

    timeline: list[dict] = []
    caption_track: list[tuple[float, float, str]] = []
    audio_parts: list[Path] = []
    clock = 0.0
    with tempfile.TemporaryDirectory(dir=work_dir) as tmp:
        tmpd = Path(tmp)
        for bi, beat in enumerate(lesson["beats"]):
            beat_len = lengths[bi] + gap
            padded = tmpd / f"a{bi:02d}.wav"
            _ffmpeg("-i", str(takes[bi]), "-af", f"apad=pad_dur={gap}", str(padded))
            audio_parts.append(padded)
            words = beat_say[bi].split()
            times = align(words, heard.get(str(takes[bi])), lengths[bi])
            at = 0
            starts, ends = [], []
            for si, spec in enumerate(beat["scenes"]):
                count = len(spec["say"].split())
                starts.append(clock if si == 0 else clock + max(0.0, times[at][0] - 0.05))
                at += count
            ends = [*starts[1:], clock + beat_len]
            at = 0
            for spec, st, en in zip(beat["scenes"], starts, ends, strict=True):
                frag = spec["say"].split()
                count = len(frag)
                timeline.append({"start": st, "end": max(en, st + 0.3), "spec": spec})
                abs_times = [(clock + a, clock + b) for a, b in times[at : at + count]]
                if spec.get("caption"):
                    # shown text differs from the speech: each caption word takes the time of the spoken word at the same relative position
                    cap_words = spec["caption"].split()
                    cap_times = [abs_times[min(count - 1, int(k * count / len(cap_words)))] for k in range(len(cap_words))]
                    caption_track += _caption_chunks(cap_words, cap_times, en)
                else:
                    caption_track += _caption_chunks(frag, abs_times, en)
                at += count
            clock += beat_len
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
                    current = next((s for s in timeline if t < s["end"]), timeline[-1])
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
    (work_dir / "credits.txt").write_text("\n".join(sorted(ctx["credits"])) + ("\n" if ctx["credits"] else ""))
    return out_path
