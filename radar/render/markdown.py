"""`digests/<week>.md` — the archive that survives the tooling (spec §7.2).

Permanent, greppable with `rg`, diffable, readable offline and in the GitHub mobile app.
A pure function of the issue JSON.
"""

from __future__ import annotations

from pathlib import Path

from ..models import Issue, Scored

ACTION_LABEL = {"read": "read", "skim": "skim", "track": "track", "cite": "cite"}


def _entry(s: Scored, n: int | None = None) -> list[str]:
    head = f"### {n}. " if n else "### "
    action = f"[{ACTION_LABEL[s.action]}] " if s.action else ""
    out = [f"{head}{action}{s.title}"]

    meta = [s.authors_short, s.venue, s.date.strftime("%-d %b"), f"`{s.category}`"]
    if s.links.get("code"):
        meta.append("code ✔")
    if s.watchlist_hit:
        meta.append(f"watchlist: {s.watchlist_hit}")
    out.append(" · ".join(m for m in meta if m))
    out.append("")

    body = s.why or s.reason
    if body:
        out.append(f"> {body}")
        out.append("")
    if s.touches:
        out.append("Touches: " + " · ".join(s.touches))
        out.append("")

    links = [f"[{k}]({v})" for k, v in s.links.items() if k in ("doi", "pdf", "code", "url")]
    if links:
        out.append(" · ".join(links))
    out.append("")
    return out


def render_markdown(issue: Issue) -> str:
    w = issue.window
    span = f"{w.from_.strftime('%-d %b')} – {w.to.strftime('%-d %b %Y')}"
    lines: list[str] = [f"# {issue.week} · {span}", ""]

    health = "All sources healthy."
    failed = [h.source for h in issue.source_health if not h.ok]
    under = [h.source for h in issue.source_health if h.under_covered]
    if failed:
        health = f"**DEGRADED** — sources failed: {', '.join(failed)}."
    elif under:
        health = f"**DEGRADED** — below expected volume: {', '.join(under)}."

    st = issue.stats
    lines += [
        f"_{st.new} new records → {st.shortlisted} screened → "
        f"{len(issue.front_page)} picks. {health}_",
        "",
    ]

    if issue.notes:
        lines += ["> " + n for n in issue.notes] + [""]

    if issue.front_page:
        lines += [f"## Top {len(issue.front_page)}", ""]
        for i, s in enumerate(issue.front_page, 1):
            lines += _entry(s, i)

    if issue.blindspot:
        b = issue.blindspot
        lines += ["## Blindspot", ""]
        lines += _entry(b)
        if b.connection:
            lines += [f"Connection: {b.connection}", ""]
        if b.confidence:
            lines += [f"Confidence: {b.confidence}", ""]

    if issue.now_published:
        lines += ["## Now published", ""]
        for np_ in issue.now_published:
            where = f" in {np_.journal}" if np_.journal else ""
            seen = f" (first seen {np_.first_seen_week})" if np_.first_seen_week else ""
            lines.append(f"- [{np_.title}](https://doi.org/{np_.journal_doi}){where}{seen}")
        lines.append("")

    if issue.backlog:
        lines += [
            f"<details><summary>Backlog · {issue.backlog_count} papers by category</summary>",
            "",
        ]
        for cat, items in issue.backlog.items():
            lines += [f"### {cat} ({len(items)})", ""]
            for s in items:
                link = s.links.get("doi") or s.links.get("url", "")
                lines.append(f"- **{s.title}** — {s.reason} — [link]({link})")
            lines.append("")
        lines += ["</details>", ""]

    return "\n".join(lines)


def write_markdown(root: Path, issue: Issue) -> Path:
    p = root / "digests" / f"{issue.week}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render_markdown(issue))
    return p
