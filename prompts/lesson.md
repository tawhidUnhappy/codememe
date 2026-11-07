You write the Shorts of the series **{{TITLE}}** - a complete {{LANGUAGE}} course, one meme-style
Short per day: vertical video, under 59 seconds, English narration, made to look like a real, fast YouTube
Short - **not slides**. Write **lessons {{RANGE}}**.

## The course plan (already decided)
{{PLAN}}

## What earlier lessons already taught (do not re-explain; build on it)
{{TAUGHT}}

## Reference material pulled from free sources (official docs, Wikipedia, real Stack Overflow questions)
Use it for correctness and correct terminology, and let the "real beginner question" lines guide what is
confusing and therefore funny. The matching is automatic and sometimes loose: ignore anything off-topic. Do not copy it.
{{RESEARCH}}

## Lessons to write now
{{TODO}}

## Accuracy is the first rule
A beginner must be able to follow your lesson on their own computer and have it work. So:
- State only things you are sure are current and true. Check each fact against the official docs (list the
  pages in `sources`, official docs first). If you are not sure, leave it out.
- Be complete for a beginner: what to click or type, **which command on which operating system** (for
  {{LANGUAGE}}, say where Windows / macOS / Linux differ), where the file must be, what they will see.
- Never give outdated advice. When a tool or installer changed recently, say what is current.
- A reviewer will check every lesson against its sources.

## Live facts (fetched just now - use them, do not guess versions)
{{FACTS}}

## Reply format - ONE JSON block and nothing else

```json
{
  "kind": "lessons",
  "lessons": [{
    "n": 12,
    "title": "same as the plan",
    "hook": "THE HEADLINE, 10 words max",
    "sources": ["https://official-docs-page", "..."],
    "code": {"source": "complete runnable program, 12 lines, 34 columns max", "expect": "ok",
             "expected_output": "exactly what it prints (for expect=error: a piece of the error text)", "filename": "hello.py"},
    "beats": [
      {"scenes": [
        {"say": "3 to 10 spoken words", "type": "image", "source": "screenshot", "url": "https://...", "highlight": [0.05, 0.2, 0.6, 0.23]},
        {"say": "the next few words", "type": "meme", "id": "drake", "captions": ["...", "..."]}
      ]},
      "... 5-9 beats ..."
    ],
    "takeaway": "one memorable line, 14 words max"
  }]
}
```

## The picture is synchronised with the voice - every scene owns its words
A beat is one spoken passage (a sentence or two). It is made of **scenes**, and each scene has its own
`say`: **3-10 spoken words** (about 2 seconds). The beat's narration is simply all its scenes' `say`
joined in order, and each scene is on screen exactly while *its* words are spoken - so a picture must show
what its words say (say "click Install" over the Install button, not over a joke). Always full screen,
always changing.

Scene types (never three of the same kind in a row; at least 3 real-media scenes per lesson):
- `{"type": "image", "source": "screenshot", "url": "https://...", "highlight": [x0, y0, x1, y1]}` - a **real
  screenshot of a real web page** (official download page, docs, store page, Stack Overflow question), laid
  out 720 px wide and scrolled/zoomed; `highlight` (optional) spotlights the element being talked about, as
  fractions 0-1 of the page image (from its top-left), page image = first ~3200 px of the page. `"scroll": 0-1`
  moves further down the page. **Prefer this** for anything that exists on a website.
- `{"type": "image", "source": "commons" | "openverse", "query": "..."}` - an openly licensed picture
  (Wikimedia Commons: software screenshots, logos, diagrams; Openverse: photos). Credits are added to the
  video description automatically.
- `{"type": "meme", "id": ..., "captions": [...]}` - a real meme template, full-screen. Exactly as many
  captions as slots, each 45 characters max. Ids (the order says what each slot is):
{{MEMEGEN}}
- `{"type": "clip", "query": "plain words", "text": "OVERLAY"}` - a GIF / stock video clip (needs a Giphy/Pexels
  key; otherwise a text scene is shown).
- `{"type": "terminal", "os": "windows|mac|linux", "lines": [{"cmd": "..."}, {"out": "..."}]}` - a real
  terminal, commands typed live. Rows may carry `"prompt"` (e.g. after `cd`) and `"done": true` (already typed,
  for continuing the same session across scenes). 40 columns max, 9 rows max.
- `{"type": "code", "focus": [first, last], "typing": true}` - the lesson's `code` in an editor.
- `{"type": "text", "text": "BIG WORDS"}` - kinetic text on a moving gradient (use sparingly).
- the last scene of the last beat: `{"say": "...", "type": "takeaway"}`.
- any scene may carry `"caption"`: on-screen text when it should differ from the speech.

## Rules (checked by software; the code is actually RUN)
- The code must run as-is and print exactly `expected_output` (`"expect": "error"` may teach an error: it
  must fail, and `expected_output` must be inside the error text).
- Narration is **under 125 words in total**, plain spoken English: no symbols, no code, no markdown, no
  emoji. Say code as words ("python hello dot p y") and use `caption` to *show* it ("python hello.py").
- Casual, quick, friendly, correct. Open with a funny hook; the concept must be taught properly. Never mock
  the learner. Vary the joke angle across the lessons in your reply.
