---
name: codememe-ops
description: How the codememe codebase works - load before changing it. Pipeline (curriculum -> lessons -> checked code -> vertical Short render -> upload text), the three LLM JSON contracts, code map, ground rules and how to test without touching a real course.
---

# codememe: working on the code

Turns a programming language into a course of meme Shorts. The LLM writes (curriculum, lessons, upload
text) as one JSON block each; codememe checks and renders. Claude, working in this repo, is the coder and
may play the LLM's part by writing the same JSON.

Entry: `./run.sh <command>` (`codememe/cli.py`). Lint: `.venv/bin/python -m ruff check codememe`.

## Code map
- `paths.py` roots, config, `Project` (projects/<name>/{project.json,curriculum.json,lessons/NNN/lesson.json,out/NNN.mp4,upload/})
- `checks.py` the contracts - **moves together with `prompts/*.md`** (curriculum.md, lesson.md, upload.md)
- `runcheck.py` runs lesson code per language; missing toolchain = warning
- `memegen.py` real meme templates (catalog from api.memegen.link, background + text boxes from the memegen repo, drawn locally = no watermark; cache global/memegen/); `assets/memegen_curated.json` = slot hints shown to the LLM (verify a new entry by rendering it and LOOKING). The public memegen server always stamps a watermark - never crop it; render locally instead.
- `memecards.py` meme layouts (built-in fallbacks), `frames.py` every still (header, code card via Pygments, output, takeaway, captions)
- `tts.py` engines: kokoro (`scripts/kokoro_worker.py`), drama3 (`scripts/drama3_worker.py` = remanga's worker + `voice_gguf`, the user's own voice file, one sentence per request), `silent`; takes cached by hash
- `render.py` takes -> caption-chunk stills -> ffmpeg concat -> mp4 (hard stop over `max_seconds`)
- `topics/<language>.json` area checklists that make "complete course" enforceable

- `youtube.py` stdlib OAuth (loopback+PKCE) + resumable upload; `publiccheck.py` secret/personal scan (pre-commit hook)

## Ground rules
- **Public repo**: run `./run.sh public-check` before every commit/push; never print/paste client_secret or tokens; commits use the GitHub noreply identity.
- Code only in git. Courses, config.json, meme pictures, renders are local and gitignored; no personal paths in code.
- A bad lesson means fixing the prompt/checker for every lesson, not hand-editing that lesson's JSON.
- Verify by running: `./run.sh render <zz-test> all --silent` and LOOK at frames; real voice via config.json.
- Test in a throwaway project named `zz-*` (delete it afterwards with Python `shutil`, not `rm -r`).
- Meme templates: only pictures the user supplies in `assets/memes/`; never download/commit copyrighted templates.
- Limits (160 chars wide code is unreadable on a phone): 12 lines, 34 columns, 125 words, 59 s - change them in `checks.py` AND the prompt together.
