"""`feed.xml` — the front page for people who live in a reader.

A pure function of the issue JSON, like every other surface.
"""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

from ..config import Config
from ..models import Issue

SITE = "https://olivernagl.github.io"
MAX_ITEMS = 60


def _item(issue: Issue, s, kind: str = "") -> str:
    link = s.links.get("doi") or s.links.get("url") or SITE
    body = s.why or s.reason or ""
    bits = [f"{s.authors_short} · {s.venue} · {s.date:%-d %b} · {s.category}"]
    if kind:
        bits.insert(0, kind)
    if s.action:
        bits.append(f"action: {s.action}")
    if s.touches:
        bits.append("touches: " + ", ".join(s.touches))
    desc = escape(f"{body}\n\n{' · '.join(bits)}")
    return f"""    <item>
      <title>{escape(s.title)}</title>
      <link>{escape(link)}</link>
      <guid isPermaLink="false">{escape(issue.week)}:{escape(s.id)}</guid>
      <pubDate>{format_datetime(datetime.combine(s.date, datetime.min.time(), timezone.utc))}</pubDate>
      <category>{escape(s.category)}</category>
      <description>{desc}</description>
    </item>"""


def render_feed(cfg: Config, issues: list[Issue]) -> str:
    items: list[str] = []
    for issue in issues:
        for s in issue.front_page:
            items.append(_item(issue, s))
        if issue.blindspot:
            items.append(_item(issue, issue.blindspot, kind="BLINDSPOT"))
        if len(items) >= MAX_ITEMS:
            break

    title = escape(cfg.profile.get("name", "Research radar"))
    now = format_datetime(datetime.now(timezone.utc))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{title}</title>
    <link>{SITE}/</link>
    <atom:link href="{SITE}/feed.xml" rel="self" type="application/rss+xml"/>
    <description>Weekly automated literature radar for protein design, self-assembly and structural machine learning.</description>
    <language>en</language>
    <lastBuildDate>{now}</lastBuildDate>
{chr(10).join(items[:MAX_ITEMS])}
  </channel>
</rss>
"""


def write_feed(cfg: Config, issues: list[Issue]) -> Path:
    p = cfg.root / "feed.xml"
    p.write_text(render_feed(cfg, issues))
    return p
