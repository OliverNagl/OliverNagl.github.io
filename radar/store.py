"""Reading and writing the canonical artefacts under `data/`.

`data/issues/<week>.json` is the single source of truth. The markdown digest, the site and
the feed are all pure functions of it, so a rendering bug is never a data-loss event and
re-rendering the whole archive is one command (spec §5).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import Issue

# How long the front page may go without a successful run before the banner turns red.
# One lookback window plus a day of slack.
STALE_AFTER_DAYS = 11


def issues_dir(root: Path) -> Path:
    return root / "data" / "issues"


def issue_path(root: Path, week: str) -> Path:
    return issues_dir(root) / f"{week}.json"


def write_issue(root: Path, issue: Issue) -> Path:
    p = issue_path(root, issue.week)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(issue.model_dump_json(indent=2, by_alias=True) + "\n")
    return p


def read_issue(root: Path, week: str) -> Issue:
    return Issue.model_validate_json(issue_path(root, week).read_text())


def all_weeks(root: Path) -> list[str]:
    """Newest first."""
    d = issues_dir(root)
    if not d.exists():
        return []
    return sorted((f.stem for f in d.glob("*.json")), reverse=True)


def read_all_issues(root: Path) -> list[Issue]:
    out = []
    for w in all_weeks(root):
        try:
            out.append(read_issue(root, w))
        except Exception:                                 # noqa: BLE001
            # A malformed archive entry must not break the whole site build.
            continue
    return out


def write_index(root: Path, issues: list[Issue]) -> Path:
    """The weeks manifest that drives the archive page and the "latest" pointer."""
    p = root / "data" / "index.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "latest": issues[0].week if issues else None,
        "weeks": [
            {
                "week": i.week,
                "from": i.window.from_.isoformat(),
                "to": i.window.to.isoformat(),
                "generated_at": i.generated_at.isoformat(),
                "degraded": i.degraded,
                "stats": i.stats.model_dump(),
                "front_page": len(i.front_page),
                "backlog": i.backlog_count,
                "categories": sorted(i.backlog.keys()),
            }
            for i in issues
        ],
    }
    p.write_text(json.dumps(payload, indent=2) + "\n")
    return p


def write_status(root: Path, issue: Issue) -> Path:
    """The health beacon the front page renders as a banner.

    A literature monitor that silently stops working is worse than no monitor (spec §0.5).
    Under a scheduled Routine there is no workflow-failure notification to rely on, so the
    site itself has to make staleness visible: `index.html` compares `ran_at` against
    STALE_AFTER_DAYS and shows a red banner when the radar has gone quiet.
    """
    p = root / "data" / "status.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    under = [h.source for h in issue.source_health if h.under_covered]
    failed = [h.source for h in issue.source_health if not h.ok]

    if failed:
        message = f"Sources failed: {', '.join(failed)}. Coverage for this week is incomplete."
    elif under:
        message = f"Under expected volume: {', '.join(under)}. Coverage may be incomplete."
    else:
        message = "All sources healthy."

    p.write_text(
        json.dumps(
            {
                "week": issue.week,
                "ran_at": datetime.now(timezone.utc).isoformat(),
                "ok": not failed,
                "degraded": issue.degraded,
                "stale_after_days": STALE_AFTER_DAYS,
                "message": message,
                "failed_sources": failed,
                "under_covered_sources": under,
                "source_health": [h.model_dump() for h in issue.source_health],
                "notes": issue.notes,
            },
            indent=2,
        )
        + "\n"
    )
    return p


def read_status(root: Path) -> dict | None:
    p = root / "data" / "status.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


def is_stale(status: dict | None, now: datetime | None = None) -> bool:
    if not status or not status.get("ran_at"):
        return True
    now = now or datetime.now(timezone.utc)
    try:
        ran = datetime.fromisoformat(status["ran_at"])
    except ValueError:
        return True
    if ran.tzinfo is None:
        ran = ran.replace(tzinfo=timezone.utc)
    days = int(status.get("stale_after_days", STALE_AFTER_DAYS))
    return now - ran > timedelta(days=days)


def prune_raw(root: Path, keep_months: int) -> list[str]:
    """Drop raw archives older than the recall audit needs (spec §8 looks back 2-6 months)."""
    d = root / "data" / "raw"
    if not d.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=31 * keep_months)
    removed = []
    for f in d.glob("*.jsonl.gz"):
        if datetime.fromtimestamp(f.stat().st_mtime, timezone.utc) < cutoff:
            f.unlink()
            removed.append(f.name)
    return removed
