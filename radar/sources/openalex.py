"""OpenAlex — the ChemRxiv channel and the catch-all supplement.

Two jobs in one source, because OpenAlex answers both with the same query shape:

* **ChemRxiv.** Its own public API sits behind a Cloudflare challenge and returns 403 to
  any script, so it is unreachable directly. OpenAlex indexes it (~244 records per 10-day
  window) and hands back abstracts, which is everything the funnel needs.
* **The supplement.** Targeted phrase searches that catch venues the other sources miss.

Abstracts arrive as an inverted index (OpenAlex does not redistribute abstract text
directly); `radar.resolve` has the reconstruction and it is reused here.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from ..models import Paper
from ..resolve import _abstract_from_inverted
from ..util import clean_abstract, find_code_url
from .base import Fetcher

log = logging.getLogger("radar.sources.openalex")

API = "https://api.openalex.org/works"
PER_PAGE = 200
MAX_PAGES = 10


class OpenAlexSource:
    name = "openalex"

    def __init__(self, cfg: dict, fetcher: Fetcher | None = None) -> None:
        # {"ChemRxiv": "S4393918830", ...}
        self.source_ids: dict[str, str] = cfg.get("source_ids") or {}
        self.searches: list[str] = cfg.get("searches") or []
        self.mailto: str = cfg.get("mailto", "")
        self.fetcher = fetcher or Fetcher(min_interval=0.15)

    def fetch(self, start: date, end: date) -> list[Paper]:
        papers: dict[str, Paper] = {}
        queries: list[tuple[str, dict]] = []

        window = f"from_publication_date:{start:%Y-%m-%d},to_publication_date:{end:%Y-%m-%d}"

        for label, sid in self.source_ids.items():
            queries.append((label, {"filter": f"primary_location.source.id:{sid},{window}"}))
        for phrase in self.searches:
            queries.append(
                (f"search:{phrase}", {"filter": window, "search": phrase})
            )

        failures: list[str] = []
        for label, params in queries:
            try:
                for p in self._run(params, label):
                    papers.setdefault(p.id, p)
            except Exception as exc:                      # noqa: BLE001
                log.warning("openalex query %s failed: %s", label, exc)
                failures.append(label)

        if failures and queries and len(failures) == len(queries):
            raise RuntimeError(f"all openalex queries failed: {failures[:5]}")
        return list(papers.values())

    def _run(self, params: dict, label: str):
        cursor = "*"
        for _ in range(MAX_PAGES):
            q = {**params, "per-page": PER_PAGE, "cursor": cursor}
            if self.mailto:
                q["mailto"] = self.mailto
            data = self.fetcher.get_json(API, params=q)
            results = data.get("results") or []
            if not results:
                return
            for w in results:
                p = self._to_paper(w, label)
                if p is not None:
                    yield p
            cursor = (data.get("meta") or {}).get("next_cursor")
            if not cursor:
                return

    def _to_paper(self, w: dict, label: str) -> Paper | None:
        title = w.get("title")
        if not title:
            return None
        try:
            d = datetime.strptime(w.get("publication_date", ""), "%Y-%m-%d").date()
        except ValueError:
            return None

        abstract = clean_abstract(_abstract_from_inverted(w.get("abstract_inverted_index")))
        loc = w.get("primary_location") or {}
        src = loc.get("source") or {}
        doi = (w.get("doi") or "").replace("https://doi.org/", "") or None
        authors = [
            (a.get("author") or {}).get("display_name", "")
            for a in (w.get("authorships") or [])
        ]

        return Paper(
            id=doi or w.get("id", ""),
            doi=doi,
            title=clean_abstract(title),
            abstract=abstract,
            authors=[a for a in authors if a],
            date=d,
            source="openalex",
            venue=src.get("display_name") or label,
            subject=(w.get("primary_topic") or {}).get("display_name", "") or "",
            url=w.get("doi") or loc.get("landing_page_url") or "",
            pdf_url=loc.get("pdf_url"),
            code_url=find_code_url(abstract),
        )
