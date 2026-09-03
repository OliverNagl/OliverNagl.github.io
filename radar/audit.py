"""The recall audit (spec §8).

This is the part that directly addresses "nothing important gets overlooked", and it is the
only component that can find misses you never knew about — the gold set can only check
papers you already discovered some other way.

Take papers the radar *rejected* 2-6 months ago, ask OpenAlex what happened to them since,
and report anything that crossed a citation threshold or reached a tracked journal as a
**miss**, with the reason it was filtered out. An invisible failure mode becomes a monthly
list of concrete bugs.

Two months is the floor because citations take that long to accumulate at all; six is the
ceiling because `data/raw` is pruned past that and because a bug you find a year late is no
longer actionable.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path

from .collect import available_raw_weeks, read_raw
from .config import Config
from .models import Paper
from .prefilter import judge
from .resolve import OPENALEX
from .sources.base import Fetcher
from .util import parse_week

log = logging.getLogger("radar.audit")

DEFAULT_MIN_AGE_DAYS = 60
DEFAULT_MAX_AGE_DAYS = 190
DEFAULT_CITATION_THRESHOLD = 5
BATCH = 50


def _week_date(week: str) -> date:
    year, wk = parse_week(week)
    return date.fromisocalendar(year, wk, 7)


def weeks_in_window(
    root: Path, *, min_age_days: int, max_age_days: int, today: date | None = None
) -> list[str]:
    today = today or date.today()
    out = []
    for w in available_raw_weeks(root):
        try:
            age = (today - _week_date(w)).days
        except ValueError:
            continue
        if min_age_days <= age <= max_age_days:
            out.append(w)
    return out


def _lookup(fetcher: Fetcher, dois: list[str], mailto: str) -> dict[str, dict]:
    """Batch citation counts and publication status. OpenAlex takes a piped OR filter,
    which keeps this to one request per 50 papers rather than one per paper."""
    if not dois:
        return {}
    params = {
        "filter": "doi:" + "|".join(dois),
        "per-page": len(dois),
        "select": "doi,cited_by_count,primary_location,publication_year,title",
    }
    if mailto:
        params["mailto"] = mailto
    try:
        data = fetcher.get_json(OPENALEX.rstrip("/"), params=params)
    except Exception as exc:                              # noqa: BLE001
        log.warning("openalex batch lookup failed: %s", exc)
        return {}
    out = {}
    for w in data.get("results") or []:
        doi = (w.get("doi") or "").replace("https://doi.org/", "").lower()
        if doi:
            out[doi] = w
    return out


def run_audit(
    cfg: Config,
    *,
    min_age_days: int = DEFAULT_MIN_AGE_DAYS,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    citation_threshold: int = DEFAULT_CITATION_THRESHOLD,
    today: date | None = None,
) -> dict:
    weeks = weeks_in_window(
        cfg.root, min_age_days=min_age_days, max_age_days=max_age_days, today=today
    )
    if not weeks:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "weeks": [],
            "checked": 0,
            "misses": [],
            "note": (
                f"no raw archives aged {min_age_days}-{max_age_days} days yet; "
                "the audit becomes meaningful after a couple of months of runs"
            ),
        }

    tracked = {j.lower() for j in cfg.source_cfg("pubmed").get("journals", [])}
    fetcher = Fetcher(min_interval=0.15)
    mailto = cfg.source_cfg("openalex").get("mailto", "")

    rejected: list[tuple[Paper, str, str, str]] = []   # paper, week, rule, reason
    for week in weeks:
        try:
            papers = read_raw(cfg.root, week)
        except FileNotFoundError:
            continue
        for p in papers:
            if not p.doi:
                continue
            v = judge(p, cfg)
            if not v.passed:
                rejected.append((p, week, v.failed_rule or "unknown", v.reason))

    log.info("auditing %d rejected papers from %s", len(rejected), ", ".join(weeks))

    misses = []
    checked = 0
    for i in range(0, len(rejected), BATCH):
        chunk = rejected[i : i + BATCH]
        found = _lookup(fetcher, [p.doi for p, _, _, _ in chunk], mailto)
        checked += len(chunk)
        for paper, week, rule, reason in chunk:
            w = found.get((paper.doi or "").lower())
            if not w:
                continue
            cites = int(w.get("cited_by_count") or 0)
            venue = (
                ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
                or ""
            )
            in_tracked_journal = venue.lower() in tracked

            if cites < citation_threshold and not in_tracked_journal:
                continue

            misses.append(
                {
                    "doi": paper.doi,
                    "title": paper.title,
                    "week": week,
                    "source": paper.source,
                    "rejected_by_rule": rule,
                    "rejected_because": reason,
                    "cited_by_count": cites,
                    "venue": venue,
                    "in_tracked_journal": in_tracked_journal,
                    "url": f"https://doi.org/{paper.doi}",
                }
            )

    misses.sort(key=lambda m: (-m["cited_by_count"], m["title"]))

    # Which *rule* is costing the most recall — grouped by the rule id, not the reason
    # text, because the rule is the thing you can actually go and change.
    by_rule: dict[str, int] = {}
    for m in misses:
        by_rule[m["rejected_by_rule"]] = by_rule.get(m["rejected_by_rule"], 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "weeks": weeks,
        "window_days": [min_age_days, max_age_days],
        "citation_threshold": citation_threshold,
        "checked": checked,
        "miss_count": len(misses),
        "misses_by_rule": dict(sorted(by_rule.items(), key=lambda kv: -kv[1])),
        "misses": misses[:100],
    }


def write_audit(root: Path, report: dict) -> Path:
    p = root / "data" / "eval" / "audit.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, indent=2) + "\n")
    return p
