# Research Radar — design spec

A weekly, automated literature radar for the Baker/King problem space. Runs in GitHub Actions,
writes to a git repo, produces a short front page plus a searchable archive.

**Target reading time: 3 minutes for the front page, 10 minutes if you scan the backlog.**
Everything in this design is subordinate to that number and to one failure mode: *missing something
that mattered*.

---

## 0. Design principles

1. **Recall first, precision second.** It is cheap to skim a bad recommendation and expensive to miss
   a good one. The funnel is wide at the top, and the rejected pool is *kept*, not discarded.
2. **Everything lab-specific lives in `config/`.** No code changes to retarget the radar at another
   group. Retargeting = editing two YAML files.
3. **Deterministic where possible, LLM where necessary.** Fetch, dedupe, prefilter and ranking
   arithmetic are plain code you can debug. The LLM only does judgement calls (category, relevance,
   why-it-matters).
4. **Replayable.** Raw fetches are archived. You can re-run last month's scoring with a new prompt
   without re-fetching, which is the only way to tune the thing honestly.
5. **Fail loudly.** A literature monitor that silently stops working is worse than no monitor. Any
   degraded run is flagged at the top of the digest and opens an issue.

---

## 1. Category taxonomy

Derived from what the two labs actually say they work on.

**Baker Lab** — design software and ML methods; therapeutics and binders; nanomaterials and symmetric
complexes (including the recent quasi-symmetric 40–200 nm cages); enzymes and catalysts; membrane
proteins and solubilisation; nanopores and protein–electronics interfaces; DNA-binding proteins and
de novo nucleases; immunomodulators, antibodies and nanobodies; intracellular cargo delivery.

**King Lab** — general methods for designed protein nanomaterials; structure-based vaccine design
(antigen stabilisation, nanoparticle immunogens, de novo glycoproteins that modulate immune
trafficking, protein adjuvants targeting innate immune receptors, mRNA-launched nanoparticle
vaccines); pseudosymmetric and asymmetric nanostructures; hybrid biomaterials incorporating lipids
and nucleic acids; scaffolds for membrane-protein display.

Nine categories. They exist to **route and organise the backlog**, not to structure the front page —
the front page is a global top-N, so adding categories does not add reading time.

| ID | Category | Scope | Weight |
|---|---|---|---|
| `ml-method` | ML methodology (transferable) | Generative modelling, diffusion/flow matching, discrete & latent diffusion, RL/preference optimisation, equivariant architectures, sampling, active learning, uncertainty, scaling laws. Domain-agnostic work that *transfers*. This is where an "explorative models" preprint lands. | 1.0 |
| `struct-pred` | Structure prediction & biomolecular representation | AF3-class co-folding, protein language models, inverse folding, MSA-free prediction, conformational ensembles, docking, confidence metrics and oracles, benchmarks. | 1.1 |
| `design-method` | De novo design methodology | RFdiffusion-class backbone generation, motif scaffolding, hallucination, sequence design, symmetry handling, binder design pipelines, in-silico filters, success-rate and benchmark papers. | 1.3 |
| `function-design` | Functional design: binders, therapeutics, sensors | Minibinders, receptor/GPCR modulators, antibodies and nanobodies, peptide therapeutics, degraders, biosensors, nanopores, DNA/RNA binders, switches and logic. | 1.0 |
| `enzyme` | Enzyme design & catalysis | Theozymes, active-site scaffolding, ML for enzymes, ML-guided directed evolution, mechanism, metalloenzymes and cofactors. | 1.0 |
| `assembly` | Self-assembly & nanomaterials | Cages, capsids, symmetric/pseudosymmetric/asymmetric oligomers, filaments, 2D arrays, protein crystals, assembly thermodynamics and kinetics, tiling theory and Caspar–Klug, hybrid protein–lipid/nucleic-acid materials, cryo-EM of assemblies. | 1.3 |
| `immunogen` | Immunogen engineering & vaccines | Nanoparticle immunogens, epitope scaffolding, germline targeting, adjuvants, glycan engineering, mRNA-launched platforms, antigen stabilisation, immune trafficking. | 1.1 |
| `delivery` | Delivery, virology & cell entry | LNPs, AAV and capsid engineering, endosomal escape, VLPs, targeted intracellular delivery, viral assembly and maturation, budding and ESCRT biology. | 1.0 |
| `wetlab-method` | Experimental methods & validation | High-throughput characterisation, cryo-EM/nsEM pipelines, deep mutational scanning, display methods, native MS, structural dynamics (HDX, smFRET), lab automation. | 0.8 |

`assembly` and `design-method` are up-weighted because they are the direct working area. Adjust in
`categories.yaml`; nothing else needs to change.

**Blindspot is not a category.** It is a separate slot fed by a separate channel — see §4.

---

## 2. Sources

| Source | API | What it covers | Rough weekly volume |
|---|---|---|---|
| bioRxiv | `api.biorxiv.org/details/biorxiv/<from>/<to>/<cursor>?category=<cat>` — open, no key, 100 records/page, returns DOI, title, authors, date, category, abstract, and a `published` field once the journal version appears | The main preprint channel | ~700 after category filter |
| medRxiv | same API, `medrxiv` server | Vaccine and clinical-adjacent | ~100 |
| arXiv | Atom API, `cat:` queries | `q-bio.BM`, `q-bio.QM`, `cond-mat.soft`, `physics.bio-ph` in full; `cs.LG`, `cs.AI`, `stat.ML` keyword-gated | ~250 + gated |
| PubMed | E-utilities `esearch`/`efetch` | Journal versions in a tracked venue list | ~400 |
| ChemRxiv | public API | Catalysis, theozymes, chemical biology | ~50 |
| OpenAlex | REST | Supplement: catches venues the above miss, supplies citation counts for the recall audit | — |

Two extra high-signal channels, cheap to run:

- **Author watchlist.** A query per tracked author across all sources. Papers from ~30 named people
  bypass the prefilter and go straight to LLM triage. This is the single best precision/effort ratio
  in the system.
- **Code-release signal.** Detect a GitHub/Zenodo link in the abstract or full text. A method with
  released code is materially more actionable than one without; it gets a score boost.

The `published` field from bioRxiv gives preprint→journal linkage for free. When a preprint you
already saw appears in a journal, the radar notes it in a one-line "now published" strip rather than
re-reporting it as new.

---

## 3. Pipeline

```
                    ~4000 records
  collect  ─────────────────────────────►  data/raw/2026-W36.jsonl.gz   (archived, replayable)
     │
     ├─ 10-day lookback window (not 7) ──► overlap absorbs indexing lag
     ▼
  dedupe   ── DOI + normalised-title fuzzy match ── against data/seen.sqlite
     │                                                     ~3500 new
     ▼
  prefilter ── lexical, tiered ──┬──► shortlist        ~250   ─┐
                                 └──► rejected pool    ~3250   │  KEPT, not dropped
     │                                    │                    │
     ▼                                    ▼                    │
  triage (Haiku, batched)          blindspot sampler           │
  category + relevance 0–10        stratified sample of 150    │
  + 12-word reason                 from the rejected pool      │
     │                                    │                    │
     ▼                                    ▼                    │
  rank (deterministic arithmetic)   blindspot scoring (Sonnet) │
     │                                    │                    │
     ▼                                    ▼                    │
  deep dive (Sonnet, ~15 papers)    1 pick                     │
     │                                    │                    │
     └──────────────┬─────────────────────┘                    │
                    ▼                                          │
              assemble → data/issues/2026-W36.json  ◄───────────┘
                    │
        ┌───────────┼───────────┬──────────────┐
        ▼           ▼           ▼              ▼
   GitHub issue  digests/*.md  docs/ (Pages)  feed.xml
```

**Prefilter, three tiers.** All in `categories.yaml`, all auditable:

- `hard_include` — watchlist author, or a phrase like `de novo design`, `protein nanoparticle`,
  `nanocage`, `RFdiffusion`. Skips the prefilter entirely.
- `must_any` — broad domain vocabulary. A record needs at least one hit to survive.
- `boost` — weighted per-category term lists; produces the shortlist ordering.
- `hard_exclude` — clinical trial reports, epidemiology, ecology, agronomy. These still land in the
  rejected pool and remain visible to the blindspot sampler.

`cs.LG` is the volume problem: several thousand a week, and the interesting fraction is small but
real. Gate it on a methodology term list (`diffusion`, `flow matching`, `discrete diffusion`,
`equivariant`, `SE(3)`, `guidance`, `preference optimization`, `test-time compute`, …) rather than
trying to read it all.

**LLM passes.**

1. *Triage* — Haiku, 25 abstracts per call, strict JSON out: `{id, category, relevance, novelty, reason}`.
   ~250 papers ≈ 100k input tokens.
2. *Deep dive* — Sonnet, one call per paper, top ~15 only. Produces three sentences of
   why-this-matters, an explicit action tag (`read` / `skim` / `track` / `cite`), and — this is the
   part that saves the most time — which of *your* open questions it touches, drawn from a
   `open_threads` list in `profile.yaml` that you keep updated by hand.
3. *Blindspot* — see below.

**Ranking** is deliberately arithmetic, not learned, so you can see why something ranked where it did:

```
score = 1.00 * relevance
      + 0.35 * novelty
      + 0.50 * category_weight
      + 0.40 * watchlist_author
      + 0.25 * code_released
      + 0.20 * venue_tier
      - 0.30 * seen_similar_recently
```

Weights live in `profile.yaml`. The front page takes the global top 5 **with a max of 2 per
category**, so one hot week in ML methodology cannot crowd out everything else.

---

## 4. The blindspot channel

The failure this addresses: the radar gets better at finding what you already know you want, and
correspondingly worse at everything else. A blindspot pick drawn from the *shortlist* would be
useless — it would just be the sixth-best hit. It has to come from the pool the filter threw away.

Mechanics:

1. The prefilter's rejected pool is retained in full for the run.
2. Sample 150 records, stratified so that low-lexical-overlap items are over-represented and every
   source is represented. Sources that are structurally under-weighted in the main funnel —
   `cond-mat.soft`, `physics.bio-ph`, `math.OC`, non-protein biology — get a guaranteed quota.
   Soft-matter self-assembly physics in particular is a standing blindspot for anyone working on
   capsids.
3. Score with a deliberately different prompt. Not *"is this relevant?"* but roughly: *"Does this
   contain a mechanism, formalism, or empirical result that would change how someone designing
   self-assembling proteins thinks — even though the paper is not about protein design?"*
4. Take the single highest scorer. One per week. Present it with an explicit stated connection to a
   current problem, and an honest confidence marker.

One is the right number. Two makes it a section people skip.

---

## 5. Repo layout

```
research-radar/
├── .github/workflows/
│   ├── weekly.yml            # cron + workflow_dispatch (backfill by --week)
│   ├── feedback.yml          # nightly: harvest reactions from the weekly issue
│   └── audit.yml             # monthly recall audit (§8)
├── config/
│   ├── profile.yaml          # who this is for, open threads, weights, models, sizes
│   ├── categories.yaml       # the taxonomy + all lexical rules
│   ├── sources.yaml          # feeds, arXiv/bioRxiv categories, journals, watchlist
│   └── prompts/
│       ├── triage.md
│       ├── deep_dive.md
│       └── blindspot.md
├── radar/
│   ├── models.py             # Paper / Scored / Issue  (pydantic)
│   ├── sources/
│   │   ├── base.py           # Source protocol: fetch(window) -> list[Paper]
│   │   ├── biorxiv.py  arxiv.py  pubmed.py  chemrxiv.py  openalex.py
│   ├── collect.py            # runs all sources concurrently, tolerates failures
│   ├── dedupe.py
│   ├── prefilter.py          # returns (shortlist, rejected_pool)
│   ├── llm.py                # batching, JSON schema validation, retry, budget guard
│   ├── rank.py
│   ├── blindspot.py
│   ├── assemble.py           # -> Issue
│   ├── render/
│   │   ├── markdown.py  site.py  rss.py
│   ├── publish.py            # git commit + open/update GitHub issue
│   └── cli.py                # radar run --week 2026-W36 [--dry-run] [--no-llm]
├── data/
│   ├── raw/2026-W36.jsonl.gz     # every record fetched, before filtering
│   ├── issues/2026-W36.json      # canonical output — everything else renders from this
│   ├── seen.sqlite               # cross-week dedupe
│   └── feedback.jsonl
├── digests/2026-W36.md
├── docs/                         # GitHub Pages build output
├── tests/
├── pyproject.toml                # uv, locked
└── README.md
```

`data/issues/*.json` is the single source of truth. Markdown, the site, and the RSS feed are all
pure functions of it, so a rendering bug is never a data-loss event and re-rendering the whole
archive is one command.

---

## 6. Data model

```jsonc
{
  "week": "2026-W36",
  "window": {"from": "2026-08-24", "to": "2026-09-02"},
  "generated_at": "2026-09-03T13:04:11Z",
  "source_health": [
    {"source": "biorxiv", "ok": true,  "fetched": 2431},
    {"source": "chemrxiv","ok": false, "error": "timeout", "expected_min": 20}
  ],
  "stats": {"fetched": 4102, "new": 3488, "shortlisted": 261, "scored": 261},
  "front_page": [
    {
      "id": "10.1101/2026.08.28.123456",
      "title": "...",
      "authors_short": "Lee S, …, King NP",
      "venue": "bioRxiv",
      "date": "2026-08-28",
      "category": "assembly",
      "score": 9.4,
      "relevance": 9, "novelty": 8,
      "why": "Three sentences on what this changes.",
      "touches": ["symmetry-native diffusion", "assembly oracle negatives"],
      "action": "read",
      "links": {"doi": "...", "pdf": "...", "code": "https://github.com/..."}
    }
  ],
  "blindspot": { "...same shape...", "connection": "...", "confidence": "medium" },
  "backlog": {"assembly": [...], "ml-method": [...]},
  "now_published": [{"preprint_doi": "...", "journal_doi": "...", "journal": "Nature"}]
}
```

---

## 7. Front end

Three surfaces, one JSON. Build them in this order.

**1. A GitHub issue per week — the primary surface.** This is the answer to "optimised for a
researcher's time". You get the notification for free, on your phone, in the place you already work.
Checkboxes let you mark things read. The comment thread is where you leave a note to yourself about
why something mattered. And crucially, **emoji reactions on the issue are the feedback signal** —
no separate UI to build, no habit to form. 👍 = good hit, 👎 = noise, 🎉 = add to library.

**2. `digests/2026-W36.md` committed to the repo.** Permanent, greppable with `rg`, diffable,
readable offline and on the GitHub mobile app. The archive that survives the tooling.

**3. GitHub Pages.** Worth building, but for one reason that markdown genuinely cannot do:
**full-archive search**. A single static page with a client-side index over every issue ever
generated, so that in six months "did anything come past about pseudosymmetric two-component
assembly" is a two-second query. Nice looks are a side benefit; search is the point. Build it in
week 3, not week 1.

Optionally an RSS feed (`docs/feed.xml`, ~20 lines) if you want it in a reader.

**Front page layout:**

```markdown
# Week 36 · 24 Aug – 2 Sep 2026
_3488 new records → 261 screened → 5 picks. All sources healthy._

## Top 5
### 1. [read] Title of the thing
Lee S, …, King NP · bioRxiv · 28 Aug · `assembly` · code ✔
> Three sentences: what it does, why it is not the previous thing, what it changes for you.
Touches: symmetry-native diffusion · assembly oracle negatives
[doi](…) · [pdf](…) · [code](…)
…

## Blindspot
### [track] Title from cond-mat.soft
> Why this might matter even though it is not about proteins. Confidence: medium.

## Now published
- That preprint from W22 is out in Nature.

<details><summary>Backlog · 47 papers by category</summary>
### assembly (9)
- Title — one line — [doi]
…
</details>
```

---

## 8. Feedback and the recall audit

**Feedback loop.** `feedback.yml` harvests reactions nightly into `data/feedback.jsonl`. It is used
two ways:

- Highly-rated papers become few-shot exemplars in the triage prompt — the cheapest and most
  effective form of tuning.
- A monthly job mines terms that discriminate 👍 from 👎 and **opens a pull request** proposing
  changes to `categories.yaml`.

The system never silently rewrites its own filters. Every change to what it looks for is a diff you
approve. Without this, drift is undetectable.

**Recall audit — the part that directly addresses "nothing important gets overlooked".** Monthly,
`audit.yml` takes papers the radar *rejected* 2–6 months ago, queries OpenAlex for citation counts
and journal publication status, and reports anything that crossed a threshold as a **miss**, with
the reason it was filtered out. This turns an invisible failure mode into a monthly list of concrete
bugs. It is the single most valuable component here and it is about 60 lines of code.

---

## 9. Robustness

- **10-day lookback, not 7.** Overlap plus `seen.sqlite` dedupe means indexing lag can never drop a
  paper on the floor.
- **Per-source isolation.** One source failing degrades the digest; it does not fail the run. Each
  source declares an `expected_min`; falling below it flags the run as degraded and prints a banner
  at the top of the digest. Silent under-coverage is the real danger, not a crash.
- **Raw archive.** `data/raw/*.jsonl.gz` holds everything fetched. `radar rescore --week 2026-W36`
  replays new prompts against old data with no network calls. You cannot tune prompts honestly
  without this.
- **Schema-validated LLM output**, one repair retry, then fall back to lexical ranking for that
  batch. A bad LLM response degrades quality; it never produces an empty digest.
- **Idempotent on the ISO week key.** Re-running overwrites cleanly. `--week` backfills.
- **Budget guard.** Hard token cap per run in `profile.yaml`; exceeding it truncates the deep-dive
  pass and says so in the digest rather than running up a bill.
- **Failure is loud.** A failed workflow opens an issue titled `radar failed: 2026-W36`. Silence is
  never a valid state.
- **Pinned dependencies** (`uv.lock`), no network access during rendering.
- Secrets: `ANTHROPIC_API_KEY`, optionally `NCBI_API_KEY` for higher PubMed rate limits.
  `GITHUB_TOKEN` is provided by Actions.

**Cost.** Triage is roughly 100k input / 15k output tokens per week on Haiku; deep dive roughly
30k / 8k on Sonnet; blindspot roughly 25k / 3k. This is a small enough monthly figure that the
budget guard exists to catch bugs, not to control spend.

---

## 10. Retargeting to another group

The whole point of pushing lab-specific content into `config/`:

1. Copy `config/` to `config-profiles/<name>/`.
2. Edit `categories.yaml` — rename categories, rewrite the term lists, set weights.
3. Edit `sources.yaml` — swap the author watchlist and journal list.
4. Edit `profile.yaml` — set `open_threads` to the new person's actual open questions.
5. `radar run --config config-profiles/<name> --dry-run --no-llm` to sanity-check the funnel volumes
   before spending a token.

No Python is touched. A second radar for a different group is a config directory and a second cron
entry.

---

## 11. Config sketches

### `config/profile.yaml`

```yaml
name: "IPD radar — capsid & nanomaterial design"
timezone: America/Los_Angeles
front_page:
  top_n: 5
  max_per_category: 2
  blindspot: 1
  backlog_max_per_category: 10

# Hand-maintained. Drives the "touches" field in the deep-dive pass.
# Keeping this current is the highest-leverage 5 minutes you will spend on the system.
open_threads:
  - "symmetry-native / tied-ASU diffusion for icosahedral assemblies"
  - "oracles predicting whether a designed subunit assembles, without experimental positives"
  - "quasi-equivalence: one sequence, multiple backbone conformations by assembly slot"
  - "negative-example construction for design-quality regression"
  - "operator-conditioned sparse attention over symmetry images"

models:
  triage: claude-haiku-4-5
  deep: claude-sonnet-5
  blindspot: claude-sonnet-5
budget:
  max_input_tokens: 400000
  max_output_tokens: 60000

weights:
  relevance: 1.00
  novelty: 0.35
  category: 0.50
  watchlist_author: 0.40
  code_released: 0.25
  venue_tier: 0.20
  similar_seen_recently: -0.30

window:
  lookback_days: 10
```

### `config/categories.yaml` (excerpt — same shape for all nine)

```yaml
hard_include_phrases:
  - de novo design
  - protein nanoparticle
  - nanocage
  - RFdiffusion
  - ProteinMPNN
  - designed protein assembly

must_any:
  - protein; peptide; enzyme; antibody; capsid; nanoparticle; assembly; fold; binder
  - diffusion model; generative model; representation learning; equivariant

hard_exclude:                 # excluded from the shortlist, KEPT in the blindspot pool
  - randomized controlled trial
  - epidemiological surveillance
  - crop yield

categories:
  - id: assembly
    name: Self-assembly & nanomaterials
    weight: 1.3
    description: >
      Designed and natural self-assembling protein systems: cages, capsids, symmetric,
      pseudosymmetric and asymmetric oligomers, filaments, 2D arrays, protein crystals.
      Assembly thermodynamics and kinetics. Tiling theory, Caspar-Klug, quasi-equivalence.
      Hybrid protein-lipid and protein-nucleic-acid materials. Cryo-EM of assemblies.
    boost:
      icosahedral: 3.0
      quasi-equivalen: 3.0        # substring, catches -t / -ce
      capsid: 2.5
      nanocage: 2.5
      two-component: 2.0
      symmetry-breaking: 2.0
      self-assembl: 2.0
      T=3: 3.0
      Caspar-Klug: 3.0
      protein crystal: 1.5
    seed_dois:                    # exemplars for the triage prompt
      - 10.1038/s41586-024-xxxxx

  - id: ml-method
    name: ML methodology (transferable)
    weight: 1.0
    description: >
      Domain-agnostic ML advances that transfer to structural biology: diffusion and flow
      matching, discrete and latent diffusion, guidance and inference-time steering, RL and
      preference optimisation, equivariant architectures, sampling, active learning,
      uncertainty, scaling behaviour.
    gate_general_cs: true         # cs.LG requires a boost-term hit to survive prefilter
    boost:
      flow matching: 3.0
      discrete diffusion: 3.0
      equivariant: 2.5
      SE(3): 2.5
      classifier-free guidance: 2.0
      test-time: 1.5
      preference optimization: 1.5
```

### `config/sources.yaml` (excerpt)

```yaml
biorxiv:
  server: biorxiv
  categories: [bioengineering, biochemistry, biophysics, synthetic_biology,
               molecular_biology, microbiology, immunology, bioinformatics]
  expected_min: 300

arxiv:
  full_categories:    [q-bio.BM, q-bio.QM, cond-mat.soft, physics.bio-ph]
  gated_categories:   [cs.LG, cs.AI, stat.ML]     # boost-term hit required
  expected_min: 100

pubmed:
  journals:
    - Nature; Science; Cell; PNAS; Science Advances; eLife
    - Nature Methods; Nature Biotechnology; Nature Chemical Biology
    - Nature Structural & Molecular Biology; Nature Nanotechnology; Nature Communications
    - JACS; ACS Nano; ACS Synthetic Biology; Angewandte Chemie
    - Protein Science; Structure; Nucleic Acids Research; Bioinformatics
    - npj Vaccines; Cell Host & Microbe; Immunity; Molecular Therapy; Journal of Virology
  expected_min: 150

watchlist_authors:      # bypass the prefilter entirely
  - Baker D
  - King NP
  - Veesler D
  - Ovchinnikov S
  - Bhardwaj G
  - DiMaio F
  - Kortemme T
  - Correia BE
  - Ferruz N
  - AlQuraishi M
  - Zhong ED
  - Hilvert D
  - Praetorius F
  - Woolfson DN
  - Yeates TO
  - Hsia Y
  - Wicky BIM
  - Watson JL
  - Dauparas J
  - Anishchenko I
  - Twarock R
  - Hagan MF
  - Zandi R
  - Sundquist WI
  - Schief WR
  - Ward AB

blindspot_quota:        # guaranteed representation in the blindspot sample
  cond-mat.soft: 25
  physics.bio-ph: 20
  math.OC: 10
  biorxiv_other: 40
```

### `.github/workflows/weekly.yml`

```yaml
name: weekly radar
on:
  schedule:
    - cron: "0 13 * * 1"        # Monday 06:00 Seattle / 15:00 Zürich
  workflow_dispatch:
    inputs:
      week: {description: "ISO week, e.g. 2026-W36", required: false}
      dry_run: {type: boolean, default: false}

permissions:
  contents: write
  issues: write

jobs:
  run:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with: {enable-cache: true}
      - run: uv sync --frozen
      - name: Run radar
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          NCBI_API_KEY: ${{ secrets.NCBI_API_KEY }}
        run: |
          uv run radar run \
            ${{ inputs.week && format('--week {0}', inputs.week) || '' }} \
            ${{ inputs.dry_run && '--dry-run' || '' }}
      - name: Commit
        if: ${{ !inputs.dry_run }}
        run: |
          git config user.name  "research-radar"
          git config user.email "actions@github.com"
          git add data digests docs
          git diff --cached --quiet || git commit -m "radar: $(date -u +%G-W%V)"
          git push
      - name: Open weekly issue
        if: ${{ !inputs.dry_run }}
        env: {GH_TOKEN: "${{ github.token }}"}
        run: uv run radar publish-issue
      - name: Report failure
        if: failure()
        env: {GH_TOKEN: "${{ github.token }}"}
        run: |
          gh issue create --title "radar failed: $(date -u +%G-W%V)" \
            --body "Run ${{ github.run_id }} failed. Coverage for this week is incomplete."
```

---

## 12. Build order

Roughly a day of work for a functioning system, spread over three weeks of use.

**Week 1 — the spine.** bioRxiv + arXiv sources, dedupe, prefilter, Haiku triage, markdown render,
GitHub issue, cron. This alone is most of the value. Run it with `--no-llm` first to check funnel
volumes at each stage before spending anything.

**Week 2 — judgement.** PubMed and ChemRxiv sources, deep-dive pass, blindspot channel, feedback
harvesting, `now_published` strip.

**Week 3 — durability.** GitHub Pages with archive search, the monthly recall audit, RSS.

**Then: tune with data, not intuition.** Once you have four weeks of `data/raw/`, use
`radar rescore` to test prompt and weight changes against real history. Judge changes by the recall
audit, not by whether this week's front page looks good — a front page that looks good is exactly
what an overfitted filter produces.
