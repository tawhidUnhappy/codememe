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
      {"say": "plain spoken sentence(s)", "caption": "optional: on-screen text when it differs from speech",
       "scenes": [ {"type": "meme", "id": "drake", "captions": ["...", "..."]},
                   {"type": "text", "text": "BIG WORDS"} ]},
      "... 5-8 beats ..."
    ],
    "takeaway": "one memorable line, 14 words max"
  }]
}
```

## Scenes - the picture changes about every 2 seconds, always full screen
Every beat has `scenes`: **one scene for every ~7 spoken words** (checked). They play in order across the
beat. Mix them - never three of the same kind in a row:
- `{"type": "meme", "id": ..., "captions": [...]}` - a real meme template, full-screen. Exactly as many
  captions as slots, each 45 characters max, written for that slot. Different template for most scenes.
  Ids that work (the order says what each slot is):
{{MEMEGEN}}
- `{"type": "clip", "query": "what to search a GIF or stock video for", "text": "OVERLAY TEXT"}` - a
  full-screen reaction GIF / video clip (text is also shown if none is found). Queries are 1-3 plain words
  ("facepalm", "typing fast", "mind blown", "loading").
- `{"type": "terminal", "os": "windows|mac|linux", "lines": [{"cmd": "..."}, {"out": "..."}]}` - a real
  terminal; the commands are typed live and the output appears. Use real, correct commands and output; one
  row = one line, 40 columns max, 9 rows max.
- `{"type": "code", "focus": [first, last], "typing": true}` - the lesson's `code` in an editor, typed live
  (`typing`) or whole with the `focus` lines lit.
- `{"type": "text", "text": "BIG WORDS"}` - kinetic text on a moving colour gradient, 60 characters max.
- The last scene of the last beat is `{"type": "takeaway"}`.

## Rules (checked by software; the code is actually RUN)
- The code must run as-is and print exactly `expected_output` (`"expect": "error"` may teach an error: it
  must fail, and `expected_output` must be inside the error text).
- Narration is **under 125 words in total**, plain spoken English: no symbols, no code, no markdown, no
  emoji. Say code as words ("python hello dot p y"); use `caption` for what should be *shown* ("python hello.py").
- Casual, quick, friendly, correct. Open with a hook that is funny; the concept must be taught properly.
  Never mock the learner. Vary the joke angle across the lessons in your reply.
