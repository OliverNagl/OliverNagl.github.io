"""Static site rendering.

`index.html` is rendered here rather than assembled by `fetch` in the browser: the surface
read every week should be plain HTML that needs zero JavaScript and paints on first byte.
Only `archive.html` and `tuning.html` are JS-driven, because search and live re-ranking
genuinely need it.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import Config
from ..models import Issue
from ..store import all_weeks, is_stale, read_all_issues, read_issue, read_status
from ..util import truncate

SITE_META = {
    "owner": "Oliver Nagl",
    "email": "olnagl@ethz.ch",
    "github": "OliverNagl",
    "linkedin": "https://www.linkedin.com/in/oliver-nagl-41a40a1b0/",
}


def env_for(root: Path) -> Environment:
    env = Environment(
        loader=FileSystemLoader(root / "templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["urlencode"] = lambda s: __import__("urllib.parse", fromlist=["quote"]).quote(str(s))
    return env


def category_names(cfg: Config) -> dict[str, str]:
    return {c.id: c.name for c in cfg.categories}


def build_banner(issue: Issue | None, status: dict | None) -> dict | None:
    """The health beacon rendered at the top of the front page.

    Three states, in order of severity: the radar has gone quiet (red), a source failed or
    under-delivered (amber), everything healthy (green). Silence is never a valid state
    (spec §0.5).
    """
    if is_stale(status):
        ran = (status or {}).get("ran_at", "never")
        return {
            "level": "bad",
            "message": (
                f"The radar has not completed a run since {ran}. "
                "Coverage is incomplete — check the scheduled routine."
            ),
            "details": [],
        }
    if issue is None:
        return None

    failed = [h for h in issue.source_health if not h.ok]
    under = [h for h in issue.source_health if h.under_covered]

    if failed or under:
        details = [f"{h.source} failed: {h.error}" for h in failed]
        details += [
            f"{h.source} returned {h.fetched}, below its expected minimum of {h.expected_min}"
            for h in under
        ]
        return {
            "level": "warn",
            "message": "This run was degraded — some of the literature was not seen.",
            "details": details,
        }

    if issue.notes:
        return {"level": "warn", "message": issue.notes[0], "details": issue.notes[1:]}

    fetched = sum(h.fetched for h in issue.source_health)
    return {
        "level": "ok",
        "message": f"All {len(issue.source_health)} sources healthy · {fetched:,} records fetched.",
        "details": [],
    }


def render_index(cfg: Config, issue: Issue | None) -> str:
    env = env_for(cfg.root)
    status = read_status(cfg.root)
    return env.get_template("index.html").render(
        page_id="week",
        base="",
        title=(f"{issue.week} · Research radar" if issue else "Research radar"),
        description=(
            "Weekly automated literature radar for protein design, self-assembly and "
            "structural machine learning."
        ),
        profile_name=cfg.profile.get("name", "Research radar"),
        issue=issue,
        banner=build_banner(issue, status),
        cat_names=category_names(cfg),
        max_per_category=cfg.profile["front_page"]["max_per_category"],
        **SITE_META,
    )


def render_static(cfg: Config, name: str, page_id: str, title: str, description: str, **kw) -> str:
    env = env_for(cfg.root)
    return env.get_template(name).render(
        page_id=page_id, base="", title=title, description=description, **SITE_META, **kw
    )


def build_search_index(cfg: Config, issues: list[Issue]) -> dict:
    """The flat document array the archive page searches.

    Abstracts are truncated hard: the index is downloaded in full by every visitor. At ~86
    documents a week that reaches roughly 4 MB raw / 1 MB gzipped after a year, which is
    still one cached fetch — but if it outgrows that, split it by year and have the archive
    page load the current one first.
    """
    docs = []
    for issue in issues:
        entries = [(s, True) for s in issue.front_page]
        if issue.blindspot:
            entries.append((issue.blindspot, True))
        for items in issue.backlog.values():
            entries.extend((s, False) for s in items)

        for s, front in entries:
            docs.append(
                {
                    "id": f"{issue.week}::{s.id}",
                    "week": issue.week,
                    "title": s.title,
                    "authors": s.authors_short,
                    "venue": s.venue,
                    "date": s.date.isoformat(),
                    "category": s.category,
                    "action": s.action or "",
                    "score": round(s.score, 3),
                    "why": s.why or "",
                    "reason": s.reason or "",
                    "touches": s.touches,
                    "abstract": truncate(s.abstract, 40),
                    "code": bool(s.links.get("code")),
                    "watchlist": s.watchlist_hit or "",
                    "front": front,
                    "url": s.links.get("doi") or s.links.get("url", ""),
                }
            )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "categories": category_names(cfg),
        "count": len(docs),
        "docs": docs,
    }


def build_site(cfg: Config, week: str | None = None) -> list[Path]:
    """Re-render every static surface from `data/`. Safe to run at any time."""
    root = cfg.root
    written: list[Path] = []

    weeks = all_weeks(root)
    target = week or (weeks[0] if weeks else None)
    issue = read_issue(root, target) if target else None

    (root / "index.html").write_text(render_index(cfg, issue))
    written.append(root / "index.html")

    issues = read_all_issues(root)

    idx = build_search_index(cfg, issues)
    p = root / "data" / "search-index.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(idx, separators=(",", ":")))
    written.append(p)

    for name, page_id, title, desc in (
        ("archive.html", "archive", "Archive · Research radar",
         "Search every paper the radar has surfaced."),
        ("tuning.html", "tuning", "Tuning · Research radar",
         "Tune the ranking weights and check the radar against papers it should have found."),
        ("projects.html", "projects", "Projects · Oliver Nagl", "Selected projects."),
    ):
        (root / name).write_text(render_static(cfg, name, page_id, title, desc))
        written.append(root / name)

    return written
