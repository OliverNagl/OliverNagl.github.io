"""`radar eval` — tune the filter against papers that should have surfaced.

This is the answer to "nothing important gets overlooked". You hand it a list of papers you
found some other way — a colleague forwarded it, you hit it three weeks late — and it tells
you, for each one:

1. whether the filter as configured today would surface it,
2. if not, **the exact rule that dropped it**, and
3. what it would cost in extra noise to change that rule.

Point 3 is the part that keeps this honest. Without it, the harness would just teach you to
bolt on whatever term recovers this week's miss, and a front page that looks good is
exactly what an overfitted filter produces (spec §12). So every suggested term is replayed
across the archived weeks in `data/raw/` and priced: *recovers 2, admits 411 more records*
is a bad trade, and the report says so in numbers rather than leaving it to intuition.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .collect import available_raw_weeks, read_raw
from .config import Config
from .models import Paper
from .prefilter import judge, score_categories
from .rank import build_scored, lexical_ratings, select_front_page
from .resolve import Resolver
from .util import compile_term, iso_week

log = logging.getLogger("radar.eval")

EXPECT_LEVELS = ("front_page", "shortlist", "surfaced")
STOPWORDS = set(
    """a an the and or of to in for on with by is are was were be been we our this that these
those as at from it its can may using used use show shows shown here present study results
based which than then but not have has had we also more most other such into their they
been than very much many one two three new novel approach method results conclusion however
therefore thus both each between during within across""".split()
)


# --------------------------------------------------------------------- gold set ----


def load_goldset(root: Path) -> list[dict]:
    p = root / "eval" / "goldset.yaml"
    if not p.exists():
        return []
    data = yaml.safe_load(p.read_text()) or {}
    entries = data.get("papers", data if isinstance(data, list) else [])
    out = []
    for e in entries or []:
        if not isinstance(e, dict):
            continue
        ident = e.get("doi") or e.get("arxiv") or e.get("id")
        if not ident:
            continue
        # An unquoted arXiv id in YAML parses as a float, and 2605.28960 silently becomes
        # 2605.2896 — data loss that then shows up as an unresolvable entry rather than as
        # a syntax error. Catch it here and say exactly what to fix.
        if isinstance(ident, float):
            log.error(
                "gold entry %r was parsed as a number: quote it in eval/goldset.yaml "
                '(write `arxiv: "%s"`). Any trailing zero is already lost.',
                ident, e.get("arxiv") or ident,
            )
            continue
        expect = e.get("expect", "shortlist")
        if expect not in EXPECT_LEVELS:
            log.warning("gold entry %s: unknown expect %r, using 'shortlist'", ident, expect)
            expect = "shortlist"
        out.append({"id": str(ident), "expect": expect, "note": e.get("note", "")})
    return out


# --------------------------------------------------------------------- verdicts ----


def _shortlist_pressure(cfg: Config) -> dict[str, Any] | None:
    """How hard the shortlist cap is binding, measured over the archived weeks.

    Passing the prefilter is not the same as being screened. The shortlist is capped and
    ordered by lexical score, so a paper with little category vocabulary can clear every
    rule and still never reach triage. Reporting that as a pass would be a lie, and it is
    exactly the kind of silent loss this harness exists to expose.
    """
    weeks = available_raw_weeks(cfg.root)[-4:]
    if not weeks:
        return None
    cap = int(cfg.profile.get("front_page", {}).get("shortlist_max", 300))

    passing_counts: list[int] = []
    cutoffs: list[float] = []
    for w in weeks:
        try:
            papers = read_raw(cfg.root, w)
        except Exception:                                 # noqa: BLE001
            continue
        scores = sorted(
            (v.lexical_score for v in (judge(p, cfg) for p in papers) if v.passed),
            reverse=True,
        )
        passing_counts.append(len(scores))
        # The score a paper must beat to be screened at all this week.
        cutoffs.append(scores[cap - 1] if len(scores) >= cap else 0.0)

    if not passing_counts:
        return None
    return {
        "cap": cap,
        "weeks_sampled": len(passing_counts),
        "passing_per_week": round(sum(passing_counts) / len(passing_counts), 1),
        "binding": any(n > cap for n in passing_counts),
        "lexical_cutoff": round(sum(cutoffs) / len(cutoffs), 2),
    }


def _rank_against_week(paper: Paper, cfg: Config, week: str) -> dict[str, Any] | None:
    """Score the gold paper alongside the real corpus of its own week.

    Standalone pass/fail on the filter is only half the answer — a paper can clear the
    prefilter and still never be seen because it ranked 83rd. Replaying it against the week
    it actually appeared in is the only way to know which happened.
    """
    try:
        corpus = read_raw(cfg.root, week)
    except FileNotFoundError:
        return None

    corpus = [p for p in corpus if p.id != paper.id] + [paper]
    scored = []
    for p in corpus:
        v = judge(p, cfg)
        if not v.passed:
            continue
        # No LLM in an eval replay: use the lexical stand-in for every paper equally, so
        # the comparison between the gold paper and its week is at least self-consistent.
        rel, nov = lexical_ratings(v)
        s = build_scored(p, v, None, cfg)
        s.relevance, s.novelty = rel, nov
        scored.append(s)

    if not any(s.id == paper.id for s in scored):
        return {"in_shortlist": False, "shortlist_size": len(scored)}

    ordered = sorted(scored, key=lambda s: s.score, reverse=True)
    rank = next(i for i, s in enumerate(ordered, 1) if s.id == paper.id)

    fp_cfg = cfg.profile["front_page"]
    front, _ = select_front_page(
        scored,
        top_n=int(fp_cfg["top_n"]),
        max_per_category=int(fp_cfg["max_per_category"]),
    )
    cutoff = front[-1].score if front else 0.0
    mine = next(s for s in scored if s.id == paper.id)

    return {
        "in_shortlist": True,
        "shortlist_size": len(scored),
        "rank": rank,
        "score": round(mine.score, 3),
        "front_page_cutoff": round(cutoff, 3),
        "on_front_page": any(s.id == paper.id for s in front),
        "breakdown": mine.breakdown.model_dump(),
        "category": mine.category,
    }


def evaluate_paper(
    paper: Paper, entry: dict, cfg: Config, pressure: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Run one gold paper through the live filter and explain the outcome."""
    verdict = judge(paper, cfg)
    chain: list[str] = []
    week = iso_week(paper.date)

    if verdict.passed:
        chain.append(f"passed prefilter ({verdict.tier}): {verdict.reason}")
    else:
        chain.append(f"REJECTED by {verdict.failed_rule}: {verdict.reason}")

    result: dict[str, Any] = {
        "id": paper.id,
        "doi": entry["id"],
        "title": paper.title,
        "note": entry.get("note", ""),
        "expect": entry["expect"],
        "date": paper.date.isoformat(),
        "week": week,
        "venue": paper.venue,
        "passed_prefilter": verdict.passed,
        "failed_rule": verdict.failed_rule,
        "matched_exclude": verdict.matched_exclude,
        "lexical_score": verdict.lexical_score,
        "category_scores": verdict.category_scores,
        "watchlist_hit": verdict.watchlist_hit,
    }

    # Name the vocabulary that *would* have saved it — the actionable half of a rejection.
    if verdict.failed_rule == "must_any":
        result["rescue_hint"] = (
            "no must_any term matched; the abstract's distinctive words are listed under "
            "`missing_terms`"
        )
    elif verdict.failed_rule == "hard_exclude":
        result["rescue_hint"] = (
            f"remove or narrow the hard_exclude phrase {verdict.matched_exclude!r}"
        )
    elif verdict.failed_rule == "gated_cs":
        result["rescue_hint"] = (
            "add a decisive term to general_cs_gate.strong, or a domain term so the weak "
            "tier can fire"
        )
    elif verdict.failed_rule == "no_boost":
        result["rescue_hint"] = "matched domain vocabulary but no category boost term"

    # Would it survive the shortlist cap? Only meaningful when the cap actually binds.
    below_cutoff = False
    if verdict.passed and pressure and pressure["binding"]:
        cutoff = pressure["lexical_cutoff"]
        result["lexical_cutoff"] = cutoff
        if verdict.tier != "hard_include" and verdict.lexical_score < cutoff:
            below_cutoff = True
            chain.append(
                f"passed the rules but scores {verdict.lexical_score} against a shortlist "
                f"cutoff of ~{cutoff}: it would be cut before triage ever saw it"
            )
            result["rescue_hint"] = (
                "needs category vocabulary to rank, not just domain vocabulary to pass — "
                "or a larger front_page.shortlist_max"
            )

    ranking = _rank_against_week(paper, cfg, week)
    if ranking is None:
        chain.append(f"no raw archive for {week}, so rank is unknown")
        result["ranking"] = None
    else:
        result["ranking"] = ranking
        if not ranking["in_shortlist"]:
            chain.append("absent from the reconstructed shortlist for its week")
        else:
            chain.append(
                f"ranked #{ranking['rank']} of {ranking['shortlist_size']} "
                f"(score {ranking['score']}, front page needs {ranking['front_page_cutoff']})"
            )

    # Did it meet the bar the gold set asked for?
    if not verdict.passed:
        status = "fail"
    elif below_cutoff:
        status = "weak"
    elif entry["expect"] == "front_page":
        if ranking and ranking.get("on_front_page"):
            status = "pass"
        elif ranking:
            status = "weak"
            chain.append("surfaced, but not on the front page as expected")
        else:
            status = "pass"
    else:
        status = "pass"

    result["status"] = status
    result["chain"] = chain
    return result


# ---------------------------------------------------------------- suggestions ----


def _terms_of(text: str) -> set[str]:
    words = re.findall(r"[a-z][a-z0-9\-]{3,}", text.lower())
    single = {w for w in words if w not in STOPWORDS}
    bigrams = set()
    seq = [w for w in words if w not in STOPWORDS]
    for a, b in zip(seq, seq[1:]):
        bigrams.add(f"{a} {b}")
    return single | bigrams


def _known_terms(cfg: Config) -> set[str]:
    known = set(cfg.must_any) | set(cfg.hard_include)
    for c in cfg.categories:
        known |= set(c.boost)
    for v in cfg.general_cs_gate.values():
        known |= set(v)
    return {t.lower() for t in known}


def suggest_terms(
    misses: list[tuple[Paper, dict]], cfg: Config, *, max_suggestions: int = 12
) -> list[dict]:
    """Propose terms that would recover the misses, each priced against real history.

    A term is only worth proposing if it is common in the papers we missed and rare in the
    corpus at large. The `admits` figure — how many extra records enter the shortlist per
    archived week — is what turns "this term sounds relevant" into a decision.
    """
    if not misses:
        return []

    known = _known_terms(cfg)
    counts: Counter[str] = Counter()
    for paper, _ in misses:
        for t in _terms_of(paper.text):
            if t not in known and len(t) > 4:
                counts[t] += 1

    # Must explain more than one miss, or be strongly distinctive in a single one.
    candidates = [t for t, n in counts.most_common(200) if n >= max(2, len(misses) // 3)]
    if not candidates:
        candidates = [t for t, _ in counts.most_common(30)]

    weeks = available_raw_weeks(cfg.root)
    corpus: list[Paper] = []
    for w in weeks[-4:]:
        try:
            corpus.extend(read_raw(cfg.root, w))
        except Exception:                                 # noqa: BLE001
            continue
    weeks_used = max(1, len(weeks[-4:]))

    # Only records the filter currently rejects can be *admitted* by a new term.
    rejected_now = [p for p in corpus if not judge(p, cfg).passed]

    out: list[dict] = []
    for term in candidates:
        pat = compile_term(term)
        recovers = sum(1 for paper, _ in misses if pat.search(paper.text))
        if not recovers:
            continue
        admits = sum(1 for p in rejected_now if pat.search(p.text))
        per_week = round(admits / weeks_used, 1)

        # The trade, stated plainly. These thresholds are a starting point, not a law —
        # they exist so the report gives an opinion rather than a wall of numbers.
        if per_week <= 5:
            v = "cheap — add it"
        elif per_week <= 25:
            v = "moderate — worth it if the miss mattered"
        else:
            v = "expensive — prefer a more specific phrase"

        cat = max(
            (score_categories(paper.text, cfg) for paper, _ in misses),
            key=lambda d: max(d.values()) if d else 0,
            default={},
        )
        category = max(cat, key=lambda k: cat[k]) if cat else "ml-method"

        out.append(
            {
                "term": term,
                "category": category,
                "weight": 2.0,
                "recovers": recovers,
                "admits": admits,
                "admits_per_week": per_week,
                "weeks_sampled": weeks_used,
                "verdict": v,
            }
        )

    out.sort(key=lambda s: (-s["recovers"], s["admits"]))
    return out[:max_suggestions]


# --------------------------------------------------------------------- driver ----


def run_eval(cfg: Config, *, offline: bool = False) -> dict[str, Any]:
    entries = load_goldset(cfg.root)
    if not entries:
        log.warning("eval/goldset.yaml is empty — nothing to check against")

    resolver = Resolver(
        cfg.root / "eval" / "cache",
        mailto=(cfg.source_cfg("openalex").get("mailto") or ""),
    )

    papers: list[dict] = []
    misses: list[tuple[Paper, dict]] = []
    unresolved: list[str] = []

    pressure = _shortlist_pressure(cfg)

    for entry in entries:
        paper = resolver.resolve(entry["id"], offline=offline)
        if paper is None:
            unresolved.append(entry["id"])
            papers.append(
                {
                    "doi": entry["id"],
                    "title": entry["id"],
                    "note": entry.get("note", ""),
                    "status": "unresolved",
                    "chain": ["could not resolve this identifier from OpenAlex, Crossref or arXiv"],
                }
            )
            continue
        r = evaluate_paper(paper, entry, cfg, pressure)
        papers.append(r)
        if r["status"] != "pass":
            misses.append((paper, r))

    suggestions = suggest_terms(misses, cfg)

    passed = sum(1 for p in papers if p.get("status") == "pass")
    checked = sum(1 for p in papers if p.get("status") != "unresolved")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checked": checked,
        "passed": passed,
        "recall": round(passed / checked, 3) if checked else None,
        "unresolved": unresolved,
        "shortlist_pressure": pressure,
        "raw_weeks_available": available_raw_weeks(cfg.root),
        "papers": papers,
        "suggestions": suggestions,
    }


def write_report(root: Path, report: dict) -> Path:
    p = root / "data" / "eval" / "latest.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, indent=2) + "\n")
    return p
