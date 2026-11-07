"""Checkers for the three LLM replies. Each returns a list of problems; empty means good.

prompts/*.md and these checks move together: change one, change the other."""

from __future__ import annotations

import re

from .paths import MEMES, TOPICS, read_json
from .runcheck import run_snippet

SHOWS = ("meme", "code", "output", "takeaway")
TEMPLATES = ("classic", "choice", "brain")
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


def check_lesson(lesson: dict, meta: dict, plan: dict | None, run_code: bool = True) -> tuple[list[str], list[str]]:
    """(problems, warnings) for one lesson."""
    bad: list[str] = []
    warn: list[str] = []
    n = lesson.get("n")
    where = f"lesson {n}"
    if plan is not None and not (isinstance(n, int) and 1 <= n <= len(plan["lessons"])):
        return [f'{where}: "n" is not a lesson number of this course.'], warn
    for key in ("title", "hook", "takeaway"):
        if not str(lesson.get(key, "")).strip():
            bad.append(f'{where}: missing "{key}".')
    if len(str(lesson.get("hook", "")).split()) > 10:
        bad.append(f"{where}: hook is over 10 words - it is the on-screen headline.")
    if len(str(lesson.get("takeaway", "")).split()) > 14:
        bad.append(f"{where}: takeaway is over 14 words.")

    meme = lesson.get("meme") or {}
    template = meme.get("template")
    caps = meme.get("captions")
    need = {"classic": (1, 2), "choice": (2, 2), "brain": (4, 4)}.get(template)
    if need is None:
        bad.append(f'{where}: meme.template must be one of {", ".join(TEMPLATES)}.')
    elif not isinstance(caps, list) or not need[0] <= len(caps) <= need[1] or not all(str(c).strip() for c in caps):
        bad.append(f"{where}: the {template} meme needs {need[0] if need[0] == need[1] else f'{need[0]}-{need[1]}'} captions.")
    else:
        for c in caps:
            if len(str(c)) > 60:
                bad.append(f'{where}: meme caption "{c[:20]}..." is over 60 characters.')
    if meme.get("image") and not (MEMES / meme["image"]).exists():
        warn.append(f'{where}: assets/memes/{meme["image"]} is missing - a plain card is used instead.')

    code = lesson.get("code") or {}
    source = str(code.get("source", ""))
    lines = source.splitlines()
    if not source.strip():
        bad.append(f"{where}: code.source is empty.")
    if len(lines) > MAX_CODE_LINES:
        bad.append(f"{where}: code is {len(lines)} lines; the screen fits {MAX_CODE_LINES}.")
    for ln in lines:
        if len(ln.expandtabs(4)) > MAX_CODE_WIDTH:
            bad.append(f"{where}: code line over {MAX_CODE_WIDTH} characters: {ln.strip()[:30]}...")
            break
    if code.get("expect", "ok") not in ("ok", "error"):
        bad.append(f'{where}: code.expect must be "ok" or "error".')

    beats = lesson.get("beats")
    if not isinstance(beats, list) or len(beats) < 3:
        bad.append(f"{where}: beats must be a list of at least 3.")
        return bad, warn
    total = 0
    for j, beat in enumerate(beats, 1):
        say = str(beat.get("say", "")).strip()
        if not say:
            bad.append(f'{where} beat {j}: empty "say".')
        if UNSPEAKABLE.search(say):
            bad.append(f"{where} beat {j}: \"say\" holds code symbols; narration is plain speech: {say[:40]}")
        total += _words(say)
        if beat.get("show") not in SHOWS:
            bad.append(f'{where} beat {j}: "show" must be one of {", ".join(SHOWS)}.')
        focus = beat.get("focus")
        if focus is not None and not (
            isinstance(focus, list) and len(focus) == 2 and 1 <= focus[0] <= focus[1] <= max(len(lines), 1)
        ):
            bad.append(f'{where} beat {j}: "focus" must be [first, last] line numbers inside the code.')
    if beats[0].get("show") != "meme":
        bad.append(f"{where}: the first beat must show the meme (the hook).")
    if beats[-1].get("show") != "takeaway":
        bad.append(f"{where}: the last beat must show the takeaway.")
    if not any(b.get("show") == "code" for b in beats):
        bad.append(f"{where}: at least one beat must show the code.")
    if total > MAX_WORDS:
        bad.append(f"{where}: narration is {total} words; the limit is {MAX_WORDS} (a Short is under 59 seconds).")
    if total < 40:
        warn.append(f"{where}: narration is only {total} words - thin for a lesson.")

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
