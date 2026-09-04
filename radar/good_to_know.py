"""The "good to know" pick — the one thing on the page with no justification at all.

Every other section answers "why should you read this?" with a relevance score and a
verdict. The blindspot already covers *useful but oblique*. What was missing is something
with no bearing on the reader's work whatsoever, so this rotates weekly through four
sources that have nothing to do with protein design:

* **xkcd** — a random strip out of ~3200, carrying its hover text, which is the joke.
* **Molecule of the Month** — David Goodsell's watercolours for the PDB, the one source
  here that is at least about proteins.
* **Wikipedia** — a featured article from a random past day. Deliberately *not* the random
  article endpoint: true random Wikipedia is stubs, villages and footballers, whereas the
  featured feed is human-curated and lands on things like the huhu beetle.
* **Ig Nobel** — a real prize for a real paper, cited in the committee's own wording.

No model is involved anywhere. Two of the four are read from seed files harvested by
`radar harvest`, and the other two come from JSON APIs, so every field is either fetched
or on disk and none of it can be invented.

A failure is never an error: if a source is down or every candidate has been used, the
week simply has no pick and the section does not render.
"""

from __future__ import annotations

import json
import logging
import random
import re
from datetime import date, timedelta
from pathlib import Path

import yaml

from .config import Config
from .models import GoodToKnow
from .sources.base import Fetcher

log = logging.getLogger("radar.good_to_know")

XKCD_CURRENT = "https://xkcd.com/info.0.json"
XKCD_COMIC = "https://xkcd.com/{n}/info.0.json"
WIKI_FEATURED = "https://api.wikimedia.org/feed/v1/wikipedia/en/featured/{y}/{m:02d}/{d:02d}"

KINDS = ("xkcd", "motm", "wikipedia", "ignobel")
LEDGER = "data/good_to_know_seen.json"

# xkcd 404 is a joke: the comic does not exist and the endpoint returns 404.
XKCD_MISSING = {404}


# ------------------------------------------------------------------------- ledger ----


def read_ledger(root: Path) -> dict:
    p = root / LEDGER
    if not p.exists():
        return {"picks": []}
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError:
        log.warning("corrupt good-to-know ledger; starting a new one")
        return {"picks": []}
    return data if isinstance(data, dict) and "picks" in data else {"picks": []}


def record(root: Path, week: str, pick: GoodToKnow) -> None:
    """Remember a pick so it is never shown twice."""
    data = read_ledger(root)
    data["picks"] = [p for p in data["picks"] if p.get("url") != pick.url]
    data["picks"].append({"week": week, "kind": pick.kind, "url": pick.url})
    p = root / LEDGER
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2))


def _used(ledger: dict) -> set[str]:
    return {p.get("url", "") for p in ledger.get("picks", [])}


def _last_kind(ledger: dict) -> str | None:
    picks = ledger.get("picks") or []
    return picks[-1].get("kind") if picks else None


# ------------------------------------------------------------------------ sources ----


def _seed_rows(cfg: Config, name: str) -> list[dict]:
    """Read one harvested seed file. Missing means that source is simply unavailable."""
    p = cfg.root / "config" / "good_to_know" / name
    if not p.exists():
        log.debug("%s not harvested yet; skipping that source", name)
        return []
    rows = yaml.safe_load(p.read_text()) or []
    return [r for r in rows if isinstance(r, dict)]


def _pick_unused(rows: list[dict], key: str, used: set[str], rng: random.Random) -> dict | None:
    fresh = [r for r in rows if r.get(key) and r[key] not in used]
    return rng.choice(fresh) if fresh else None


def from_xkcd(cfg: Config, rng: random.Random, fetcher: Fetcher, used: set[str]) -> GoodToKnow | None:
    latest = int(fetcher.get_json(XKCD_CURRENT)["num"])
    for _ in range(8):                                    # a few draws, then give up
        n = rng.randint(1, latest)
        url = f"https://xkcd.com/{n}/"
        if n in XKCD_MISSING or url in used:
            continue
        c = fetcher.get_json(XKCD_COMIC.format(n=n))
        return GoodToKnow(
            kind="xkcd",
            title=c.get("safe_title") or c.get("title") or f"xkcd {n}",
            url=url,
            # The alt text is the second joke and the reason to render it at all.
            blurb=c.get("alt", ""),
            image=c.get("img"),
            image_alt=c.get("title", ""),
            credit="xkcd.com · CC BY-NC 2.5",
            note=f"xkcd #{n} · {c.get('year', '')}",
        )
    return None


def from_motm(cfg: Config, rng: random.Random, fetcher: Fetcher, used: set[str]) -> GoodToKnow | None:
    row = _pick_unused(_seed_rows(cfg, "motm.yaml"), "url", used, rng)
    if not row:
        return None
    return GoodToKnow(
        kind="motm",
        title=row["title"],
        url=row["url"],
        blurb=row.get("blurb", ""),
        image=row.get("image"),
        image_alt=row["title"],
        credit="RCSB PDB-101 · illustration by David S. Goodsell",
        note=f"Molecule of the Month #{row['n']}",
    )


def from_wikipedia(cfg: Config, rng: random.Random, fetcher: Fetcher, used: set[str]) -> GoodToKnow | None:
    """A featured article, or an "on this day" event, from a random past day.

    Both come from one request. The coin flip is worth it: the featured article is the
    better-written of the two but drifts towards film and sport biographies, whereas "on
    this day" is reliably historical, which is closer to the register this section wants.
    """
    years_back = int((cfg.profile.get("good_to_know") or {}).get("wikipedia_years_back", 8))
    today = date.today()
    for _ in range(5):
        day = today - timedelta(days=rng.randint(1, 365 * years_back))
        feed = fetcher.get_json(WIKI_FEATURED.format(y=day.year, m=day.month, d=day.day))

        events = [e for e in (feed.get("onthisday") or []) if e.get("pages")]
        if events and rng.random() < 0.5:
            event = rng.choice(events)
            page = event["pages"][0]
            url = ((page.get("content_urls") or {}).get("desktop") or {}).get("page", "")
            if url and url not in used:
                return GoodToKnow(
                    kind="wikipedia",
                    title=page.get("normalizedtitle") or page.get("title", ""),
                    url=url,
                    blurb=event.get("text", ""),
                    image=(page.get("thumbnail") or {}).get("source"),
                    image_alt=page.get("normalizedtitle", ""),
                    credit="Wikipedia · CC BY-SA 4.0",
                    note=f"On this day · {event.get('year', '')}",
                )

        tfa = feed.get("tfa")
        if not tfa:
            continue
        url = ((tfa.get("content_urls") or {}).get("desktop") or {}).get("page", "")
        if not url or url in used:
            continue
        return GoodToKnow(
            kind="wikipedia",
            title=tfa.get("normalizedtitle") or tfa.get("title", ""),
            url=url,
            blurb=tfa.get("extract", ""),
            image=(tfa.get("thumbnail") or {}).get("source"),
            image_alt=tfa.get("normalizedtitle", ""),
            credit="Wikipedia · CC BY-SA 4.0",
            note=f"Featured article · {day:%-d %B %Y}",
        )
    return None


def _ignobel_url(row: dict) -> str:
    """A real link for every prize.

    Most of the pre-2000 winners predate DOIs entirely, so those point at the winners
    page, anchored by year and category to stay unique — the ledger dedupes on this.
    """
    if row.get("doi"):
        return f"https://doi.org/{row['doi']}"
    slug = str(row.get("category", "")).lower().replace(" ", "-")
    return f"https://improbable.com/ig/winners/#{row.get('year', '')}-{slug}"


def _ignobel_clause(citation: str) -> str:
    """Lead with the joke.

    The committee's wording is "<a dozen names>, for <the funny part>", which buries the
    punchline under an author list on a card this size. The names are not lost — they are
    in the reference line underneath and on the other end of the link.
    """
    m = re.search(r",?\s+for\s+", citation)
    if not m:
        return citation
    clause = citation[m.end():].strip()
    return clause[:1].upper() + clause[1:] if clause else citation


def from_ignobel(cfg: Config, rng: random.Random, fetcher: Fetcher, used: set[str]) -> GoodToKnow | None:
    rows = [r for r in _seed_rows(cfg, "ignobel.yaml") if r.get("citation")]
    fresh = [r for r in rows if _ignobel_url(r) not in used]
    if not fresh:
        return None
    row = rng.choice(fresh)
    return GoodToKnow(
        kind="ignobel",
        title=f"Ig Nobel {row['category']} Prize, {row['year']}",
        url=_ignobel_url(row),
        blurb=_ignobel_clause(row["citation"]),
        credit="Ig Nobel Prizes · Annals of Improbable Research",
        note=f"Ig Nobel · {row['year']}",
        detail=row.get("reference", ""),
    )


FETCHERS = {
    "xkcd": from_xkcd,
    "motm": from_motm,
    "wikipedia": from_wikipedia,
    "ignobel": from_ignobel,
}


# -------------------------------------------------------------------------- pick ----


def pick(cfg: Config, week: str, *, fetcher: Fetcher | None = None) -> GoodToKnow | None:
    """One item for the week, or `None` if nothing could be had.

    The order is shuffled deterministically from the week key, with last week's kind sent
    to the back so the same source never lands twice running. The first source that
    returns something unused wins; anything that raises is skipped, because a comic being
    unreachable must never cost you a digest.
    """
    # An empty `kinds:` list means "switch the section off", which is not the same as the
    # key being absent — so this cannot collapse to `or KINDS`.
    configured = (cfg.profile.get("good_to_know") or {}).get("kinds")
    enabled = list(KINDS) if configured is None else list(configured)
    order = [k for k in enabled if k in FETCHERS]
    if not order:
        return None

    ledger = read_ledger(cfg.root)
    used = _used(ledger)
    last = _last_kind(ledger)

    rng = random.Random(week)
    rng.shuffle(order)
    if last in order and len(order) > 1:
        order.append(order.pop(order.index(last)))

    own_fetcher = fetcher is None
    fetcher = fetcher or Fetcher(min_interval=0.3, retries=2)
    try:
        for kind in order:
            try:
                got = FETCHERS[kind](cfg, rng, fetcher, used)
            except Exception as exc:                      # noqa: BLE001
                log.warning("good-to-know source %s failed: %s", kind, exc)
                continue
            if got is not None:
                log.info("good to know: %s — %s", got.kind, got.title)
                return got
        log.info("no good-to-know pick this week: every source was empty or unreachable")
        return None
    finally:
        if own_fetcher:
            fetcher.close()
