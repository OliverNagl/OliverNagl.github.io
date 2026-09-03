"""PubMed via E-utilities — the journal channel.

`esearch` to collect PMIDs per tracked journal and date window, then `efetch` in batches
for the records themselves. Verified live: a 10-day window over Nature alone returns ~150
records, so the journal list is the volume control here rather than any keyword gate.

NCBI allows 3 requests/second anonymously and 10 with an `NCBI_API_KEY`, which is why the
fetcher is throttled and the key is read from the environment when present.
"""

from __future__ import annotations

import logging
import os
import xml.etree.ElementTree as ET
from datetime import date, datetime

from ..models import Paper
from ..util import clean_abstract, find_code_url
from .base import Fetcher

log = logging.getLogger("radar.sources.pubmed")

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
FETCH_BATCH = 150
MAX_PER_JOURNAL = 400

MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


class PubMedSource:
    name = "pubmed"

    def __init__(self, cfg: dict, fetcher: Fetcher | None = None) -> None:
        self.journals: list[str] = cfg.get("journals") or []
        self.api_key = os.environ.get("NCBI_API_KEY", "")
        # 3 req/s anonymously, 10 with a key. Stay comfortably inside either.
        interval = 0.12 if self.api_key else 0.4
        self.fetcher = fetcher or Fetcher(min_interval=interval)

    def _params(self, **kw) -> dict:
        p = {"db": "pubmed", "retmode": "json", **kw}
        if self.api_key:
            p["api_key"] = self.api_key
        return p

    def fetch(self, start: date, end: date) -> list[Paper]:
        pmids: set[str] = set()
        failures: list[str] = []

        for journal in self.journals:
            term = (
                f'"{journal}"[Journal] AND '
                f'{start:%Y/%m/%d}:{end:%Y/%m/%d}[Date - Publication]'
            )
            try:
                data = self.fetcher.get_json(
                    ESEARCH, params=self._params(term=term, retmax=MAX_PER_JOURNAL)
                )
                ids = (data.get("esearchresult") or {}).get("idlist") or []
                pmids.update(ids)
            except Exception as exc:                      # noqa: BLE001
                log.warning("pubmed search failed for %s: %s", journal, exc)
                failures.append(journal)

        if failures and len(failures) == len(self.journals):
            raise RuntimeError(f"all pubmed journal searches failed: {failures[:5]}")
        if not pmids:
            return []

        papers: list[Paper] = []
        ids = sorted(pmids)
        for i in range(0, len(ids), FETCH_BATCH):
            chunk = ids[i : i + FETCH_BATCH]
            try:
                r = self.fetcher.get(
                    EFETCH,
                    params={
                        "db": "pubmed",
                        "id": ",".join(chunk),
                        "retmode": "xml",
                        **({"api_key": self.api_key} if self.api_key else {}),
                    },
                )
                root = ET.fromstring(r.content)
            except Exception as exc:                      # noqa: BLE001
                log.warning("pubmed efetch batch failed: %s", exc)
                continue
            for art in root.findall(".//PubmedArticle"):
                p = self._to_paper(art)
                if p is not None:
                    papers.append(p)

        return papers

    def _to_paper(self, art: ET.Element) -> Paper | None:
        pmid = art.findtext(".//PMID", "")
        title = clean_abstract("".join(art.find(".//ArticleTitle").itertext())
                               if art.find(".//ArticleTitle") is not None else "")
        if not pmid or not title:
            return None

        # Abstracts arrive as several labelled sections; join them in document order.
        parts = [
            "".join(node.itertext())
            for node in art.findall(".//Abstract/AbstractText")
        ]
        abstract = clean_abstract(" ".join(parts))

        authors = []
        for a in art.findall(".//Author"):
            last = a.findtext("LastName")
            initials = a.findtext("Initials") or ""
            if last:
                authors.append(f"{last} {initials}".strip())

        journal = art.findtext(".//Journal/Title") or art.findtext(".//ISOAbbreviation") or ""

        doi = None
        for eid in art.findall(".//ArticleId"):
            if eid.get("IdType") == "doi" and eid.text:
                doi = eid.text.strip()
                break

        return Paper(
            id=doi or f"pubmed:{pmid}",
            doi=doi,
            title=title,
            abstract=abstract,
            authors=authors,
            date=self._parse_date(art),
            source="pubmed",
            venue=journal,
            subject=journal,
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            code_url=find_code_url(abstract),
        )

    @staticmethod
    def _parse_date(art: ET.Element) -> date:
        for path in (".//ArticleDate", ".//PubDate", ".//DateRevised"):
            node = art.find(path)
            if node is None:
                continue
            y = node.findtext("Year")
            if not y:
                continue
            m = node.findtext("Month") or "1"
            d = node.findtext("Day") or "1"
            month = MONTHS.get(m[:3], None)
            if month is None:
                try:
                    month = int(m)
                except ValueError:
                    month = 1
            try:
                return date(int(y), month, int(d))
            except ValueError:
                return date(int(y), month, 1)
        return date(1970, 1, 1)
