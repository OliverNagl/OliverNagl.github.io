"""bioRxiv / medRxiv.

Verified live against the API (2026-09):

* `?category=<name>` **does** filter — 34 records vs 788 for the same 3-day window.
* Pages are **30 records**, not the 100 the design spec assumed. Cursor steps by 30.
* Category names use underscores for spaces: `synthetic_biology`.
* `published` is the literal string `"NA"` when there is no journal version yet, so a
  truthiness check on it is wrong.
* DOIs are now issued under the `10.64898` prefix, not `10.1101`. Nothing may assume either.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from ..models import Paper
from ..util import clean_abstract, find_code_url
from .base import Fetcher

log = logging.getLogger("radar.sources.biorxiv")

API = "https://api.biorxiv.org/details/{server}/{start}/{end}/{cursor}"
PAGE_SIZE = 30
DISPLAY_NAME = {"biorxiv": "bioRxiv", "medrxiv": "medRxiv"}
MAX_PAGES_PER_CATEGORY = 200        # safety valve; 6000 records for one category is a bug


class BioRxivSource:
    def __init__(self, name: str, cfg: dict, fetcher: Fetcher | None = None) -> None:
        self.name = name
        self.server = cfg.get("server", name)
        self.categories: list[str] = cfg.get("categories") or []
        self.fetcher = fetcher or Fetcher(min_interval=0.4)

    def fetch(self, start: date, end: date) -> list[Paper]:
        papers: dict[str, Paper] = {}
        failures: list[str] = []
        for cat in self.categories:
            try:
                for rec in self._fetch_category(cat, start, end):
                    p = self._to_paper(rec)
                    if p is None:
                        continue
                    # A record can be returned under more than one query; keep the newest
                    # version, which is the one with the most complete metadata.
                    prev = papers.get(p.id)
                    if prev is None or p.date >= prev.date:
                        papers[p.id] = p
            except Exception as exc:                      # noqa: BLE001
                # One category failing must not cost us the other seven.
                log.warning("%s category %s failed: %s", self.name, cat, exc)
                failures.append(cat)
        if failures and len(failures) == len(self.categories):
            raise RuntimeError(f"all {self.name} categories failed: {failures}")
        return list(papers.values())

    def _fetch_category(self, category: str, start: date, end: date):
        cursor = 0
        for _ in range(MAX_PAGES_PER_CATEGORY):
            url = API.format(
                server=self.server, start=start.isoformat(), end=end.isoformat(), cursor=cursor
            )
            data = self.fetcher.get_json(url, params={"category": category})
            msgs = data.get("messages") or [{}]
            if msgs[0].get("status") != "ok":
                break
            batch = data.get("collection") or []
            if not batch:
                break
            yield from batch
            total = int(msgs[0].get("total") or 0)
            cursor += PAGE_SIZE
            if cursor >= total:
                break

    def _to_paper(self, rec: dict) -> Paper | None:
        doi = (rec.get("doi") or "").strip()
        title = (rec.get("title") or "").strip()
        if not doi or not title:
            return None
        try:
            d = datetime.strptime(rec["date"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            return None

        # "Kushawah, G.; Aldas Bulos, V. D.; Bazzini, A. A."
        authors = [a.strip() for a in (rec.get("authors") or "").split(";") if a.strip()]
        abstract = clean_abstract(rec.get("abstract", ""))

        published = (rec.get("published") or "").strip()
        published_doi = published if published and published.upper() != "NA" else None

        return Paper(
            id=doi,
            doi=doi,
            title=clean_abstract(title),
            abstract=abstract,
            authors=authors,
            date=d,
            source=self.name,
            venue=DISPLAY_NAME.get(self.name, self.name),
            subject=(rec.get("category") or "").strip().lower(),
            url=f"https://doi.org/{doi}",
            pdf_url=f"https://www.{self.server}.org/content/{doi}v{rec.get('version', '1')}.full.pdf",
            code_url=find_code_url(abstract),
            published_doi=published_doi,
        )
