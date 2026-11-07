# codememe

Learn a programming language **by meme**: a whole course as a series of vertical Shorts - "100 Days of
Python by Meme", "Learn Rust by Meme", "Complete C++ in Shorts" - with an LLM (Gemini, ChatGPT, Claude, ...)
as the teacher and writer, and codememe doing everything else on your machine.

It is the sibling of [remanga](../remanga): same shape - the LLM makes the judgment calls and replies
with **one JSON block**, codememe checks it before saving anything, then renders.

1. **Plan the course** - `new` writes a prompt; the LLM returns the whole curriculum: N lessons in
   teaching order, each with its concepts and meme idea. Python, Rust and C++ ship with a checklist of
   areas (`topics/*.json`: ownership, templates, decorators, concurrency, ...) that the plan **must cover
   completely** - the checker rejects a plan that skips one. Any other language gets an LLM-made area
   list, and the same "every area covered" rule.
2. **Write the Shorts** - `lesson-prompt` builds a prompt for the next 10 lessons (it includes what
   earlier lessons taught, so nothing is re-explained). The reply: per lesson a hook, a meme, a short
   runnable program, narration beats and a takeaway.
3. **Check** - `import` verifies the reply, and **runs every lesson's code** (Python, C/C++, Rust,
   JavaScript, Go - whichever toolchain is installed) and compares the output with what the lesson says.
   A meme never teaches code that does not work. Wrong reply -> a fix list to paste back to the LLM.
4. **Render** - 1080x1920 (configurable), under 59 s: header with *Day n/N* and a progress bar, the meme
   (built-in `choice`, `brain` and `classic` layouts, or your own template pictures in `assets/memes/`),
   a syntax-highlighted code card with the lines being explained lit up, the program's output, the
   takeaway, big captions, and Kokoro-82M narration (optional background music, ducked).
5. **Upload** - `upload-prompt` -> titles, descriptions, tags and a pinned comment per video.

## Use it

```bash
./run.sh new python --title "100 Days of Python by Meme" --lessons 100
# give projects/<name>/curriculum.prompt.md to an LLM, save its JSON reply as reply.json
./run.sh import <name> reply.json
./run.sh lesson-prompt <name> 1-10        # -> LLM -> reply
./run.sh import <name> reply.json         # checks it AND runs the code
./run.sh render <name> 1-10               # or: all ; add --silent to test the layout without a voice
./run.sh status <name>                    # what is written / rendered, and the next command
./run.sh check <name>                     # re-run every saved lesson's code
```

`./run.sh` creates its own `.venv` (needs [uv](https://docs.astral.sh/uv/) and ffmpeg). Voice: copy
`config.example.json` to `config.json` and point `kokoro_python` / `kokoro_model_dir` at a Kokoro-82M
install; or set `"engine": "drama3"` to narrate with Fish Audio Drama 3 in a voice file of your own
(`speech_exe`, `drama3_model`, `voice_gguf` - make the file once from a recording of **your own voice**:
`speech voice <model.gguf> rec.wav --transcript "what it says" my.voice.gguf`). Kokoro: (remanga's `.tools/venv-kokoro` and `checkpoints/kokoro_82m` work as they are). `config.json`,
`projects/` and your meme pictures are gitignored; the repo is code only.

## Adding a language

Run `new <language>` - it works for any name. To make completeness **enforced**, add
`topics/<language>.json` (`{"language": ..., "areas": [{"id", "name"}]}`); to run its code, add a branch to
`codememe/runcheck.py`.

## YouTube upload

1. In Google Cloud: create a project, enable **YouTube Data API v3**, set up the OAuth consent screen
   (add your channel's Google account as a test user, then publish the app), create an **OAuth client ID
   of type Desktop app** and download its JSON.
2. Save it as `global/youtube/client_secret.json` (gitignored), then `./run.sh youtube-login` once - it
   opens the browser; the token is kept in `global/youtube/token.json` (gitignored).
3. `./run.sh upload <name> 1-6 --privacy private` or schedule: `--schedule-start "2026-11-09 18:00" --per-day 1`.
   Uses the title/description/tags from `upload-prompt` when imported; adds `#Shorts`; puts each video in
   the playlist named by `"playlist"` in `config.json`; records the video id, so a re-run skips finished ones.

YouTube limits: the default quota fits about 6 uploads a day (a quota stop is clean - run it again the next
day), and an API project that Google has not audited uploads private only; flip them public in Studio or
apply for the YouTube API compliance audit.

## The repo is public

Secrets and personal data never go in git: `config.json`, `global/` (voice, OAuth client and token), `projects/`
and `assets/memes/*` are gitignored, and `./run.sh public-check` scans every tracked/staged file for keys,
tokens, e-mails and home paths. A pre-commit hook runs it (re-create it after a fresh clone:
`printf '#!/usr/bin/env bash\n./run.sh public-check\n' > .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit`).

See `.claude/skills/codememe-ops/SKILL.md` for the code map and what has bitten before.
