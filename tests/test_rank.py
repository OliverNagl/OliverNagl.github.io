"""Ranking arithmetic, the front-page cap, and the Python/JS parity contract."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

try:
    import dukpy
except ImportError:      # pragma: no cover
    dukpy = None

from radar.models import ScoreBreakdown
from radar.rank import build_backlog, score, select_front_page
from radar.models import Scored

FIXTURE = Path(__file__).parent / "fixtures" / "rank_cases.json"

WEIGHTS = {
    "relevance": 1.00, "novelty": 0.35, "category": 0.50, "watchlist_author": 0.40,
    "code_released": 0.25, "venue_tier": 0.20, "similar_seen_recently": -0.30,
}


def test_score_terms_are_kept_separately():
    b = score(
        relevance=8, novelty=6, category_weight=1.3, watchlist_author=True,
        code_released=True, venue_tier=0.6, similar_seen_recently=False, weights=WEIGHTS,
    )
    assert b.relevance == pytest.approx(0.8)
    assert b.novelty == pytest.approx(0.21)
    assert b.category == pytest.approx(0.65)
    assert b.watchlist_author == pytest.approx(0.40)
    assert b.code_released == pytest.approx(0.25)
    assert b.venue_tier == pytest.approx(0.12)
    assert b.total == pytest.approx(2.43)


def test_similar_seen_recently_is_a_penalty():
    kw = dict(relevance=8, novelty=6, category_weight=1.0, watchlist_author=False,
              code_released=False, venue_tier=0.0, weights=WEIGHTS)
    assert score(similar_seen_recently=True, **kw).total < score(
        similar_seen_recently=False, **kw).total


def _scored(id_, cat, sc, day=1):
    return Scored(
        id=id_, title=f"paper {id_}", authors_short="A, …, B", venue="bioRxiv",
        source="biorxiv", date=date(2026, 1, day), category=cat, score=sc,
        breakdown=ScoreBreakdown(),
    )


class TestFrontPage:
    def test_per_category_cap_prevents_one_area_crowding_out_the_rest(self):
        # Four very strong ml-method papers must not take four of the five slots.
        papers = [_scored(f"ml{i}", "ml-method", 9.0 - i * 0.1) for i in range(4)]
        papers += [_scored("as1", "assembly", 5.0), _scored("en1", "enzyme", 4.0)]
        front, rest = select_front_page(papers, top_n=5, max_per_category=2)
        assert sum(1 for s in front if s.category == "ml-method") == 2
        assert {s.id for s in front} >= {"as1", "en1"}
        assert len(front) + len(rest) == len(papers)

    def test_remainder_excludes_exactly_what_was_chosen(self):
        papers = [_scored(f"p{i}", "assembly", float(i)) for i in range(8)]
        front, rest = select_front_page(papers, top_n=2, max_per_category=2)
        assert {s.id for s in front}.isdisjoint({s.id for s in rest})
        assert len(rest) == 6


def test_backlog_caps_each_category_and_orders_by_size():
    papers = [_scored(f"a{i}", "assembly", float(i)) for i in range(15)]
    papers += [_scored(f"e{i}", "enzyme", float(i)) for i in range(3)]
    backlog = build_backlog(papers, max_per_category=10)
    assert len(backlog["assembly"]) == 10
    assert len(backlog["enzyme"]) == 3
    assert list(backlog)[0] == "assembly"       # busiest first — itself information


# ------------------------------------------------------------------ JS parity ----


def test_fixture_matches_python():
    """The fixture is the contract between rank.py and assets/rank.js."""
    cases = json.loads(FIXTURE.read_text())
    for case in cases["cases"]:
        got = score(**case["input"], weights=cases["weights"])
        assert got.total == pytest.approx(case["expected_total"]), case["name"]


@pytest.mark.skipif(dukpy is None, reason="dukpy not installed")
def test_javascript_matches_the_same_fixture():
    """Guards the two implementations against drift.

    The tuning page re-ranks in the browser, which is only safe while assets/rank.js and
    radar/rank.py agree. dukpy embeds a JS engine so this actually runs in CI rather than
    being skipped; the fixture above is the shared contract between the two.
    """
    root = Path(__file__).resolve().parent.parent
    cases = json.loads(FIXTURE.read_text())
    prog = "var window={};" + (root / "assets" / "rank.js").read_text() + """
      var out = [];
      for (var i = 0; i < CASES.cases.length; i++) {
        var c = CASES.cases[i];
        var b = window.RadarRank.score({
          relevance: c.input.relevance,
          novelty: c.input.novelty,
          category_weight: c.input.category_weight,
          watchlist_author: c.input.watchlist_author,
          code_released: c.input.code_released,
          venue_tier: c.input.venue_tier,
          similar_seen_recently: c.input.similar_seen_recently
        }, CASES.weights);
        out.push([c.name, b.total, c.expected_total]);
      }
      out;
    """
    got = dukpy.evaljs(["var CASES=" + json.dumps(cases) + ";", prog])
    drift = [(n, js, py) for n, js, py in got if abs(js - py) > 1e-9]
    assert not drift, f"rank.js and rank.py disagree: {drift}"
