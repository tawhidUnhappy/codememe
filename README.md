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
4. **Render** - a real Short, not slides: 1080x1920, every beat cut into ~2 s **full-screen scenes** (checked: one scene per
   ~7 spoken words) rendered at 30 fps - real meme templates, **GIF / video clips** (Giphy or Pexels free key, below), animated
   **Windows / macOS / Linux terminals** that type the real commands, a code editor that types the code, big kinetic text on
   moving gradients, a takeaway card; spoken captions, Day n/N progress, Kokoro or Drama 3 narration, optional music.
5. **Upload** - `upload-prompt` -> titles, descriptions, tags and a pinned comment per video.

## Real screenshots and pictures, synced to the voice

Every scene of a lesson owns the words spoken while it is on screen (`say`, 3-10 words), and the video is timed from
**word-level alignment** of the narration (faster-whisper, `whisper_python` / `whisper_model_dir` in `config.json`): a
picture appears exactly when its words are spoken, and captions follow the real word times. `image` scenes grab
**real web pages with headless Chrome** (python.org, docs, the Microsoft Store, Stack Overflow ...) at phone-readable size,
with an optional spotlight (`highlight`) on the element being talked about, or openly licensed pictures from Wikimedia Commons /
Openverse (credits are added to the upload description). Live facts (e.g. the latest Python version) are fetched into every
lesson prompt, so output like `Python 3.15.2` is current.

## GIFs and video clips (free keys, optional but recommended)

Add either or both to `config.json` (gitignored): `"giphy_key"` (free at developers.giphy.com) for reaction GIFs, `"pexels_key"`
(free at pexels.com/api) for real stock video. A scene `{"type": "clip", "query": "facepalm", "text": "..."}` is cached in
`global/clips/`; with no key, or no match, it falls back to a text scene (Wikimedia Commons video only when a scene asks for
`"source": "wikimedia"`).

## Material from free servers (no keys)

Lessons are written from sources, not memory. `./run.sh research <name> 1-10` (and every `lesson-prompt`) pulls,
cached in `global/sources/`: the matching paragraphs of the **official docs** (mapped per area in
`topics/<language>.json`), the **Wikipedia** summary, and the **real Stack Overflow questions** beginners ask about
the concept (Stack Exchange API) - what people get stuck on is the best meme. **Memes** come from memegen (below),
**music** from Openverse: `./run.sh music-fetch "lofi hip hop" --use` downloads a CC0/public-domain track (no
attribution needed) and sets it in `config.json`. Everything fails soft when offline.

## Memes

Free, no key, no account: codememe uses the template data of the open-source
[memegen](https://github.com/jacebrowning/memegen) project (MIT, ~200 templates). The LLM picks a template `id`
and writes one caption per slot (the checker verifies the id exists and the slot count); the lesson prompt lists
22 hand-checked templates with what each slot means. The captions are drawn locally from the template's own
background picture and text-box positions, so there is no watermark and, once a template is downloaded
(`global/memegen/`, gitignored), it works offline. Offline and not downloaded yet -> a built-in layout is used.
The template pictures belong to their original owners (meme use, as on any meme site).

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
