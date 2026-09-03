"""Turn a week's fetched corpus into the canonical `Issue`.

This is the deterministic half of the pipeline. Judgement (triage, deep dive, blindspot)
arrives as *files* written by whatever is acting as the model — the Routine agent, or an
API-backed `radar triage`. See `radar/work.py` for that contract. If those files are
absent or invalid, ranking degrades to lexical rather than failing (spec §9).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from .collect import collect, write_raw
from .config import Config
from .dedupe import SeenStore, dedupe, find_now_published
from .models import Issue, NowPublished, Paper, Scored, SourceHealth, Stats, Triage, Window
from .prefilter import prefilter
from .rank import build_backlog, build_scored, select_front_page
from .util import week_window

log = logging.getLogger("radar.assemble")


def _shortlist_limit(cfg: Config) -> int:
    return int(cfg.profile.get("front_page", {}).get("shortlist_max", 300))


def gather(
    cfg: Config, week: str, *, use_cache: bool = False
) -> tuple[list[Paper], list[SourceHealth], Stats, list[NowPublished], dict]:
    """Fetch (or replay), dedupe, prefilter. No judgement, no network if `use_cache`."""
    from .collect import read_raw

    lookback = int(cfg.profile["window"]["lookback_days"])
    start, end = week_window(week, lookback)

    if use_cache:
        papers = read_raw(cfg.root, week)
        health = [
            SourceHealth(source=s, ok=True, fetched=sum(1 for p in papers if p.source == s))
            for s in sorted({p.source for p in papers})
        ]
        log.info("replaying %d archived records for %s", len(papers), week)
    else:
        papers, health = collect(cfg, start, end)
        write_raw(cfg.root, week, papers)

    fetched = len(papers)

    with SeenStore(cfg.root / "data" / "seen.sqlite") as store:
        now_pub_raw = find_now_published(papers, store)
        fresh, dropped = dedupe(papers, store, week)
        store.record(fresh, week)

    log.info("dedupe: %d fetched -> %d new (%d already seen)", fetched, len(fresh), dropped)

    result = prefilter(fresh, cfg, limit=_shortlist_limit(cfg))
    log.info(
        "prefilter: %d shortlisted, %d rejected (pool retained)",
        len(result.shortlist), len(result.rejected),
    )

    stats = Stats(
        fetched=fetched,
        new=len(fresh),
        shortlisted=len(result.shortlist),
        rejected=len(result.rejected),
    )
    now_published = [NowPublished(**n) for n in now_pub_raw]

    return (
        result.shortlist,
        health,
        stats,
        now_published,
        {"verdicts": result.verdicts, "rejected": result.rejected, "window": (start, end)},
    )


def assemble(
    cfg: Config,
    week: str,
    shortlist: list[Paper],
    health: list[SourceHealth],
    stats: Stats,
    now_published: list[NowPublished],
    extras: dict,
    *,
    triage: dict[str, Triage] | None = None,
    deep: dict[str, dict] | None = None,
    blindspot: Scored | None = None,
) -> Issue:
    fp_cfg = cfg.profile["front_page"]
    verdicts = extras["verdicts"]
    start, end = extras["window"]
    triage = triage or {}
    deep = deep or {}

    scored = [
        build_scored(p, verdicts[p.id], triage.get(p.id), cfg) for p in shortlist
    ]
    stats.scored = len(scored)

    front, remainder = select_front_page(
        scored,
        top_n=int(fp_cfg["top_n"]),
        max_per_category=int(fp_cfg["max_per_category"]),
    )

    # Deep-dive output only decorates; it never changes the ordering, so a missing deep
    # dive costs you the three-sentence "why" and nothing else.
    for s in front:
        d = deep.get(s.id)
        if not d:
            continue
        s.why = d.get("why")
        s.touches = list(d.get("touches") or [])
        action = d.get("action")
        if action in ("read", "skim", "track", "cite"):
            s.action = action

    backlog = build_backlog(
        remainder, max_per_category=int(fp_cfg["backlog_max_per_category"])
    )

    failed = [h for h in health if not h.ok]
    under = [h for h in health if h.under_covered]
    degraded = bool(failed or under) or any(s.degraded for s in front)

    notes: list[str] = []
    for h in failed:
        notes.append(f"source {h.source} failed: {h.error}")
    for h in under:
        notes.append(
            f"source {h.source} returned {h.fetched}, below its expected minimum "
            f"of {h.expected_min}"
        )
    if any(s.degraded for s in front) and triage:
        notes.append("some entries fell back to lexical scoring: triage output was missing or invalid")
    if not triage:
        notes.append("run made without LLM judgement: ranking is lexical only")

    return Issue(
        week=week,
        window=Window(**{"from": start, "to": end}),
        generated_at=datetime.now(timezone.utc),
        source_health=health,
        stats=stats,
        front_page=front,
        blindspot=blindspot,
        backlog=backlog,
        now_published=now_published,
        weights=cfg.weights,
        degraded=degraded,
        notes=notes,
    )
