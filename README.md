# olivernagl.github.io — research radar

A weekly automated literature radar for de novo protein design, self-assembling protein
nanomaterials, and the machine learning behind them. It fetches a few thousand new records
a week, filters them down, has a model read what survives, and publishes a front page you
can read in three minutes.

The site *is* the front end. Pipeline and site live in one repository so the pages can
`fetch` the data directly, same-origin, with no token and no sync job to go stale.

**Live:** <https://olivernagl.github.io>

---

## Surfaces

| Page | What it is for |
|---|---|
| `index.html` | This week: five picks, one blindspot, "now published", collapsed backlog. **Rendered statically by Python** — it needs no JavaScript and paints on first byte. |
| `archive.html` | Full-archive search. The one thing the markdown digests genuinely cannot do. |
| `tuning.html` | Gold-set verdicts, priced suggestions, and live re-ranking with the weight sliders. |
| `projects.html` | A few things I have built. |
| `digests/*.md` | The permanent, greppable archive that survives the tooling. |
| `feed.xml` | RSS. |

`data/issues/<week>.json` is the single source of truth. The markdown, the site and the feed
are all pure functions of it, so a rendering bug is never a data-loss event and re-rendering
the whole archive is `radar render`.

## How a week runs

The deterministic stages are plain Python you can debug. The judgement in the middle
arrives as *files*, which is what lets a scheduled Claude Code routine act as the model
with no API key anywhere in this repository:

```
radar collect    fetch → dedupe → prefilter → data/raw/<week>.jsonl.gz
                 → work/<week>/triage/batch_NN.md          (prompts)
   ⟶  the routine reads each prompt and writes work/<week>/triage_out/batch_NN.json
radar select     apply triage → work/<week>/deep/*.md      (prompts)
   ⟶  the routine answers into work/<week>/deep_out/*.json
radar assemble   validate, rank, write data/ + digests/ + the site
```

Because the boundary is files rather than a code path, `radar triage --llm=api` could fill
exactly the same files from the Anthropic SDK: moving to a GitHub Actions cron is a flag,
not a rewrite.

Anything missing or schema-invalid degrades that paper to lexical scoring. A bad run
produces a worse digest; it never produces an empty one.

```bash
uv sync
uv run radar run --week 2026-W35 --no-llm     # full pipeline, real data, zero tokens
uv run pytest -q
python3 -m http.server                        # then open http://localhost:8000
```

The routine lives in [`.claude/routines/weekly-radar.md`](.claude/routines/weekly-radar.md).

## Tuning it

Everything lab-specific is in `config/`. Retargeting the radar at another group means
editing YAML, not Python:

- `config/profile.yaml` — open threads, ranking weights, front-page sizes
- `config/categories.yaml` — the nine categories, every lexical rule, the general-CS gate
- `config/sources.yaml` — feeds, journals, the author watchlist, blindspot quotas
- `config/prompts/` — triage, deep dive, blindspot

**When something is overlooked, add it to `eval/goldset.yaml` and run `radar eval`.** For
each paper it reports whether the filter as configured today would surface it, the exact
rule that dropped it if not, and — the part that keeps this honest — what recovering it
would cost:

```
  [      FAIL] Building the nuclear pore complex
               · REJECTED by must_any: no must_any vocabulary hit
               → no must_any term matched

  suggested terms — each priced against the archived weeks:
    nuclear pore       recovers 1, admits +1.0/week    [cheap — add it]
    complex            recovers 1, admits +137.0/week  [expensive — prefer a more specific phrase]
```

Nothing is ever applied automatically. Every change to what the radar looks for is a diff
you approve. Judge changes by the gold set and the recall audit, never by whether this
week's front page happens to look good — a front page that looks good is exactly what an
overfitted filter produces.

`data/raw/*.jsonl.gz` keeps everything fetched, so `--cached` replays a week with no
network calls. You cannot tune prompts or weights honestly without that.

## Notes on the sources

Verified live against the APIs, and worth knowing before changing anything:

- bioRxiv `?category=` **does** filter, but pages are **30 records**, not 100.
- bioRxiv DOIs are now issued under the `10.64898` prefix, not `10.1101`.
- bioRxiv `published` is the literal string `"NA"` when there is no journal version.
- arXiv requires `https` and rate-limits to about one request per three seconds.
- `cs.LG` + `cs.AI` + `stat.ML` hold ~3,200 records per 10-day window against ~200 for the
  four full categories. The methodology gate is therefore pushed into the arXiv *query*,
  which brings that to ~300 with no truncation — capping the fetch instead would silently
  drop papers, which is the failure this radar exists to avoid.

## Failure is loud

`radar assemble` always writes `data/status.json`, and the front page renders a banner from
it: amber when a source failed or came in under its expected minimum, red when the radar
has not completed a run in more than ten days. Under a scheduled routine there is no
failed-workflow notification to rely on, so staleness has to be visible on the surface you
actually read. Silence is never a valid state.

---

Design spec: [`research-radar-spec.md`](research-radar-spec.md).
