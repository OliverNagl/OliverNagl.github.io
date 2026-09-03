"""Ranking (spec §3).

Deliberately arithmetic, not learned, so you can always see why something ranked where it
did. Every term is kept in a `ScoreBreakdown` rather than collapsed into a total, because
the whole tuning story depends on being able to say "it lost on category weight, not on
relevance".

`assets/rank.js` reimplements `score()` so the tuning page can re-rank an archived week
live in the browser. `tests/test_rank_parity.py` asserts the two agree on a fixture; change
them together.
"""

from __future__ import annotations

from .config import Config
from .models import Paper, PrefilterVerdict, ScoreBreakdown, Scored, Triage

# Relevance and novelty are 0-10 from triage; normalise to 0-1 so the weights in
# profile.yaml stay comparable to each other.
MAX_RATING = 10.0


def venue_tier(paper: Paper, cfg: Config) -> float:
    v = (paper.venue or "").lower().strip()
    if v in cfg.venue_tiers:
        return cfg.venue_tiers[v]
    for name, tier in cfg.venue_tiers.items():
        if name and name in v:
            return tier
    return 0.0


def score(
    *,
    relevance: float,
    novelty: float,
    category_weight: float,
    watchlist_author: bool,
    code_released: bool,
    venue_tier: float,
    similar_seen_recently: bool,
    weights: dict[str, float],
) -> ScoreBreakdown:
    """The §3 arithmetic, isolated so it can be tested and mirrored in JS."""
    return ScoreBreakdown(
        relevance=round(weights["relevance"] * (relevance / MAX_RATING), 4),
        novelty=round(weights["novelty"] * (novelty / MAX_RATING), 4),
        category=round(weights["category"] * category_weight, 4),
        watchlist_author=round(weights["watchlist_author"] * float(watchlist_author), 4),
        code_released=round(weights["code_released"] * float(code_released), 4),
        venue_tier=round(weights["venue_tier"] * venue_tier, 4),
        similar_seen_recently=round(
            weights["similar_seen_recently"] * float(similar_seen_recently), 4
        ),
    )


def lexical_ratings(verdict: PrefilterVerdict) -> tuple[int, int]:
    """Stand-in relevance/novelty when there is no LLM judgement for a paper.

    Used by `--no-llm` runs and as the per-batch degradation path when triage output fails
    schema validation. A degraded run produces a worse digest; it never produces an empty
    one (spec §9).
    """
    # Lexical scores in practice run 0-15; map onto the 0-10 rating scale, capped.
    rel = max(0, min(10, round(verdict.lexical_score / 1.5)))
    return rel, 5


def build_scored(
    paper: Paper,
    verdict: PrefilterVerdict,
    triage: Triage | None,
    cfg: Config,
    *,
    similar_seen_recently: bool = False,
) -> Scored:
    if triage is not None:
        category = triage.category
        relevance, novelty = triage.relevance, triage.novelty
        reason = triage.reason
        degraded = triage.degraded
    else:
        category = verdict.best_category or "ml-method"
        relevance, novelty = lexical_ratings(verdict)
        reason = verdict.reason
        degraded = True

    cat = cfg.category_by_id.get(category)
    if cat is None:                       # LLM invented a category id; fall back safely
        category = verdict.best_category or cfg.categories[0].id
        cat = cfg.category_by_id[category]

    breakdown = score(
        relevance=relevance,
        novelty=novelty,
        category_weight=cat.weight,
        watchlist_author=bool(verdict.watchlist_hit),
        code_released=bool(paper.code_url),
        venue_tier=venue_tier(paper, cfg),
        similar_seen_recently=similar_seen_recently,
        weights=cfg.weights,
    )

    links = {"url": paper.url}
    if paper.doi:
        links["doi"] = f"https://doi.org/{paper.doi}"
    if paper.pdf_url:
        links["pdf"] = paper.pdf_url
    if paper.code_url:
        links["code"] = paper.code_url

    return Scored(
        id=paper.id,
        title=paper.title,
        authors_short=paper.authors_short,
        authors=paper.authors,
        venue=paper.venue,
        source=paper.source,
        date=paper.date,
        subject=paper.subject,
        category=category,
        score=breakdown.total,
        breakdown=breakdown,
        relevance=relevance,
        novelty=novelty,
        reason=reason,
        abstract=paper.abstract,
        links=links,
        watchlist_hit=verdict.watchlist_hit,
        degraded=degraded,
    )


def select_front_page(
    scored: list[Scored], *, top_n: int, max_per_category: int
) -> tuple[list[Scored], list[Scored]]:
    """Global top-N with a per-category cap, so one hot week in ML methodology cannot
    crowd out everything else (spec §3). Returns (front_page, remainder)."""
    ordered = sorted(scored, key=lambda s: (s.score, s.date), reverse=True)
    front: list[Scored] = []
    per_cat: dict[str, int] = {}
    chosen: set[str] = set()

    for s in ordered:
        if len(front) >= top_n:
            break
        if per_cat.get(s.category, 0) >= max_per_category:
            continue
        front.append(s)
        chosen.add(s.id)
        per_cat[s.category] = per_cat.get(s.category, 0) + 1

    return front, [s for s in ordered if s.id not in chosen]


def build_backlog(
    remainder: list[Scored], *, max_per_category: int
) -> dict[str, list[Scored]]:
    backlog: dict[str, list[Scored]] = {}
    for s in sorted(remainder, key=lambda s: s.score, reverse=True):
        bucket = backlog.setdefault(s.category, [])
        if len(bucket) < max_per_category:
            bucket.append(s)
    # Busiest category first — that ordering is itself information about the week.
    return dict(sorted(backlog.items(), key=lambda kv: len(kv[1]), reverse=True))
