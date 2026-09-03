# Blindspot

Every paper below was **rejected** by the radar's filter. That is the point. The filter
gets steadily better at finding what the reader already knows they want, and
correspondingly worse at everything else. Your job is to find the one thing it should not
have thrown away.

## The question

Do **not** ask "is this relevant?" — the filter already answered that, and you would just
be re-deriving a sixth-best hit.

Ask instead:

> Does this contain a **mechanism, formalism, or empirical result** that would change how
> someone designing self-assembling proteins thinks — even though the paper is not about
> protein design at all?

Things that qualify: a statistical-mechanics result about nucleation or kinetic traps; a
tiling or group-theoretic construction; an optimisation formalism that maps onto sequence
or backbone search; a measurement technique from another field; a failure mode observed in
some other self-assembling system.

Things that do not: a protein paper the filter merely underrated; anything whose relevance
runs through "this is also machine learning"; an analogy with no mechanism behind it.

Soft-matter self-assembly physics is a standing blindspot for anyone working on capsids.
So is anything treating assembly as a kinetic rather than a thermodynamic problem.

## Pick exactly one

One, not two. Two makes this a section people skip.

- `connection` — two sentences naming the *specific* current problem it bears on and the
  *specific* mechanism that transfers. A vague connection is worse than no pick.
- `confidence` — `low`, `medium` or `high`. Be honest. `low` is a perfectly good answer and
  far more useful than false confidence: the reader is calibrating on this over time, and
  one overstated pick costs more than several modest ones.

If nothing here genuinely qualifies, return `"id": null`. An empty week is a real signal
about the filter, not a failure to be papered over.

## Output

Write **only** this JSON object — no prose, no markdown fence:

```
{"id": "...", "why": "...", "connection": "...", "confidence": "medium", "action": "track"}
```
