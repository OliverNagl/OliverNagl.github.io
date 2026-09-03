"""Small shared helpers: ISO weeks, text normalisation, code-link detection."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta

WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$")

# GitHub / Zenodo / GitLab links in an abstract. A method with released code is materially
# more actionable than one without, so this earns a ranking term (spec §2).
CODE_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:github\.com/[\w.\-]+/[\w.\-]+"
    r"|gitlab\.com/[\w.\-/]+"
    r"|zenodo\.org/(?:record|records|doi)/[\w.\-/]+"
    r"|huggingface\.co/[\w.\-]+/[\w.\-]+)",
    re.I,
)


def iso_week(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def parse_week(week: str) -> tuple[int, int]:
    m = WEEK_RE.match(week)
    if not m:
        raise ValueError(f"bad ISO week {week!r}; expected e.g. 2026-W36")
    return int(m.group(1)), int(m.group(2))


def week_end(week: str) -> date:
    """Sunday of the given ISO week — the inclusive end of the fetch window."""
    year, wk = parse_week(week)
    return date.fromisocalendar(year, wk, 7)


def week_window(week: str, lookback_days: int) -> tuple[date, date]:
    """The fetch window for a week.

    Deliberately longer than 7 days: the overlap plus `seen.sqlite` dedupe means indexing
    lag can never drop a paper on the floor (spec §9).
    """
    end = week_end(week)
    return end - timedelta(days=lookback_days - 1), end


def current_week(today: date | None = None) -> str:
    return iso_week(today or date.today())


def normalise_title(title: str) -> str:
    """Aggressive normalisation for fuzzy title dedupe: strip accents, punctuation and
    whitespace so that a preprint and its journal version collide."""
    t = unicodedata.normalize("NFKD", title or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower()
    t = re.sub(r"<[^>]+>", " ", t)      # some feeds leave markup in titles
    t = re.sub(r"[^a-z0-9]+", "", t)
    return t


def find_code_url(text: str) -> str | None:
    m = CODE_URL_RE.search(text or "")
    if not m:
        return None
    return m.group(0).rstrip(").,;")


def clean_abstract(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def truncate(text: str, words: int) -> str:
    parts = (text or "").split()
    if len(parts) <= words:
        return text or ""
    return " ".join(parts[:words]) + "…"


def compile_term(term: str) -> re.Pattern[str]:
    """Compile a config term to a pattern anchored at a word start.

    Terms are matched as *prefixes*, deliberately: `self-assembl` should catch
    assembly/assembling/assembled, and `molecul` should catch molecular/molecule, without
    needing a stemmer. But an unanchored substring search is badly wrong for short terms —
    `rna` matches inside "inte**rna**l" and "gove**rna**nce", which was silently admitting
    unrelated CS papers through the domain gate.

    Requiring a word boundary at the *start* only fixes that while keeping prefix matching.
    """
    return re.compile(r"(?<![0-9A-Za-z])" + re.escape(term), re.I)


def compile_terms(terms) -> list[tuple[str, re.Pattern[str]]]:
    return [(t, compile_term(t)) for t in terms]


def first_term_hit(text: str, compiled: list[tuple[str, re.Pattern[str]]]) -> str | None:
    for term, pat in compiled:
        if pat.search(text):
            return term
    return None
