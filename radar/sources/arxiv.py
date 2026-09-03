"""arXiv Atom API.

Verified live (2026-09): plain `http` 301s to `https`; `submittedDate:[YYYYMMDDHHMM TO ...]`
range queries work and are far cheaper than client-side date filtering; the API asks for
roughly one request per three seconds.

Measured volume for a 10-day window: q-bio.BM 15, q-bio.QM 37, cond-mat.soft 111,
physics.bio-ph 40 — against cs.LG 1345, cs.AI 1682, stat.ML 166.

That ~3200 is the volume problem the design spec flags. Capping the fetch would "solve" it
by taking an arbitrary most-recent slice, which is a silent recall loss — precisely the
failure mode this radar exists to avoid. So the methodology gate is pushed into the *query*
instead: the same boost terms that categories.yaml uses for `gate_general_cs` are OR'd into
the search. Measured effect: 3193 records become 296, all of them gate-passing, with no
truncation anywhere.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime

from ..models import Paper
from ..util import clean_abstract, find_code_url
from .base import Fetcher

log = logging.getLogger("radar.sources.arxiv")

API = "https://export.arxiv.org/api/query"
NS = {
    "a": "http://www.w3.org/2005/Atom",
    "arx": "http://arxiv.org/schemas/atom",
    "os": "http://a9.com/-/spec/opensearch/1.1/",
}
PAGE_SIZE = 200

# arXiv's query parser chokes on punctuation inside field terms, so a term like "SE(3)"
# cannot go into the query. It is still applied locally by the prefilter to everything the
# gate returns; in practice such papers also say "equivariant", so the gate still sees them.
QUERY_SAFE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 \-]*")


class ArxivSource:
    name = "arxiv"

    def __init__(self, cfg: dict, gate_terms: list[str] | None = None,
                 fetcher: Fetcher | None = None) -> None:
        self.full = cfg.get("full_categories") or []
        self.gated = cfg.get("gated_categories") or []
        self.cap = int(cfg.get("max_results_per_category", 2000))
        self.gate_terms = gate_terms or []
        # arXiv asks for ~1 request / 3 s. Honour it: being throttled out mid-run is a
        # silent coverage loss, which is the failure mode we care most about.
        self.fetcher = fetcher or Fetcher(min_interval=3.1, timeout=60.0)

    # --- query construction ------------------------------------------------------

    @staticmethod
    def _date_clause(start: date, end: date) -> str:
        return (
            f"submittedDate:[{start.strftime('%Y%m%d')}0000 "
            f"TO {end.strftime('%Y%m%d')}2359]"
        )

    def _gate_clause(self) -> str | None:
        safe = [t for t in self.gate_terms if QUERY_SAFE.fullmatch(t)]
        dropped = [t for t in self.gate_terms if t not in safe]
        if dropped:
            log.debug("gate terms not expressible in an arXiv query: %s", dropped)
        if not safe:
            return None
        return "(" + " OR ".join(f'abs:"{t}"' for t in safe) + ")"

    # --- fetching ----------------------------------------------------------------

    def fetch(self, start: date, end: date) -> list[Paper]:
        papers: dict[str, Paper] = {}
        queries: list[tuple[str, str]] = []

        for cat in self.full:
            queries.append((cat, f"cat:{cat} AND {self._date_clause(start, end)}"))

        if self.gated:
            cats = " OR ".join(f"cat:{c}" for c in self.gated)
            q = f"({cats}) AND {self._date_clause(start, end)}"
            gate = self._gate_clause()
            if gate:
                q += f" AND {gate}"
            else:
                # No usable gate terms: fetching these categories in full would flood the
                # funnel, so skip them loudly rather than degrade the whole run silently.
                log.warning(
                    "no query-safe gate terms; skipping general-CS categories %s", self.gated
                )
                q = None
            if q:
                queries.append(("+".join(self.gated), q))

        failures: list[str] = []
        for label, q in queries:
            try:
                for p in self._run_query(q, label):
                    papers.setdefault(p.id, p)
            except Exception as exc:                      # noqa: BLE001
                log.warning("arxiv query %s failed: %s", label, exc)
                failures.append(label)

        if failures and len(failures) == len(queries):
            raise RuntimeError(f"all arxiv queries failed: {failures}")
        return list(papers.values())

    def _run_query(self, query: str, label: str):
        offset = 0
        seen = 0
        while offset < self.cap:
            r = self.fetcher.get(
                API,
                params={
                    "search_query": query,
                    "start": offset,
                    "max_results": min(PAGE_SIZE, self.cap - offset),
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                },
            )
            root = ET.fromstring(r.content)
            entries = root.findall("a:entry", NS)
            if not entries:
                break
            for e in entries:
                p = self._to_paper(e, label)
                if p is not None:
                    yield p
            total = int(root.findtext("os:totalResults", "0", NS) or 0)
            offset += len(entries)
            seen = total
            if offset >= total:
                break
        if seen > self.cap:
            log.warning(
                "arxiv %s: %d records available but capped at %d — raise "
                "max_results_per_category or tighten the gate",
                label, seen, self.cap,
            )

    def _to_paper(self, e: ET.Element, label: str) -> Paper | None:
        raw_id = (e.findtext("a:id", "", NS) or "").strip()
        title = clean_abstract(e.findtext("a:title", "", NS))
        if not raw_id or not title:
            return None
        # "http://arxiv.org/abs/2609.01132v1" -> "2609.01132v1"
        arxiv_id = raw_id.rsplit("/", 1)[-1]

        published = (e.findtext("a:published", "", NS) or "")[:10]
        try:
            d = datetime.strptime(published, "%Y-%m-%d").date()
        except ValueError:
            return None

        abstract = clean_abstract(e.findtext("a:summary", "", NS))
        authors = [
            (a.findtext("a:name", "", NS) or "").strip() for a in e.findall("a:author", NS)
        ]

        prim = e.find("arx:primary_category", NS)
        subject = (prim.get("term") if prim is not None else None) or label

        pdf = next(
            (lk.get("href") for lk in e.findall("a:link", NS) if lk.get("title") == "pdf"),
            f"https://arxiv.org/pdf/{arxiv_id}",
        )

        return Paper(
            id=f"arxiv:{arxiv_id}",
            doi=(e.findtext("arx:doi", None, NS) or None),
            title=title,
            abstract=abstract,
            authors=[a for a in authors if a],
            date=d,
            source="arxiv",
            venue="arXiv",
            subject=subject,
            url=f"https://arxiv.org/abs/{arxiv_id}",
            pdf_url=pdf,
            code_url=find_code_url(abstract),
        )
