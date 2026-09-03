# Deep dive

This paper made the front page. Write the three sentences that decide whether the reader
opens it.

## What to write

**`why` — exactly three sentences.**

1. What the paper actually does, mechanistically. Not what it claims; what it does.
2. Why it is not the previous thing. Name what it replaces or improves on.
3. What changes for someone designing self-assembling proteins — a decision, a method they
   could adopt, an assumption now in doubt. If the honest answer is "nothing directly",
   write that.

Write plainly. No "this exciting work", no "sheds light on", no restating the title.
Assume a reader who knows the field and is deciding in five seconds.

**`action` — one of:**

- `read` — sit down with it; it bears on current work
- `skim` — the abstract and figures are enough
- `track` — nothing to do now, but worth knowing it exists
- `cite` — a result to reference, not a method to adopt

**`touches` — zero to three of the reader's open threads, listed below, that this paper
genuinely bears on.** Copy the thread text verbatim. **Do not stretch.** An empty list is a
useful and honest answer; a forced connection costs the reader more than a missing one,
because it teaches them to stop trusting this field.

## Output

Write **only** this JSON object — no prose, no markdown fence:

```
{"id": "...", "why": "...", "action": "read", "touches": ["..."]}
```

Copy `id` back exactly as given.
