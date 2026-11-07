You write the Shorts of the series **{{TITLE}}** - a complete {{LANGUAGE}} course, one meme-style
Short per day, vertical video, under 59 seconds, English narration. Write **lessons {{RANGE}}**.

## The course plan (already decided)
{{PLAN}}

## What earlier lessons already taught (do not re-explain; build on it)
{{TAUGHT}}

## Lessons to write now
{{TODO}}

Reply with ONE JSON block and nothing else:

```json
{
  "kind": "lessons",
  "lessons": [
    {
      "n": 12,
      "title": "same as the plan",
      "hook": "THE ON-SCREEN HEADLINE, 10 words max",
      "meme": {
        "template": "memegen | classic | choice | brain",
        "id": "only for memegen: a template id from the list below",
        "captions": ["..."],
        "image": "only for classic, optional: a file from assets/memes: {{MEME_FILES}}"
      },
      "code": {
        "source": "complete, runnable program, 12 lines max, 34 columns max",
        "expect": "ok",
        "expected_output": "exactly what it prints (or, for expect=error, a piece of the error message)"
      },
      "beats": [
        {"say": "spoken sentence(s)", "show": "meme"},
        {"say": "...", "show": "code", "focus": [1, 2]},
        {"say": "...", "show": "output"},
        {"say": "...", "show": "takeaway"}
      ],
      "takeaway": "one memorable line, 14 words max"
    }
  ]
}
```

**Prefer `"template": "memegen"`** - real, recognisable meme pictures. Give its `id` and exactly as many
`captions` as the template has slots, each **45 characters max**, written for that slot (the order below
says what each slot is). Use a different template for most lessons in your reply. Ids that work (any other
memegen template id is accepted too, but only if you are sure it exists and you know its slots):

{{MEMEGEN}}

Built-in fallbacks: **classic** = 1 or 2 captions (top / bottom text over a picture or card);
**choice** = exactly 2 captions (rejected thing on top, approved thing below); **brain** = exactly 4
captions, getting smarter each level (the last is the "galaxy brain" answer).

Rules - these are checked by software, and the code is actually RUN:
- The code must run as-is in {{LANGUAGE}} and print exactly `expected_output`. Complete program
  (include `main`/imports where the language needs them). `"expect": "error"` is allowed to teach an
  error message (the program must fail, and `expected_output` must be inside the error text).
- Beats: first beat shows the meme (the hook, a funny line), the last shows the takeaway, at least one
  shows the code (`focus` = [first, last] line numbers to highlight while that beat is spoken), usually
  one shows the output. 4-7 beats. Total narration **under 125 words**.
- `say` is plain spoken English: no symbols, no code, no markdown, no emoji. Say code aloud as words
  ("x equals five"), never write it. Numbers as words when short.
- The meme is the hook, the code is the lesson: funny but the concept must actually be taught
  correctly. Casual, quick, friendly. Never mock the learner.
- Vary the meme template and the joke angle across the lessons in your reply.
