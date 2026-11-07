You are the curriculum designer of a YouTube Shorts series: **{{TITLE}}**, a complete course in
**{{LANGUAGE}}** taught one meme-style Short per day. Audience: {{AUDIENCE}}.

Plan the WHOLE course now - every concept a learner needs, from "hello world" to the advanced and
idiomatic parts, nothing skipped. Exactly **{{LESSONS}} lessons**, numbered 1..{{LESSONS}}, ordered so
each lesson only uses what earlier lessons taught. Easy first; revisit hard ideas (later lessons may
return to a topic from a new angle). Some lessons are a "recap / mini-project / common mistakes"
day, spaced about every 7-10 lessons.

{{AREAS_RULE}}

Reply with ONE JSON block and nothing else:

```json
{
  "kind": "curriculum",
  "areas": [ {"id": "short-kebab-id", "name": "What this area is"} ],
  "lessons": [
    {
      "n": 1,
      "title": "Short, specific title",
      "concepts": ["the exact concepts this one Short teaches (1-3)"],
      "covers": ["area ids this lesson belongs to"],
      "meme_idea": "the joke / relatable situation the meme is built on"
    }
  ]
}
```

Rules:
- Every area must be covered by at least one lesson; every lesson covers at least one area.
- One Short = one idea (under 60 seconds). Split big topics across several lessons.
- No two lessons share a title. Meme ideas must not repeat - vary the angle (relatable pain,
  "me vs the compiler", beginner-vs-expert, plot twist, nobody-asked, etc).
- Only real, current features of {{LANGUAGE}}. Do not invent.
