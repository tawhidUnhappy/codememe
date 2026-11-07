"""Checkers for the three LLM replies. Each returns a list of problems; empty means good.

prompts/*.md and these checks move together: change one, change the other."""

from __future__ import annotations

import re

from .paths import TOPICS, read_json
from .runcheck import run_snippet

SHOWS = ("meme", "code", "output", "takeaway")
TEMPLATES = ("memegen", "classic", "choice", "brain")
MAX_WORDS = 125          # about 46 s at Kokoro's pace, leaving room for pauses under 59 s
MAX_CODE_LINES = 12
MAX_CODE_WIDTH = 34      # characters; wider code gets tiny on a phone
UNSPEAKABLE = re.compile(r"[`{}\[\]<>=#*_\\|~^]|->|::|\(\)|==")


def topic_areas(language: str) -> list[dict]:
    path = TOPICS / f"{language.lower().replace('+', 'p')}.json"
    return read_json(path)["areas"] if path.exists() else []


def check_curriculum(reply: dict, meta: dict) -> list[str]:
    bad: list[str] = []
    if reply.get("kind") != "curriculum":
        return ['The reply must have "kind": "curriculum".']
    areas = reply.get("areas")
    lessons = reply.get("lessons")
    if not isinstance(areas, list) or not areas:
        return ['"areas" must be the list of {"id","name"} the course covers.']
    if not isinstance(lessons, list) or not lessons:
        return ['"lessons" must be a non-empty list.']
    area_ids = [a.get("id") for a in areas if isinstance(a, dict)]
    if len(set(area_ids)) != len(area_ids) or not all(area_ids):
        bad.append('"areas" ids must be unique and non-empty.')
    for need in topic_areas(meta["language"]):
        if need["id"] not in area_ids:
            bad.append(f'Missing required area "{need["id"]}" ({need["name"]}).')
    covered: set[str] = set()
    titles: set[str] = set()
    for i, lesson in enumerate(lessons, 1):
        where = f"lesson {i}"
        if lesson.get("n") != i:
            bad.append(f'{where}: "n" must be {i} (lessons are numbered 1..N with no gaps).')
        for key in ("title", "concepts", "covers", "meme_idea"):
            if not lesson.get(key):
                bad.append(f'{where}: missing "{key}".')
        title = str(lesson.get("title", "")).strip().lower()
        if title in titles:
            bad.append(f'{where}: duplicate title "{title}".')
        titles.add(title)
        for a in lesson.get("covers") or []:
            if a not in area_ids:
                bad.append(f'{where}: covers unknown area "{a}".')
            covered.add(a)
    for a in area_ids:
        if a not in covered:
            bad.append(f'Area "{a}" is not covered by any lesson.')
    want = meta.get("lessons")
    if want and len(lessons) != want:
        bad.append(f"The course must have exactly {want} lessons; the reply has {len(lessons)}.")
    return bad


def _words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", text))


SCENE_TYPES = ("meme", "clip", "image", "terminal", "code", "text", "takeaway")
MEDIA = ("meme", "clip", "image")
MIN_FRAGMENT, MAX_FRAGMENT = 3, 10
MAX_TERMINAL_WIDTH = 40


def _check_scene(spec: dict, where: str, n_code_lines: int, known_memes: dict) -> list[str]:
    bad: list[str] = []
    kind = spec.get("type")
    if kind not in SCENE_TYPES:
        return [f'{where}: scene type must be one of {", ".join(SCENE_TYPES)} (got {kind!r}).']
    if kind == "meme":
        info = known_memes.get(spec.get("id"))
        caps = spec.get("captions")
        if known_memes and info is None:
            bad.append(f'{where}: meme id "{spec.get("id")}" is not a memegen template (use one from the list).')
        elif not isinstance(caps, list) or not caps or (info and len(caps) != info["lines"]):
            bad.append(f'{where}: the "{spec.get("id")}" meme needs exactly {info["lines"] if info else "the right number of"} captions.')
        else:
            bad += [f'{where}: meme caption "{str(c)[:20]}..." is over 45 characters.' for c in caps if len(str(c)) > 45]
    elif kind == "clip":
        if not str(spec.get("query", "")).strip() or not str(spec.get("text", "")).strip():
            bad.append(f'{where}: a clip needs "query" (what to search a GIF/video for) and "text" (overlay text, also used if no clip is found).')
        if len(str(spec.get("text", ""))) > 40:
            bad.append(f"{where}: clip text is over 40 characters.")
    elif kind == "image":
        src = spec.get("source", "screenshot")
        if src == "screenshot" and not str(spec.get("url", "")).startswith("http"):
            bad.append(f'{where}: a screenshot image needs "url" (the page to grab).')
        elif src in ("commons", "openverse") and not str(spec.get("query", "")).strip():
            bad.append(f'{where}: a {src} image needs "query".')
        elif src not in ("screenshot", "commons", "openverse"):
            bad.append(f'{where}: image "source" must be screenshot, commons or openverse.')
        hl = spec.get("highlight")
        if hl is not None and not (isinstance(hl, list) and len(hl) == 4 and all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in hl)
                                   and hl[0] < hl[2] and hl[1] < hl[3]):
            bad.append(f'{where}: "highlight" must be [x0, y0, x1, y1] fractions (0-1) of the page, top-left to bottom-right.')
    elif kind == "text":
        if not str(spec.get("text", "")).strip() or len(spec["text"]) > 60:
            bad.append(f'{where}: a text scene needs "text" of 1-60 characters.')
    elif kind == "terminal":
        if spec.get("os") not in ("windows", "mac", "linux"):
            bad.append(f'{where}: terminal "os" must be windows, mac or linux.')
        rows = spec.get("lines")
        if not isinstance(rows, list) or not rows or len(rows) > 9:
            bad.append(f'{where}: terminal "lines" must be 1-9 rows of {{"cmd": ...}} or {{"out": ...}}.')
        else:
            for r in rows:
                prompt = len(r.get("prompt", "")) or {"windows": 15, "mac": 12, "linux": 10}.get(spec.get("os"), 12)
                text = r.get("cmd", r.get("out"))
                if not isinstance(text, str) or ("cmd" in r) == ("out" in r):
                    bad.append(f'{where}: each terminal row has exactly one of "cmd" or "out".')
                elif "cmd" in r and prompt + len(text) > MAX_TERMINAL_WIDTH + 4:
                    bad.append(f"{where}: terminal command too long for the screen: {text[:30]}...")
    elif kind == "code":
        focus = spec.get("focus")
        if focus is not None and not (isinstance(focus, list) and len(focus) == 2 and 1 <= focus[0] <= focus[1] <= max(n_code_lines, 1)):
            bad.append(f'{where}: "focus" must be [first, last] line numbers inside the code.')
    return bad


def check_lesson(lesson: dict, meta: dict, plan: dict | None, run_code: bool = True) -> tuple[list[str], list[str]]:
    """(problems, warnings) for one lesson (format 2: beats made of full-screen scenes)."""
    from .memegen import catalog
    bad: list[str] = []
    warn: list[str] = []
    n = lesson.get("n")
    where = f"lesson {n}"
    if plan is not None and not (isinstance(n, int) and 1 <= n <= len(plan["lessons"])):
        return [f'{where}: "n" is not a lesson number of this course.'], warn
    for key in ("title", "hook", "takeaway"):
        if not str(lesson.get(key, "")).strip():
            bad.append(f'{where}: missing "{key}".')
    if len(str(lesson.get("takeaway", "")).split()) > 14:
        bad.append(f"{where}: takeaway is over 14 words.")
    srcs = lesson.get("sources")
    if not isinstance(srcs, list) or not srcs or not all(str(u).startswith("http") for u in srcs):
        bad.append(f'{where}: "sources" must list the URLs (official docs first) every factual statement was checked against.')

    code = lesson.get("code") or {}
    source = str(code.get("source", ""))
    lines = source.splitlines()
    if not source.strip():
        bad.append(f"{where}: code.source is empty.")
    if len(lines) > MAX_CODE_LINES:
        bad.append(f"{where}: code is {len(lines)} lines; the screen fits {MAX_CODE_LINES}.")
    if any(len(ln.expandtabs(4)) > MAX_CODE_WIDTH for ln in lines):
        bad.append(f"{where}: a code line is over {MAX_CODE_WIDTH} characters.")
    if code.get("expect", "ok") not in ("ok", "error"):
        bad.append(f'{where}: code.expect must be "ok" or "error".')

    beats = lesson.get("beats")
    if not isinstance(beats, list) or len(beats) < 4:
        return [*bad, f"{where}: beats must be a list of at least 4."], warn
    known = catalog()
    total, kinds = 0, []
    for j, beat in enumerate(beats, 1):
        bw = f"{where} beat {j}"
        sc = beat.get("scenes")
        if not isinstance(sc, list) or not sc:
            bad.append(f'{bw}: "scenes" must be a list of full-screen scenes.')
            continue
        for k, spec in enumerate(sc, 1):
            sw = f"{bw} scene {k}"
            say = str(spec.get("say", "")).strip()
            words = _words(say)
            total += words
            if not MIN_FRAGMENT <= words <= MAX_FRAGMENT:
                bad.append(f'{sw}: "say" is the words spoken while this picture is on screen: {MIN_FRAGMENT}-{MAX_FRAGMENT} words (about 2 seconds); it has {words}.')
            if UNSPEAKABLE.search(say):
                bad.append(f'{sw}: "say" holds code symbols; narration is plain speech: {say[:40]}')
            if "caption" in spec and (not isinstance(spec["caption"], str) or not spec["caption"].strip()):
                bad.append(f'{sw}: "caption" must be non-empty text (or leave it out).')
            bad += _check_scene(spec, sw, len(lines), known)
            kinds.append(spec.get("type"))
    if total > MAX_WORDS:
        bad.append(f"{where}: narration is {total} words; the limit is {MAX_WORDS} (a Short is under 59 seconds).")
    if total < 40:
        warn.append(f"{where}: narration is only {total} words - thin for a lesson.")
    if sum(k in MEDIA for k in kinds) < 3:
        bad.append(f"{where}: use at least 3 real-media scenes (meme / image / clip) - screenshots of the real thing beat text slides.")
    if "code" not in kinds and "terminal" not in kinds:
        bad.append(f"{where}: show the code or a terminal.")
    last = (beats[-1].get("scenes") or [{}])[-1]
    if last.get("type") != "takeaway":
        bad.append(f'{where}: the very last scene must be {{"type": "takeaway"}}.')
    if not known:
        warn.append(f"{where}: memegen catalog unavailable (offline) - meme ids not checked.")

    if run_code and source.strip() and not bad:
        problem, note = run_snippet(meta["language"], source, code.get("expect", "ok"), str(code.get("expected_output", "")))
        if problem:
            bad.append(f"{where}: {problem}")
        if note:
            warn.append(f"{where}: {note}")
    return bad, warn


def check_lessons(reply: dict, meta: dict, plan: dict | None, run_code: bool = True):
    if reply.get("kind") != "lessons" or not isinstance(reply.get("lessons"), list) or not reply["lessons"]:
        return ['The reply must be {"kind": "lessons", "lessons": [ ... ]}.'], []
    bad: list[str] = []
    warn: list[str] = []
    seen: set = set()
    for lesson in reply["lessons"]:
        b, w = check_lesson(lesson, meta, plan, run_code)
        bad += b
        warn += w
        if lesson.get("n") in seen:
            bad.append(f"lesson {lesson.get('n')} appears twice in the reply.")
        seen.add(lesson.get("n"))
    return bad, warn


def check_upload(reply: dict) -> list[str]:
    if reply.get("kind") != "upload" or not isinstance(reply.get("videos"), list):
        return ['The reply must be {"kind": "upload", "videos": [ ... ]}.']
    bad = []
    for v in reply["videos"]:
        n = v.get("n")
        title = str(v.get("title", ""))
        if not title or len(title) > 100:
            bad.append(f"video {n}: title must be 1-100 characters.")
        if not str(v.get("description", "")).strip():
            bad.append(f"video {n}: missing description.")
        if not isinstance(v.get("tags"), list) or not v["tags"]:
            bad.append(f"video {n}: tags must be a non-empty list.")
    return bad
