# Weekly research radar

Run the literature radar for the current ISO week and publish it.

You are acting as the **model** in this pipeline, not just the operator. The Python code
does every deterministic stage — fetching, dedupe, filtering, ranking, rendering. Your job
is the judgement in the middle: reading abstracts and writing structured answers to files.

Work in the repository root. Everything below is one pass; do not stop halfway.

---

## 1. Collect

```bash
uv sync --frozen
WEEK=$(uv run radar current-week)
uv run radar collect --week "$WEEK"
```

Read the funnel it prints. If a source reports `FAIL` or falls under its expected minimum,
note it — it will already be on the front page banner, but say so in your final summary too.

If `collect` fails outright, **stop and report it**. Do not publish a partial week: a
silently incomplete digest is worse than a missing one.

Note the branch. This repository publishes from `radar-rebuild`, not `main`; `git status`
should already show it after checkout. If you are on a different branch, switch before
committing anything.

## 2. Triage

`work/$WEEK/triage/` now holds numbered batch files, each with ~25 abstracts and complete
instructions.

For each `batch_NN.md`: read it, follow its instructions exactly, and write the JSON array
to `work/$WEEK/triage_out/batch_NN.json`.

**Work through them in numerical order, and start with `batch_00.md`.** The prefilter sorts
the shortlist by signal before batching, so `batch_00` holds the watchlist authors and the
strongest keyword matches and the numbering decays from there. If you run out of room, the
papers you did read are the ones that mattered most.

**Handle one batch at a time and do not carry earlier ones.** Each batch file is
self-contained and its answer goes straight to disk, so nothing is lost when earlier
context is compacted away — that is the whole reason this stage is a file contract rather
than one long conversation. There can be thirty or more batches; do not try to hold them
all at once, and do not summarise several batches into one answer file.

- Every paper in a batch gets a row. A missing row silently downgrades that paper to
  keyword scoring.
- Copy each `id` back **exactly** — that string is the join key.
- Write strict JSON. No markdown fence, no commentary, no trailing commas.
- Work through the batches steadily. Do not skip any, and do not summarise several batches
  into one file.

Also answer the blindspot prompt at `work/$WEEK/blindspot.md`, writing
`work/$WEEK/blindspot_out.json`. Read that prompt carefully: it asks a *different* question
from triage, and answering it like triage defeats its purpose. `"id": null` is a legitimate
answer when nothing in the sample genuinely qualifies.

## 3. Select

```bash
uv run radar select --week "$WEEK"
```

This applies your triage and writes ~15 deep-dive prompts to `work/$WEEK/deep/`.

## 4. Deep dive

For each `work/$WEEK/deep/<name>.md`: read it and write `work/$WEEK/deep_out/<name>.json`
(same stem, `.json` instead of `.md`).

The `why` field is the single most valuable text this system produces — it is what the
reader actually reads, and it decides whether they open the paper. Three sentences, plainly
written, no throat-clearing. Follow the prompt's structure exactly.

On `touches`: only list an open thread the paper genuinely bears on. An empty list is the
right answer more often than not. A forced connection costs the reader more than a missing
one, because it teaches them to stop trusting the field.

## 5. Assemble and publish

```bash
uv run radar assemble --week "$WEEK"
uv run pytest -q
```

Then commit and push:

```bash
git add -A
git commit -m "radar: $WEEK"
git push
```

If `gh` is available, also open the weekly issue with the digest body, so emoji reactions
on it can be harvested as the feedback signal:

```bash
gh issue create --title "radar: $WEEK" --body-file "digests/$WEEK.md" --label radar
```

## 6. Report

Summarise in a few lines: the funnel numbers, the top pick and why, the blindspot pick and
its confidence, and anything degraded. If any source failed, say so plainly rather than
burying it.

---

## Rules

- **Never fabricate a paper, an id, or a `why`.** Everything you write must come from the
  abstract in front of you. This system's only value is that its output is trustworthy.
- **Never edit `config/` or `radar/` during a run.** If the filter looks wrong, say so in
  the report and leave it; tuning is a deliberate, reviewed act via `radar eval`, not a
  side effect of a cron job.
- If you run out of budget or time partway through triage, **still run `select` and
  `assemble`**. Papers without a triage row degrade to keyword scoring, the digest says so,
  and a partial week beats no week. Report how far you got.
- Do not delete `data/raw/` — it is what makes the radar tunable after the fact.
