"""Resolve a DOI or arXiv id to a full `Paper`, for the gold set and the recall audit.

OpenAlex first — one call returns title, abstract, venue, authors and citation count, which
is everything both callers need. Crossref and arXiv are fallbacks for records OpenAlex has
not indexed.

Results are cached to `eval/cache/`. That is not an optimisation: it is what makes
`radar eval` runnable offline and deterministic, so you can iterate on `categories.yaml`
in a tight loop without hammering anyone's API or getting different answers each time.
"""

from __future__ import annotations

import json
import logging
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path

from .models import Paper
from .sources.base import Fetcher
from .util import clean_abstract, find_code_url

log = logging.getLogger("radar.resolve")

OPENALEX = "https://api.openalex.org/works/"
CROSSREF = "https://api.crossref.org/works/"
ARXIV = "https://export.arxiv.org/api/query"
ARXIV_ID = re.compile(r"^(?:arxiv:)?(\d{4}\.\d{4,5})(v\d+)?$", re.I)


def cache_key(ident: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", ident).strip("_")[:120]


def _abstract_from_inverted(index: dict | None) -> str:
    """OpenAlex stores abstracts as {word: [positions]} for copyright reasons."""
    if not index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, spots in index.items():
        for s in spots:
            positions.append((s, word))
    positions.sort()
    return " ".join(w for _, w in positions)


class Resolver:
    def __init__(self, cache_dir: Path, mailto: str = "", fetcher: Fetcher | None = None) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.mailto = mailto
        self._fetcher = fetcher
        self.offline_misses: list[str] = []

    @property
    def fetcher(self) -> Fetcher:
        if self._fetcher is None:
            self._fetcher = Fetcher(min_interval=0.3)
        return self._fetcher

    def resolve(self, ident: str, *, offline: bool = False) -> Paper | None:
        cached = self._read_cache(ident)
        if cached is not None:
            return cached
        if offline:
            self.offline_misses.append(ident)
            return None

        for attempt in (self._from_openalex, self._from_crossref, self._from_arxiv):
            try:
                paper = attempt(ident)
            except Exception as exc:                      # noqa: BLE001
                log.debug("%s failed for %s: %s", attempt.__name__, ident, exc)
                continue
            if paper is not None:
                self._write_cache(ident, paper)
                return paper

        log.warning("could not resolve %s from OpenAlex, Crossref or arXiv", ident)
        return None

    # --- cache --------------------------------------------------------------------

    def _cache_path(self, ident: str) -> Path:
        return self.cache_dir / f"{cache_key(ident)}.json"

    def _read_cache(self, ident: str) -> Paper | None:
        p = self._cache_path(ident)
        if not p.exists():
            return None
        try:
            return Paper.model_validate_json(p.read_text())
        except Exception:                                 # noqa: BLE001
            log.warning("corrupt cache entry %s; refetching", p.name)
            return None

    def _write_cache(self, ident: str, paper: Paper) -> None:
        self._cache_path(ident).write_text(paper.model_dump_json(indent=2))

    # --- backends -----------------------------------------------------------------

    def _from_openalex(self, ident: str) -> Paper | None:
        m = ARXIV_ID.match(ident)
        key = f"arxiv:{m.group(1)}" if m else f"doi:{ident}"
        params = {"mailto": self.mailto} if self.mailto else None
        w = self.fetcher.get_json(OPENALEX + key, params=params)
        if not w or not w.get("title"):
            return None

        loc = w.get("primary_location") or {}
        src = loc.get("source") or {}
        pub = w.get("publication_date") or ""
        try:
            d = datetime.strptime(pub, "%Y-%m-%d").date()
        except ValueError:
            d = date(int(w.get("publication_year") or 1970), 1, 1)

        abstract = clean_abstract(_abstract_from_inverted(w.get("abstract_inverted_index")))
        authors = [
            (a.get("author") or {}).get("display_name", "")
            for a in (w.get("authorships") or [])
        ]
        doi = (w.get("doi") or "").replace("https://doi.org/", "") or None

        return Paper(
            id=doi or ident,
            doi=doi,
            title=clean_abstract(w["title"]),
            abstract=abstract,
            authors=[a for a in authors if a],
            date=d,
            source="openalex",
            venue=src.get("display_name") or "",
            subject=(w.get("primary_topic") or {}).get("display_name", "") or "",
            url=w.get("doi") or loc.get("landing_page_url") or "",
            pdf_url=loc.get("pdf_url"),
            code_url=find_code_url(abstract),
        )

    def _from_crossref(self, ident: str) -> Paper | None:
        if ARXIV_ID.match(ident):
            return None
        m = self.fetcher.get_json(CROSSREF + ident).get("message") or {}
        title = (m.get("title") or [""])[0]
        if not title:
            return None
        parts = ((m.get("issued") or {}).get("date-parts") or [[1970, 1, 1]])[0]
        parts = list(parts) + [1, 1]
        abstract = clean_abstract(m.get("abstract", ""))
        authors = [
            f"{a.get('family', '')} {a.get('given', '')}".strip()
            for a in (m.get("author") or [])
        ]
        return Paper(
            id=ident, doi=ident,
            title=clean_abstract(title),
            abstract=abstract,
            authors=[a for a in authors if a],
            date=date(int(parts[0]), int(parts[1]), int(parts[2])),
            source="crossref",
            venue=(m.get("container-title") or [""])[0],
            url=f"https://doi.org/{ident}",
            code_url=find_code_url(abstract),
        )

    def _from_arxiv(self, ident: str) -> Paper | None:
        m = ARXIV_ID.match(ident)
        if not m:
            return None
        aid = m.group(1)
        r = self.fetcher.get(ARXIV, params={"id_list": aid, "max_results": 1})
        ns = {"a": "http://www.w3.org/2005/Atom"}
        e = ET.fromstring(r.content).find("a:entry", ns)
        if e is None:
            return None
        title = clean_abstract(e.findtext("a:title", "", ns))
        if not title:
            return None
        abstract = clean_abstract(e.findtext("a:summary", "", ns))
        published = (e.findtext("a:published", "", ns) or "")[:10]
        return Paper(
            id=f"arxiv:{aid}",
            title=title,
            abstract=abstract,
            authors=[a.findtext("a:name", "", ns) for a in e.findall("a:author", ns)],
            date=datetime.strptime(published, "%Y-%m-%d").date(),
            source="arxiv",
            venue="arXiv",
            subject="",
            url=f"https://arxiv.org/abs/{aid}",
            code_url=find_code_url(abstract),
        )


def citation_count(fetcher: Fetcher, doi: str, mailto: str = "") -> int | None:
    """Used by the monthly recall audit to spot rejected papers that later mattered."""
    try:
        params = {"mailto": mailto} if mailto else None
        w = fetcher.get_json(f"{OPENALEX}doi:{doi}", params=params)
        return int(w.get("cited_by_count") or 0)
    except Exception:                                     # noqa: BLE001
        return None


def load_json(path: Path) -> dict:
    return json.loads(Path(path).read_text())
