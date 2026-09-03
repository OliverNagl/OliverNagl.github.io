"""The prefilter is where recall is won or lost, so its tiers are pinned down here."""

from __future__ import annotations

from radar.prefilter import judge, prefilter, score_categories, watchlist_hit
from radar.util import compile_term

from .conftest import make_paper


class TestTiers:
    def test_watchlist_author_bypasses_everything(self, cfg):
        # No domain vocabulary at all — only the author should carry it through.
        p = make_paper(title="Some unrelated title", abstract="Nothing to see.",
                       authors=["King NP"])
        v = judge(p, cfg)
        assert v.passed and v.tier == "hard_include"
        assert v.watchlist_hit == "King NP"

    def test_hard_include_phrase_bypasses_must_any(self, cfg):
        p = make_paper(title="Nanocage engineering", abstract="No other vocabulary here.")
        v = judge(p, cfg)
        assert v.passed and v.tier == "hard_include"
        assert v.matched_include == "nanocage"

    def test_no_domain_vocabulary_is_rejected(self, cfg):
        p = make_paper(title="A study of medieval pottery",
                       abstract="Kiln temperatures in the twelfth century.")
        v = judge(p, cfg)
        assert not v.passed
        assert v.failed_rule == "must_any"

    def test_hard_exclude_is_rejected_but_names_the_phrase(self, cfg):
        p = make_paper(
            title="A randomized controlled trial of a protein supplement",
            abstract="We enrolled 400 patients. Protein intake was measured.",
        )
        v = judge(p, cfg)
        assert not v.passed
        assert v.failed_rule == "hard_exclude"
        # Naming the offending phrase is what makes `radar eval` able to explain a miss.
        assert v.matched_exclude == "randomized controlled trial"

    def test_domain_hit_without_category_vocabulary_is_rejected(self, cfg):
        p = make_paper(title="Protein content of oat flour",
                       abstract="We measured protein in several samples.")
        v = judge(p, cfg)
        assert not v.passed
        assert v.failed_rule == "no_boost"


class TestGeneralCSGate:
    def test_decisive_term_passes_alone(self, cfg):
        p = make_paper(
            id="arxiv:2601.00001", source="arxiv", venue="arXiv", subject="cs.LG",
            title="Flow matching for image generation",
            abstract="We propose a new flow matching objective.",
        )
        v = judge(p, cfg)
        assert v.passed and v.tier == "gated_cs"

    def test_generic_term_alone_is_rejected(self, cfg):
        p = make_paper(
            id="arxiv:2601.00002", source="arxiv", venue="arXiv", subject="cs.LG",
            title="Test-time adaptation for video segmentation",
            abstract="We adapt at test-time to improve video results.",
        )
        v = judge(p, cfg)
        assert not v.passed
        assert v.failed_rule == "gated_cs"

    def test_generic_term_with_a_domain_term_passes(self, cfg):
        p = make_paper(
            id="arxiv:2601.00003", source="arxiv", venue="arXiv", subject="cs.LG",
            title="Test-time adaptation for molecular property prediction",
            abstract="We adapt at test-time on molecular graphs.",
        )
        v = judge(p, cfg)
        assert v.passed and v.tier == "gated_cs"


class TestTermMatching:
    def test_terms_match_as_prefixes(self):
        pat = compile_term("self-assembl")
        assert pat.search("the self-assembly of capsids")
        assert pat.search("proteins that self-assembled")

    def test_short_terms_do_not_match_inside_words(self):
        # This was a real bug: "rna" matched inside "internal" and "governance", quietly
        # letting unrelated CS papers through the domain gate.
        pat = compile_term("rna")
        assert not pat.search("an internal representation")
        assert not pat.search("model governance")
        assert pat.search("RNA polymerase")

    def test_scoring_sums_matched_weights(self, cfg):
        text = "icosahedral capsid self-assembly with quasi-equivalence"
        scores = score_categories(text, cfg)
        assert scores["assembly"] > 5.0


class TestPrefilterSplit:
    def test_overflow_goes_to_the_rejected_pool_not_the_bin(self, cfg):
        # The blindspot channel and the recall audit both depend on nothing being dropped.
        papers = [
            make_paper(id=f"10.1101/x{i}", title="Nanocage design",
                       abstract="A designed protein nanocage assembly.")
            for i in range(10)
        ]
        res = prefilter(papers, cfg, limit=3)
        assert len(res.shortlist) == 3
        assert len(res.rejected) == 7
        assert len(res.verdicts) == 10

    def test_watchlist_sorts_above_keyword_dense_papers(self, cfg):
        dense = make_paper(
            id="10.1101/dense",
            title="icosahedral capsid nanocage quasi-equivalence T=3 Caspar-Klug",
            abstract="self-assembly two-component symmetry-breaking protein crystal",
        )
        watched = make_paper(id="10.1101/watched", title="A modest result",
                             abstract="Some protein work.", authors=["Baker D"])
        res = prefilter([dense, watched], cfg, limit=2)
        assert res.shortlist[0].id == "10.1101/watched"


def test_watchlist_matches_across_author_name_formats(cfg):
    for form in ["King NP", "King, Neil P.", "Neil P. King", "N. P. King"]:
        p = make_paper(authors=[form])
        assert watchlist_hit(p, cfg) == "King NP", form
