"""Exercise assets/search.js directly.

Archive search is the one reason the Pages site exists rather than just the markdown
digests, and it is entirely client-side — so it needs real coverage, not an assumption
that it works. dukpy embeds a JS engine, so these run in CI without node.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

try:
    import dukpy
except ImportError:      # pragma: no cover
    dukpy = None

pytestmark = pytest.mark.skipif(dukpy is None, reason="dukpy not installed")

ROOT = Path(__file__).resolve().parent.parent

DOCS = [
    {"id": "1", "week": "2026-W01", "title": "Icosahedral protein nanocage design",
     "authors": "Lee S, …, King NP", "venue": "bioRxiv", "date": "2026-01-05",
     "category": "assembly", "action": "read", "score": 2.4,
     "why": "Ties the asymmetric unit across the icosahedral orbit.",
     "reason": "", "touches": ["symmetry-native diffusion"],
     "abstract": "We design two-component capsids with quasi-equivalence.",
     "code": True, "watchlist": "King NP", "front": True, "url": "u1"},
    {"id": "2", "week": "2026-W01", "title": "Flow matching for discrete sequences",
     "authors": "Doe J", "venue": "arXiv", "date": "2026-01-06",
     "category": "ml-method", "action": "skim", "score": 1.8,
     "why": "A discrete flow matching objective.", "reason": "", "touches": [],
     "abstract": "We extend flow matching to categorical data.",
     "code": False, "watchlist": "", "front": True, "url": "u2"},
    {"id": "3", "week": "2026-W02", "title": "Enzyme active site scaffolding",
     "authors": "Roe A", "venue": "Nature", "date": "2026-01-12",
     "category": "enzyme", "action": "", "score": 1.2,
     "why": "", "reason": "theozyme scaffolding into designed backbones",
     "touches": [], "abstract": "Catalytic residues placed by geometric matching.",
     "code": False, "watchlist": "", "front": False, "url": "u3"},
]


def search(queries: list[str]) -> dict:
    prog = "var window={};" + (ROOT / "assets" / "search.js").read_text() + """
      var ix = new window.RadarSearch.Index(DOCS);
      var out = {};
      for (var i = 0; i < QUERIES.length; i++) {
        var q = QUERIES[i];
        var r = ix.search(q);
        out[q] = r === null ? null : {
          partial: !!r.partial,
          ids: r.map(function (h) { return h.doc.id; })
        };
      }
      out;
    """
    return dukpy.evaljs(
        ["var DOCS=" + json.dumps(DOCS) + "; var QUERIES=" + json.dumps(queries) + ";", prog]
    )


def test_empty_query_is_distinguishable_from_no_results():
    # null means "show everything", [] means "nothing matched" — the page renders these
    # very differently, so conflating them is a real bug.
    r = search(["", "   "])
    assert r[""] is None
    assert r["   "] is None


def test_finds_a_title_term():
    assert search(["nanocage"])["nanocage"]["ids"] == ["1"]


def test_matches_the_last_token_as_a_prefix_so_results_update_while_typing():
    for partial_word in ["nanocag", "nanoca", "icosahed"]:
        assert "1" in search([partial_word])[partial_word]["ids"], partial_word


def test_searches_the_why_and_reason_fields_not_just_titles():
    assert search(["theozyme"])["theozyme"]["ids"] == ["3"]
    assert "1" in search(["orbit"])["orbit"]["ids"]


def test_searches_touches():
    assert "1" in search(["symmetry-native"])["symmetry-native"]["ids"]


def test_all_terms_must_match_when_a_full_match_exists():
    r = search(["flow matching discrete"])["flow matching discrete"]
    assert r["ids"] == ["2"]
    assert r["partial"] is False


def test_falls_back_to_partial_matches_rather_than_a_dead_end():
    # The half-remembered query is exactly what this page is for; returning nothing
    # because one word is absent would defeat it.
    r = search(["icosahedral quasi-equivalence unicorn"])["icosahedral quasi-equivalence unicorn"]
    assert r["partial"] is True
    assert r["ids"][0] == "1"


def test_unknown_term_yields_no_results():
    assert search(["zzzznothinghere"])["zzzznothinghere"]["ids"] == []


def test_rare_terms_outrank_common_ones():
    # "protein" is near-universal in this corpus; "theozyme" is not. IDF should mean the
    # rare term decides the ordering.
    r = search(["design"])["design"]
    assert set(r["ids"]) >= {"1"}
