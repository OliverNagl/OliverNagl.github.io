"""The lexical prefilter (spec §3).

Four tiers, all driven by `config/categories.yaml`:

  hard_include  a watchlist author or a decisive phrase -> skips the filter entirely
  must_any      broad domain vocabulary; at least one hit required to survive
  boost         weighted per-category terms; produces the shortlist ordering
  hard_exclude  clinical/ecology/agronomy; dropped from the shortlist but KEPT in the
                rejected pool, where the blindspot sampler can still reach it (spec §4)

Every paper gets a `PrefilterVerdict` recording which rule decided its fate. That is not
diagnostics for its own sake: it is what lets `radar eval` explain an overlooked paper by
naming the exact rule that dropped it, instead of guessing (requirement 3).
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import Config, normalise_author
from .models import Paper, PrefilterVerdict
from .util import first_term_hit

# arXiv categories whose volume is unmanageable without a methodology gate. Measured at
# ~3200 records per 10-day window against ~200 for the four full categories.
GENERAL_CS = {"cs.lg", "cs.ai", "stat.ml", "cs.cv", "cs.cl", "cs.ne"}


@dataclass
class PrefilterResult:
    shortlist: list[Paper]
    rejected: list[Paper]
    verdicts: dict[str, PrefilterVerdict]

    @property
    def counts(self) -> dict[str, int]:
        return {"shortlist": len(self.shortlist), "rejected": len(self.rejected)}


def watchlist_hit(paper: Paper, cfg: Config) -> str | None:
    """Return the watchlist entry this paper matches, if any."""
    wl = cfg.watchlist
    for a in paper.authors:
        key = normalise_author(a)
        if key and key in wl:
            return wl[key]
    return None


def score_categories(text: str, cfg: Config) -> dict[str, float]:
    """Sum of matched boost weights per category.

    Terms match as word-anchored prefixes (see `util.compile_term`): `self-assembl` catches
    assembly/assembling/assembled without a stemmer, while `rna` no longer matches inside
    "internal".
    """
    scores: dict[str, float] = {}
    for cat in cfg.categories:
        s = 0.0
        for _term, weight, pat in cat.boost_patterns:
            if pat.search(text):
                s += weight
        if s:
            scores[cat.id] = round(s, 3)
    return scores


def judge(paper: Paper, cfg: Config) -> PrefilterVerdict:
    """Decide one paper's fate and record why."""
    text = paper.text
    cat_scores = score_categories(text, cfg)
    best = max(cat_scores, key=lambda k: cat_scores[k]) if cat_scores else None
    lexical = round(sum(cat_scores.values()), 3)

    wl = watchlist_hit(paper, cfg)
    if wl:
        return PrefilterVerdict(
            passed=True, tier="hard_include",
            reason=f"watchlist author: {wl}",
            matched_include=wl, watchlist_hit=wl,
            lexical_score=lexical, best_category=best, category_scores=cat_scores,
        )

    inc = first_term_hit(text, cfg.hard_include_patterns)
    if inc:
        return PrefilterVerdict(
            passed=True, tier="hard_include",
            reason=f"hard-include phrase: {inc!r}",
            matched_include=inc,
            lexical_score=lexical, best_category=best, category_scores=cat_scores,
        )

    exc = first_term_hit(text, cfg.hard_exclude_patterns)
    if exc:
        return PrefilterVerdict(
            passed=False, tier="rejected",
            reason=f"hard-exclude phrase: {exc!r}",
            failed_rule="hard_exclude", matched_exclude=exc,
            lexical_score=lexical, best_category=best, category_scores=cat_scores,
        )

    # The general-CS gate. Volume there is ~16x the rest of arXiv combined and most of it
    # is not about molecules at all, so a decisive generative-modelling term passes on its
    # own while generic ML vocabulary additionally needs a domain term (spec §3).
    if paper.source == "arxiv" and paper.subject.lower() in GENERAL_CS:
        gate = cfg.gate_patterns
        strong = first_term_hit(text, gate["strong"])
        if strong:
            return PrefilterVerdict(
                passed=True, tier="gated_cs",
                reason=f"general-CS {paper.subject}: decisive method term {strong!r}",
                lexical_score=lexical, best_category=best, category_scores=cat_scores,
            )
        weak = first_term_hit(text, gate["weak_needs_domain"])
        domain = first_term_hit(text, gate["domain"])
        if weak and domain:
            return PrefilterVerdict(
                passed=True, tier="gated_cs",
                reason=f"general-CS {paper.subject}: {weak!r} together with domain term {domain!r}",
                lexical_score=lexical, best_category=best, category_scores=cat_scores,
            )
        if weak:
            reason = f"general-CS {paper.subject}: {weak!r} but no domain term"
        else:
            reason = f"general-CS {paper.subject}: no methodology term"
        return PrefilterVerdict(
            passed=False, tier="rejected", reason=reason, failed_rule="gated_cs",
            lexical_score=lexical, best_category=best, category_scores=cat_scores,
        )

    must = first_term_hit(text, cfg.must_any_patterns)
    if not must:
        return PrefilterVerdict(
            passed=False, tier="rejected",
            reason="no must_any vocabulary hit",
            failed_rule="must_any",
            lexical_score=lexical, best_category=best, category_scores=cat_scores,
        )

    if lexical <= 0:
        # Survived must_any but matched no category vocabulary at all. Ranking it would be
        # arbitrary, so it goes to the rejected pool where the blindspot sampler can reach it.
        return PrefilterVerdict(
            passed=False, tier="rejected",
            reason=f"must_any hit {must!r} but no category boost term matched",
            failed_rule="no_boost",
            lexical_score=0.0, best_category=None, category_scores={},
        )

    return PrefilterVerdict(
        passed=True, tier="must_any",
        reason=f"must_any hit {must!r}, lexical score {lexical}",
        lexical_score=lexical, best_category=best, category_scores=cat_scores,
    )


def prefilter(papers: list[Paper], cfg: Config, limit: int | None = None) -> PrefilterResult:
    """Split the corpus into a shortlist and a retained rejected pool.

    `limit` caps the shortlist by lexical score. The overflow is *not* discarded — it is
    appended to the rejected pool, so the blindspot channel and the recall audit still see it.
    """
    verdicts: dict[str, PrefilterVerdict] = {}
    passed: list[Paper] = []
    rejected: list[Paper] = []

    for p in papers:
        v = judge(p, cfg)
        verdicts[p.id] = v
        (passed if v.passed else rejected).append(p)

    # Watchlist first, then other hard-include hits, then lexical score. The watchlist is
    # the single best precision/effort channel in the system (spec §2), so a paper from a
    # tracked author must never be pushed out of a capped shortlist by a keyword-dense but
    # ordinary paper — which is exactly what happens if both merely share the same tier.
    passed.sort(
        key=lambda p: (
            verdicts[p.id].watchlist_hit is not None,
            verdicts[p.id].tier == "hard_include",
            verdicts[p.id].lexical_score,
            p.date,
        ),
        reverse=True,
    )

    if limit is not None and len(passed) > limit:
        rejected.extend(passed[limit:])
        passed = passed[:limit]

    return PrefilterResult(shortlist=passed, rejected=rejected, verdicts=verdicts)
