# Deep dive

This paper made the front page. Write the line that decides whether the reader opens it.

## `why` — one sentence. Two only if the second earns its place.

Not a summary. The reader has the abstract one click away for detail; what they do not have
is the *intuition*. Give them the shape of the idea in the time it takes to read a line.

Write it the way you would say it to a colleague in the corridor. Plain words, active voice,
the concrete thing the paper does or found. If there is a trick that makes it work, the
trick is the sentence.

Good:

- `Ties the asymmetric unit across the icosahedral orbit, so one denoising pass yields a shell that is consistent by construction rather than symmetrised afterwards.`
- `Their binders fail in exactly the cases the confidence metric was most sure about.`
- `Grafts de novo binders into plant immune receptors, turning a designed interaction into disease resistance in a live plant.`

Bad:

- `This exciting work sheds light on protein assembly.` — says nothing
- `The authors present a method for X. They validate it on Y. It could be useful for Z.` — an abstract, rewritten
- `A novel deep learning framework leveraging state-of-the-art architectures…` — words about words

Rules:

- One sentence. A second only when the first genuinely cannot carry it — a caveat that
  changes whether it is worth reading, or a result that is the actual point.
- Never restate the title.
- No "this paper", no "the authors", no "novel", no "sheds light on", no "paves the way".
- Concrete over general: name the mechanism, the number, or the failure.

## `action` — one of

- `read` — sit down with it; it bears on current work
- `skim` — the abstract and figures are enough
- `track` — nothing to do now, but worth knowing it exists
- `cite` — a result to reference, not a method to adopt

## `touches` — zero to three of the reader's open threads

Listed below. Copy the thread text verbatim. **Do not stretch.** An empty list is a useful
and honest answer; a forced connection costs the reader more than a missing one, because it
teaches them to stop trusting the field.

## Output

Write **only** this JSON object — no prose, no markdown fence:

```
{"id": "...", "why": "...", "action": "read", "touches": ["..."]}
```

Copy `id` back exactly as given.
