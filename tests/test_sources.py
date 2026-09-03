"""Source parsing, against captured response shapes.

These pin the API quirks that cost real debugging time — a spec assumption being wrong is
exactly the kind of thing that silently halves coverage.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date

from radar.audit import weeks_in_window
from radar.sources.arxiv import ArxivSource
from radar.sources.biorxiv import BioRxivSource
from radar.sources.pubmed import PubMedSource


class TestBioRxiv:
    def _src(self):
        return BioRxivSource("biorxiv", {"server": "biorxiv", "categories": []}, fetcher=object())

    def _record(self, **kw):
        rec = {
            "title": "Programmable de novo design of protein cages",
            "authors": "Li, Z.; Hsia, Y.; Baker, D.",
            "doi": "10.64898/2026.08.25.747085",
            "date": "2026-08-26",
            "version": "1",
            "category": "bioengineering",
            "abstract": "We design cages. Code at https://github.com/x/y for reuse.",
            "published": "NA",
        }
        rec.update(kw)
        return rec

    def test_parses_a_record(self):
        p = self._src()._to_paper(self._record())
        assert p.doi == "10.64898/2026.08.25.747085"
        assert p.date == date(2026, 8, 26)
        assert p.authors == ["Li, Z.", "Hsia, Y.", "Baker, D."]
        assert p.venue == "bioRxiv"                    # not the lowercase server name

    def test_published_NA_is_not_a_journal_doi(self):
        # The field is the literal string "NA", so a truthiness check would report every
        # preprint as newly published.
        assert self._src()._to_paper(self._record()).published_doi is None

    def test_published_doi_is_picked_up_when_present(self):
        p = self._src()._to_paper(self._record(published="10.1038/s41586-026-1"))
        assert p.published_doi == "10.1038/s41586-026-1"

    def test_does_not_assume_the_old_doi_prefix(self):
        # bioRxiv moved from 10.1101 to 10.64898; both must parse.
        for doi in ("10.1101/2024.01.01.000001", "10.64898/2026.08.25.747085"):
            assert self._src()._to_paper(self._record(doi=doi)).doi == doi

    def test_detects_a_code_link_in_the_abstract(self):
        assert self._src()._to_paper(self._record()).code_url == "https://github.com/x/y"

    def test_drops_records_missing_a_doi_or_title(self):
        assert self._src()._to_paper(self._record(doi="")) is None
        assert self._src()._to_paper(self._record(title="")) is None

    def test_drops_records_with_an_unparseable_date(self):
        assert self._src()._to_paper(self._record(date="not-a-date")) is None


class TestArxivGate:
    """The general-CS gate is pushed into the query; capping the fetch instead would
    silently drop papers, which is the failure this radar exists to avoid."""

    def _src(self, terms):
        return ArxivSource(
            {"full_categories": ["q-bio.BM"], "gated_categories": ["cs.LG", "cs.AI"]},
            gate_terms=terms, fetcher=object(),
        )

    def test_gate_clause_quotes_each_term(self):
        clause = self._src(["flow matching", "equivariant"])._gate_clause()
        assert clause == '(abs:"flow matching" OR abs:"equivariant")'

    def test_terms_with_punctuation_are_excluded_from_the_query(self):
        # arXiv's parser chokes on "SE(3)"; the prefilter still applies it locally.
        clause = self._src(["SE(3)", "equivariant"])._gate_clause()
        assert "SE(3)" not in clause
        assert "equivariant" in clause

    def test_no_usable_terms_yields_no_clause(self):
        assert self._src(["SE(3)", "T=3"])._gate_clause() is None

    def test_date_clause_is_inclusive_of_both_ends(self):
        c = ArxivSource._date_clause(date(2026, 8, 24), date(2026, 9, 2))
        assert c == "submittedDate:[202608240000 TO 202609022359]"


class TestPubMed:
    XML = """<PubmedArticleSet><PubmedArticle><MedlineCitation>
      <PMID>42687030</PMID>
      <Article>
        <Journal><Title>Nature</Title></Journal>
        <ArticleTitle>De novo design of <i>protein</i> cages</ArticleTitle>
        <Abstract>
          <AbstractText Label="BACKGROUND">Cages are useful.</AbstractText>
          <AbstractText Label="RESULTS">We made some.</AbstractText>
        </Abstract>
        <AuthorList>
          <Author><LastName>King</LastName><Initials>NP</Initials></Author>
          <Author><CollectiveName>A Consortium</CollectiveName></Author>
        </AuthorList>
        <ArticleDate><Year>2026</Year><Month>08</Month><Day>28</Day></ArticleDate>
      </Article></MedlineCitation>
      <PubmedData><ArticleIdList>
        <ArticleId IdType="pubmed">42687030</ArticleId>
        <ArticleId IdType="doi">10.1038/s41586-026-00001-0</ArticleId>
      </ArticleIdList></PubmedData>
    </PubmedArticle></PubmedArticleSet>"""

    def test_parses_a_record(self):
        src = PubMedSource({"journals": []}, fetcher=object())
        art = ET.fromstring(self.XML).find(".//PubmedArticle")
        p = src._to_paper(art)
        assert p.doi == "10.1038/s41586-026-00001-0"
        assert p.venue == "Nature"
        assert p.date == date(2026, 8, 28)
        # Markup inside the title must be flattened, not dropped mid-sentence.
        assert p.title == "De novo design of protein cages"
        # Labelled abstract sections are joined in order.
        assert p.abstract == "Cages are useful. We made some."
        # A CollectiveName author has no LastName and must not become an empty entry.
        assert p.authors == ["King NP"]

    def test_month_names_and_numbers_both_parse(self):
        src = PubMedSource({"journals": []}, fetcher=object())
        for month, expected in (("Aug", 8), ("08", 8), ("garbage", 1)):
            xml = self.XML.replace("<Month>08</Month>", f"<Month>{month}</Month>")
            art = ET.fromstring(xml).find(".//PubmedArticle")
            assert src._to_paper(art).date.month == expected, month


class TestAuditWindow:
    def test_selects_only_weeks_inside_the_age_window(self, tmp_path):
        raw = tmp_path / "data" / "raw"
        raw.mkdir(parents=True)
        for w in ("2026-W20", "2026-W30", "2026-W35"):
            (raw / f"{w}.jsonl.gz").write_bytes(b"")
        got = weeks_in_window(
            tmp_path, min_age_days=60, max_age_days=190, today=date(2026, 9, 3)
        )
        # W20 ends 17 May (109 days), W30 ends 26 Jul (39 days), W35 ends 30 Aug (4 days).
        assert got == ["2026-W20"]
