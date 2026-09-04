"""One-off scrapers for the two "good to know" sources that have no API.

Both targets are finite, curated and slow-moving — the PDB adds one Molecule of the Month
per month, the Ig Nobels land once a year — so they are harvested into `config/good_to_know/`
and read from disk thereafter. That keeps the weekly run down to at most one live request
(xkcd or Wikipedia) and means a scraper breaking never costs you a week.

Run `radar harvest` after a new Ig Nobel ceremony, or when the Molecule of the Month
index has moved on. Nothing here runs on the weekly path.
"""

from __future__ import annotations

import html
import logging
import re
from pathlib import Path

import yaml

from .sources.base import Fetcher

log = logging.getLogger("radar.harvest")

MOTM_INDEX = "https://pdb101.rcsb.org/motm/motm-by-date"
MOTM_PAGE = "https://pdb101.rcsb.org/motm/{n}"
IGNOBEL = "https://improbable.com/ig/winners/"

TAG = re.compile(r"<[^>]+>")


def _text(fragment: str) -> str:
    """Strip tags and collapse whitespace, the way both of these pages need.

    Tags are replaced by a space rather than removed, so that `a<em>b</em>` does not become
    `ab` — which then leaves gaps in front of punctuation and inside quotation marks that
    have to be closed up again.
    """
    s = re.sub(r"\s+", " ", html.unescape(TAG.sub(" ", fragment))).strip()
    s = re.sub(r"\s+([,.;:!?)\]])", r"\1", s)
    s = re.sub(r"([(\[])\s+", r"\1", s)
    s = re.sub(r"([“‘])\s+", r"\1", s)
    return re.sub(r"\s+([”’])", r"\1", s)


def _meta(page: str, prop: str) -> str:
    """Read one Open Graph property. Both attribute orders appear in the wild."""
    for pattern in (
        rf'<meta[^>]+property="{prop}"[^>]+content="([^"]*)"',
        rf'<meta[^>]+content="([^"]*)"[^>]+property="{prop}"',
    ):
        m = re.search(pattern, page, re.I)
        if m:
            return html.unescape(m.group(1)).strip()
    return ""


# ------------------------------------------------------------------ molecule of the month ----


def harvest_motm(fetcher: Fetcher) -> list[dict]:
    """Every Molecule of the Month, from the by-date index plus each entry's OG tags.

    The index gives the number and title; the entry page carries `og:image` (Goodsell's
    illustration) and `og:description` (a clean one-line summary), which is exactly the
    card this renders into. That is ~320 requests, which is why it is not on the weekly
    path.
    """
    index = fetcher.get(MOTM_INDEX).text
    seen: dict[int, str] = {}
    for href, num, title in re.findall(r'href="(/motm/(\d+))"[^>]*>([^<]{2,120})<', index):
        n = int(num)
        title = _text(title)
        # The index links each entry more than once; the first link carries the title.
        if title and n not in seen:
            seen[n] = title

    out: list[dict] = []
    for n in sorted(seen):
        try:
            page = fetcher.get(MOTM_PAGE.format(n=n)).text
        except Exception as exc:                          # noqa: BLE001
            log.warning("motm %d: %s", n, exc)
            continue
        image = _meta(page, "og:image")
        blurb = _meta(page, "og:description")
        if not image:
            log.debug("motm %d (%s): no og:image, skipping", n, seen[n])
            continue
        out.append(
            {
                "n": n,
                "title": seen[n],
                "url": MOTM_PAGE.format(n=n),
                "image": image,
                "blurb": blurb,
            }
        )
    log.info("harvested %d Molecule of the Month entries", len(out))
    return out


# ------------------------------------------------------------------------- ig nobel ----

YEAR_HEADING = re.compile(r"The (\d{4}) Ig Nobel Prize Winners")

# Thirty-five years of hand-written HTML, so the prize header comes in three shapes:
# the recent "IG NOBEL BIOMECHANICS PRIZE 2026 [UK, USA]"; the middle era's
# "MEDICINE PRIZE [ITALY]" with the citation after a <br/>; and the oldest, bare
# "NUTRITION: ...". The last two carry no year and rely on the heading above them.
MODERN = re.compile(r"IG NOBEL\s+(?P<category>[A-Z][A-Z \-&'\.]*?)\s*PRIZE\s+(?P<year>\d{4})")
LEGACY = re.compile(r"^\s*(?P<category>[A-Z][A-Z \-&'\.]{2,40}?)(?:\s+PRIZE)?\s*(?::|(?=\[))")
DOI = re.compile(r"doi\.org/(10\.[^\s<>\"]+)")


# The reference line runs on into whatever the editors appended that year.
# "WHO ATTENDED", "WHO CAME TO", "WHO TOOK PART IN" — the wording changes by year.
REF_TAIL = re.compile(r"\s*(?:WHO\b[^:]{0,40}:|NOTE:|REFERENCE:)", re.I)


def _clean_reference(reference: str) -> str:
    """Trim the citation down to the first reference and drop the page's punctuation.

    The bare DOI is wrapped in literal angle brackets that survive tag-stripping, and the
    editors append ceremony notes to the same line in some years.
    """
    reference = REF_TAIL.split(reference)[0]
    reference = re.sub(r"<[^<>]*>", " ", reference)       # "< doi.org/10.x/y >"
    reference = reference.replace("<", " ").replace(">", " ")
    return re.sub(r"\s+", " ", reference).strip(" ,;")


def _year_sections(page: str) -> list[tuple[int, str]]:
    """Split the page at each "The YYYY Ig Nobel Prize Winners" heading."""
    marks = [(m.start(), int(m.group(1))) for m in YEAR_HEADING.finditer(page)]
    if not marks:
        return []
    bounds = [m[0] for m in marks] + [len(page)]
    return [(marks[i][1], page[bounds[i] : bounds[i + 1]]) for i in range(len(marks))]


def harvest_ignobel(fetcher: Fetcher) -> list[dict]:
    """Every Ig Nobel prize, with the citation and the underlying paper's DOI.

    The prizes are real awards for real papers, so nothing here is invented: the citation
    is the committee's own wording and the reference is whatever the page links. Entries
    whose reference has no DOI are still kept — plenty of the older ones predate DOIs —
    but they render without a link to the paper itself.
    """
    page = fetcher.get(IGNOBEL).text
    page = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.S | re.I)

    out: list[dict] = []
    for year, section in _year_sections(page):
        # Kept in both forms: the DOI lives in an href, so it only survives in the raw
        # markup, while every pattern above matches against readable text.
        raw = re.findall(r"<p[^>]*>(.*?)</p>", section, flags=re.S)
        blocks = [_text(p) for p in raw]
        for i, block in enumerate(blocks):
            if block.startswith("REFERENCE:") or block.startswith("WHO ATTENDED"):
                continue

            m = MODERN.search(block)
            if m:
                category, prize_year = m.group("category"), int(m.group("year"))
                citation = block[m.end():]
            else:
                m = LEGACY.match(block)
                # A legacy header is only a header if a name follows the colon; the
                # page's prose paragraphs never open with a shouted category.
                if not m or len(block) - m.end() < 25:
                    continue
                category, prize_year = m.group("category"), year
                citation = block[m.end():]

            # Drop the optional "[UK, USA]" country list; the rest is the committee's
            # own wording, which is the part that is actually funny. From 2014 on the
            # references share the paragraph, so cut them off the end.
            citation = re.sub(r"^\s*\[[^\]]*\]\s*", "", citation)
            citation = re.split(r"REFERENCE:|WHO ATTENDED", citation)[0].strip(" —-–:")

            # The REFERENCE line is in this paragraph or one of the next two. Take the
            # text of the first one for display and the matching raw markup for the DOI.
            reference, reference_raw = "", ""
            for j in range(i, min(i + 3, len(blocks))):
                if "REFERENCE:" in blocks[j]:
                    reference = blocks[j].split("REFERENCE:", 1)[1].strip()
                    reference_raw = raw[j]
                    break
            reference = re.split(r"WHO ATTENDED|REFERENCE:", reference)[0].strip()

            if len(citation) < 25:
                continue
            doi_m = DOI.search(reference_raw)
            out.append(
                {
                    "category": _text(category).replace(" PRIZE", "").title(),
                    "year": prize_year,
                    "citation": citation,
                    "reference": _clean_reference(reference),
                    "doi": doi_m.group(1).rstrip(".>\"'") if doi_m else "",
                }
            )

    # The page repeats some prizes in its own summaries; keep the first of each.
    deduped: dict[tuple[str, int], dict] = {}
    for row in out:
        deduped.setdefault((row["category"], row["year"]), row)

    rows = sorted(deduped.values(), key=lambda r: (-r["year"], r["category"]))
    log.info("harvested %d Ig Nobel prizes across %d years", len(rows), len({r["year"] for r in rows}))
    return rows


# ---------------------------------------------------------------------------- write ----


def write_seeds(root: Path, motm: list[dict], ignobel: list[dict]) -> list[Path]:
    d = root / "config" / "good_to_know"
    d.mkdir(parents=True, exist_ok=True)
    written = []
    for name, rows, note in (
        ("motm.yaml", motm, "RCSB PDB-101 Molecule of the Month, by David S. Goodsell."),
        ("ignobel.yaml", ignobel, "Ig Nobel Prizes, Annals of Improbable Research."),
    ):
        if not rows:
            log.warning("%s: nothing harvested, leaving the existing file alone", name)
            continue
        p = d / name
        p.write_text(
            f"# Harvested by `radar harvest` — do not edit by hand.\n# {note}\n\n"
            + yaml.safe_dump(rows, sort_keys=False, allow_unicode=True, width=100)
        )
        written.append(p)
    return written
