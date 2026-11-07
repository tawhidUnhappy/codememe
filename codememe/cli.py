"""codememe command line. The flow:

  new -> (LLM: prompts/curriculum.md) -> import -> lesson-prompt a-b -> (LLM) -> import -> render -> upload-prompt -> (LLM) -> import
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import checks
from .paths import MEMES, PROJECTS, PROMPTS, Project, config, read_json, require, slug, write_json
from .replies import extract_json

BATCH = 10


def parse_range(text: str, last: int) -> list[int]:
    if text == "all":
        return list(range(1, last + 1))
    out: list[int] = []
    for part in text.split(","):
        a, _, b = part.partition("-")
        out += range(int(a), int(b or a) + 1)
    bad = [n for n in out if not 1 <= n <= last]
    if bad:
        raise SystemExit(f"Lessons {bad} are outside 1..{last}.")
    return out


def fill(template: str, values: dict) -> str:
    for k, v in values.items():
        template = template.replace("{{" + k + "}}", str(v))
    return template


def cmd_new(a) -> None:
    name = a.name or slug(f"{a.language}-by-meme")
    project = Project(name)
    if project.exists():
        raise SystemExit(f"Project '{name}' already exists.")
    meta = {"name": name, "language": a.language, "title": a.title or f"{a.language} by Meme",
            "series_title": a.title or f"{a.language} by Meme", "lessons": a.lessons, "audience": a.audience}
    write_json(project.dir / "project.json", meta)
    areas = checks.topic_areas(a.language)
    rule = ("The course MUST include these areas (use these exact ids; you may add more areas):\n" +
            "\n".join(f"- `{x['id']}`: {x['name']}" for x in areas)) if areas else \
        f"List the areas of {a.language} yourself - the complete language: syntax, types, data structures, control flow, " \
        "functions, error handling, modules, the object/ownership/memory model, concurrency, standard library, tooling, idioms."
    prompt = fill((PROMPTS / "curriculum.md").read_text(), {
        "TITLE": meta["title"], "LANGUAGE": a.language, "LESSONS": a.lessons, "AUDIENCE": a.audience,
        "AREAS_RULE": rule})
    (project.dir / "curriculum.prompt.md").write_text(prompt)
    print(f"Created projects/{name}\nGive this prompt to an LLM: {project.dir / 'curriculum.prompt.md'}\n"
          f"Save its reply to a file, then: ./run.sh import {name} reply.json")


def _plan_text(plan: dict, numbers: list[int]) -> str:
    return "\n".join(f"- {x['n']}. {x['title']} | teaches: {'; '.join(x['concepts'])} | meme idea: {x['meme_idea']}"
                     for x in plan["lessons"] if x["n"] in numbers)


def cmd_lesson_prompt(a) -> None:
    project = require(a.name)
    plan = project.curriculum()
    numbers = parse_range(a.range, len(plan["lessons"]))[: a.batch]
    first = numbers[0]
    taught = [x for x in plan["lessons"] if x["n"] < first]
    taught_text = "\n".join(f"- {x['n']}. {x['title']}: {'; '.join(x['concepts'])}" for x in taught[-60:]) or "(nothing yet - this is the start)"
    neighbours = [n for n in range(max(1, first - 2), min(len(plan["lessons"]), numbers[-1] + 2) + 1)]
    memes = sorted(p.name for p in MEMES.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png")) or ["(none - plain cards are used)"]
    from .memegen import catalog, curated
    from .sources import pack_text, research
    known = catalog()
    memegen = "\n".join(f"- `{k}`: {v}" for k, v in curated().items() if not known or k in known)
    prompt = fill((PROMPTS / "lesson.md").read_text(), {
        "MEMEGEN": memegen,
        "RESEARCH": "\n".join(f"- lesson {x['n']} ({x['title']}):\n{pack_text(research(project.meta, x))}"
                              for x in plan["lessons"] if x["n"] in numbers),
        "TITLE": project.meta["title"], "LANGUAGE": project.meta["language"],
        "RANGE": f"{numbers[0]}-{numbers[-1]}" if len(numbers) > 1 else numbers[0],
        "PLAN": _plan_text(plan, neighbours), "TAUGHT": taught_text,
        "TODO": _plan_text(plan, numbers), "MEME_FILES": ", ".join(memes)})
    out = project.dir / "prompts" / f"lessons_{numbers[0]:03d}-{numbers[-1]:03d}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(prompt)
    print(f"Wrote {out}\nGive it to an LLM, save the JSON reply, then: ./run.sh import {a.name} reply.json")


def cmd_upload_prompt(a) -> None:
    project = require(a.name)
    plan = project.curriculum()
    numbers = parse_range(a.range, len(plan["lessons"]))[: a.batch * 2]
    todo = []
    for n in numbers:
        path = project.lesson_path(n)
        if path.exists():
            lesson = read_json(path)
            todo.append(f"- {n}. {lesson['title']} | hook: {lesson['hook']} | takeaway: {lesson['takeaway']}")
    out = project.dir / "prompts" / f"upload_{numbers[0]:03d}-{numbers[-1]:03d}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(fill((PROMPTS / "upload.md").read_text(), {
        "TITLE": project.meta["title"], "LANGUAGE": project.meta["language"], "TODO": "\n".join(todo)}))
    print(f"Wrote {out}")


def cmd_import(a) -> None:
    project = require(a.name)
    text = Path(a.file).read_text(encoding="utf-8") if a.file != "-" else sys.stdin.read()
    reply = extract_json(text)
    kind = reply.get("kind")
    if kind == "curriculum":
        problems = checks.check_curriculum(reply, project.meta)
        if _report(problems, []):
            return
        write_json(project.curriculum_path, reply)
        print(f"Curriculum saved: {len(reply['lessons'])} lessons, {len(reply['areas'])} areas, all covered.")
    elif kind == "lessons":
        plan = project.curriculum() if project.curriculum_path.exists() else None
        if plan is None:
            raise SystemExit("Import the curriculum first.")
        problems, warns = checks.check_lessons(reply, project.meta, plan, run_code=not a.no_run)
        if _report(problems, warns):
            return
        for lesson in reply["lessons"]:
            write_json(project.lesson_path(lesson["n"]), lesson)
        print(f"Saved lessons {[x['n'] for x in reply['lessons']]} - code ran and printed what the lessons say.")
    elif kind == "upload":
        problems = checks.check_upload(reply)
        if _report(problems, []):
            return
        for v in reply["videos"]:
            write_json(project.dir / "upload" / f"{v['n']:03d}.json", v)
        print(f"Saved upload text for {[v['n'] for v in reply['videos']]}.")
    else:
        raise SystemExit('The reply has no "kind" of curriculum / lessons / upload.')


def _report(problems: list[str], warns: list[str]) -> bool:
    for w in warns:
        print("warning:", w)
    if problems:
        print("The reply has problems - paste this back into the same chat and ask for the whole JSON again, fixed:\n")
        for p in problems:
            print("-", p)
        return True
    return False


def cmd_check(a) -> None:
    project = require(a.name)
    plan = project.curriculum()
    bad_total = 0
    for n in project.lessons_done():
        if a.n and n != a.n:
            continue
        problems, warns = checks.check_lesson(read_json(project.lesson_path(n)), project.meta, plan, not a.no_run)
        for w in warns:
            print("warning:", w)
        for p in problems:
            print("-", p)
        bad_total += len(problems)
    print("all lessons good" if not bad_total else f"{bad_total} problem(s)")
    sys.exit(1 if bad_total else 0)


def cmd_render(a) -> None:
    from .render import render_lesson
    project = require(a.name)
    plan = project.curriculum()
    todo = parse_range(a.range, len(plan["lessons"]))
    have = set(project.lessons_done())
    for n in todo:
        if n not in have:
            print(f"lesson {n}: not written yet, skipped")
            continue
        out = render_lesson(project, n, "silent" if a.silent else (a.engine or config()["engine"]), a.fresh)
        print(f"lesson {n}: {out}")


def cmd_upload(a) -> None:
    import datetime as dt

    from . import youtube
    project = require(a.name)
    plan = project.curriculum()
    todo = parse_range(a.range, len(plan["lessons"]))
    cfg = config()
    playlist = None
    slot = dt.datetime.strptime(a.schedule_start, "%Y-%m-%d %H:%M").astimezone() if a.schedule_start else None
    done_today = 0
    for n in todo:
        video = project.video_path(n)
        text_path = project.dir / "upload" / f"{n:03d}.json"
        if not video.exists():
            print(f"lesson {n}: not rendered, skipped")
            continue
        text = read_json(text_path) if text_path.exists() else None
        if text is None:
            lesson = read_json(project.lesson_path(n))
            text = {"n": n, "title": f"{lesson['title']} - {project.meta['title']} (Day {n})", "description": lesson["takeaway"], "tags": []}
        if text.get("youtube_id"):
            print(f"lesson {n}: already uploaded ({text['youtube_id']})")
            continue
        text["description"] = text["description"].rstrip() + f"\n\n#Shorts #{project.meta['language'].replace('+', 'p')}"
        publish_at = None
        if slot:
            publish_at = slot.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            done_today += 1
            if done_today >= a.per_day:
                slot, done_today = slot + dt.timedelta(days=1), 0
        if a.dry_run:
            print(f"lesson {n}: would upload {video.name} as {text['title']!r} ({publish_at or a.privacy})")
            continue
        vid = youtube.upload_video(video, text, a.privacy, publish_at)
        if cfg.get("playlist"):
            playlist = playlist or youtube.playlist_id(cfg["playlist"])
            youtube.add_to_playlist(playlist, vid)
        text["youtube_id"] = vid
        write_json(text_path, text)
        print(f"lesson {n}: https://youtube.com/shorts/{vid} ({publish_at or a.privacy})")


def cmd_research(a) -> None:
    from .sources import pack_text, research
    project = require(a.name)
    plan = project.curriculum()
    for n in parse_range(a.range, len(plan["lessons"])):
        x = plan["lessons"][n - 1]
        print(f"lesson {n}: {x['title']}\n{pack_text(research(project.meta, x))}\n")


def cmd_music_fetch(a) -> None:
    from .sources import music_fetch
    path = music_fetch(a.query)
    if a.use:
        import json
        cfg_path = Path(__file__).resolve().parent.parent / "config.json"
        cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}
        cfg["music"] = str(path)
        cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")
        print("config.json: music set")


def cmd_youtube_login(a) -> None:
    from . import youtube
    youtube.login()


def cmd_public_check(a) -> None:
    from .publiccheck import scan
    problems = scan()
    for p in problems:
        print("-", p)
    print("public-check: clean" if not problems else f"public-check: {len(problems)} problem(s) - do not commit/push")
    sys.exit(1 if problems else 0)


def cmd_status(a) -> None:
    project = require(a.name)
    meta = project.meta
    plan = project.curriculum() if project.curriculum_path.exists() else None
    done = set(project.lessons_done())
    rendered = {n for n in done if project.video_path(n).exists()}
    print(f"{meta['title']} ({meta['language']}) - curriculum: {'ready, ' + str(len(plan['lessons'])) + ' lessons' if plan else 'not imported'}")
    if plan:
        total = len(plan["lessons"])
        gaps = [n for n in range(1, total + 1) if n not in done]
        print(f"lessons written {len(done)}/{total} | videos rendered {len(rendered)}/{total}")
        if gaps:
            print(f"next to write: {gaps[0]}-{min(gaps[0] + BATCH - 1, total)}  ->  ./run.sh lesson-prompt {a.name} {gaps[0]}-{min(gaps[0] + BATCH - 1, total)}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="codememe", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new", help="start a course and write the curriculum prompt")
    p.add_argument("language", help="python, rust, cpp, javascript, go, ...")
    p.add_argument("--name"), p.add_argument("--title", help='e.g. "100 Days of Python by Meme"')
    p.add_argument("--lessons", type=int, default=100)
    p.add_argument("--audience", default="complete beginners, ages 15+, who watch on a phone")
    p.set_defaults(fn=cmd_new)
    for name, fn, help_ in (("lesson-prompt", cmd_lesson_prompt, "prompt for the next lessons"),
                            ("upload-prompt", cmd_upload_prompt, "prompt for titles/descriptions")):
        p = sub.add_parser(name, help=help_)
        p.add_argument("name"), p.add_argument("range", help="3, 1-10, 5,8 or all")
        p.add_argument("--batch", type=int, default=BATCH)
        p.set_defaults(fn=fn)
    p = sub.add_parser("import", help="check and save an LLM reply (curriculum / lessons / upload)")
    p.add_argument("name"), p.add_argument("file", help="JSON file, or - for stdin")
    p.add_argument("--no-run", action="store_true", help="skip running the lesson code")
    p.set_defaults(fn=cmd_import)
    p = sub.add_parser("check", help="re-check saved lessons, running their code")
    p.add_argument("name"), p.add_argument("n", nargs="?", type=int)
    p.add_argument("--no-run", action="store_true")
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser("render", help="make the videos")
    p.add_argument("name"), p.add_argument("range", help="3, 1-10 or all")
    p.add_argument("--silent", action="store_true", help="no voice (layout test)")
    p.add_argument("--engine", choices=("kokoro", "drama3"), help="override config.json engine")
    p.add_argument("--fresh", action="store_true", help="re-render existing videos")
    p.set_defaults(fn=cmd_render)
    sub.add_parser("youtube-login", help="sign in to YouTube once (opens the browser)").set_defaults(fn=cmd_youtube_login)
    p = sub.add_parser("research", help="pull reference material (docs, Wikipedia, Stack Overflow) for lessons")
    p.add_argument("name"), p.add_argument("range")
    p.set_defaults(fn=cmd_research)
    p = sub.add_parser("music-fetch", help="download a CC0 background track from Openverse")
    p.add_argument("query"), p.add_argument("--use", action="store_true", help="set it as the music in config.json")
    p.set_defaults(fn=cmd_music_fetch)
    sub.add_parser("public-check", help="fail if a tracked/staged file holds a key, token or personal path").set_defaults(fn=cmd_public_check)
    p = sub.add_parser("upload", help="upload rendered videos to YouTube (uses upload text if imported)")
    p.add_argument("name"), p.add_argument("range", help="3, 1-10 or all")
    p.add_argument("--privacy", choices=("private", "unlisted", "public"), default="private")
    p.add_argument("--schedule-start", help='schedule instead: first publish time, local, "YYYY-MM-DD HH:MM"')
    p.add_argument("--per-day", type=int, default=1, help="with --schedule-start: videos per day")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_upload)
    p = sub.add_parser("status")
    p.add_argument("name")
    p.set_defaults(fn=cmd_status)
    p = sub.add_parser("list")
    p.set_defaults(fn=lambda a: print("\n".join(sorted(x.name for x in PROJECTS.glob("*") if x.is_dir())) or "no projects"))
    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
