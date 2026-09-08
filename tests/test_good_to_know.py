"""The good-to-know pick.

The contract worth protecting is that this section can never break a run: it touches the
network, it scrapes two pages that nobody promised to keep stable, and it is the least
important thing on the page. Every test here is really the same test — a bad week costs
you the section and nothing else.
"""

from __future__ import annotations

import json
import random



from radar.good_to_know import (
    _ignobel_clause,
    _ignobel_url,
    from_ignobel,
    from_motm,
    from_xkcd,
    pick,
    read_ledger,
    record,
)
from radar.harvest import _clean_reference, _text, harvest_ignobel
from radar.models import GoodToKnow

XKCD_LATEST = {"num": 3000}
XKCD_COMIC = {
    "num": 1319,
    "safe_title": "Automation",
    "title": "Automation",
    "alt": "'Automating' comes from the roots 'auto-' meaning 'self-', and 'mating'.",
    "img": "https://imgs.xkcd.com/comics/automation.png",
    "year": "2014",
}


class FakeFetcher:
    """Serves canned JSON and counts calls, so a test never touches the network."""

    def __init__(self, responses: dict | None = None, fail: bool = False) -> None:
        self.responses = responses or {}
        self.fail = fail
        self.calls: list[str] = []

    def get_json(self, url: str, params=None):
        self.calls.append(url)
        if self.fail:
            raise RuntimeError("network down")
        # Longest key first: "https://xkcd.com/1319/info.0.json" contains both the
        # comic path and the current-comic path.
        for key in sorted(self.responses, key=len, reverse=True):
            if key in url:
                return self.responses[key]
        raise KeyError(url)

    def close(self) -> None:
        pass


# ------------------------------------------------------------------------ sources ----


def test_xkcd_builds_a_card_from_the_api(cfg):
    f = FakeFetcher({"info.0.json": XKCD_LATEST, "/1319/info.0.json": XKCD_COMIC})
    # Force the draw so the test does not depend on the shape of random.Random.
    rng = random.Random()
    rng.randint = lambda a, b: 1319                       # type: ignore[method-assign]

    g = from_xkcd(cfg, rng, f, set())

    assert g is not None
    assert g.kind == "xkcd"
    assert g.title == "Automation"
    # The hover text is the joke; a card without it is not worth rendering.
    assert g.blurb.startswith("'Automating' comes from")
    assert g.url == "https://xkcd.com/1319/"
    assert g.image and g.image.endswith("automation.png")
    assert "CC BY-NC" in g.credit


def test_xkcd_never_draws_the_comic_that_does_not_exist(cfg):
    """xkcd 404 is a joke: the endpoint really does 404."""
    f = FakeFetcher({"info.0.json": XKCD_LATEST, "/404/info.0.json": XKCD_COMIC})
    rng = random.Random()
    rng.randint = lambda a, b: 404                        # type: ignore[method-assign]

    assert from_xkcd(cfg, rng, f, set()) is None
    assert not any("/404/" in c for c in f.calls)


def test_seeded_sources_read_the_harvested_files(cfg):
    """`radar harvest` output is a real dependency of the weekly run."""
    motm = from_motm(cfg, random.Random(1), FakeFetcher(), set())
    ig = from_ignobel(cfg, random.Random(1), FakeFetcher(), set())

    assert motm is not None and motm.kind == "motm"
    assert motm.url.startswith("https://pdb101.rcsb.org/motm/")
    assert motm.image, "the Goodsell illustration is the point of this source"

    assert ig is not None and ig.kind == "ignobel"
    assert ig.url.startswith("https://")


def test_every_pick_links_somewhere_real(cfg):
    """A card whose link is prose rather than a URL is worse than no card."""
    seen = set()
    for seed in range(25):
        for fn in (from_motm, from_ignobel):
            g = fn(cfg, random.Random(seed), FakeFetcher(), seen)
            assert g is not None
            assert g.url.startswith("https://"), g.url


def test_ignobel_url_is_unique_without_a_doi():
    a = {"category": "Peace", "year": 1995, "citation": "x"}
    b = {"category": "Physics", "year": 1995, "citation": "y"}
    assert _ignobel_url(a) != _ignobel_url(b)
    assert _ignobel_url({"doi": "10.1/x"}) == "https://doi.org/10.1/x"


def test_ignobel_leads_with_the_joke_not_the_author_list():
    citation = "Ryo Okabe, Toyofumi Chen-Yoshikawa, and Yosuke Yoneyama, for discovering that many mammals can breathe through their anus."
    assert _ignobel_clause(citation) == (
        "Discovering that many mammals can breathe through their anus."
    )
    # No "for" clause: keep the wording rather than mangling it.
    assert _ignobel_clause("A citation with no clause") == "A citation with no clause"


# ------------------------------------------------------------------------- ledger ----


def test_a_pick_is_never_shown_twice(cfg, tmp_path):
    used = GoodToKnow(kind="motm", title="Myoglobin", url="https://pdb101.rcsb.org/motm/1")
    record(tmp_path, "2026-W01", used)

    assert read_ledger(tmp_path)["picks"][0]["url"] == used.url

    # A source asked to avoid that URL must return something else, not repeat it.
    for seed in range(10):
        g = from_motm(cfg, random.Random(seed), FakeFetcher(), {used.url})
        assert g is None or g.url != used.url


def test_a_corrupt_ledger_does_not_break_the_run(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "good_to_know_seen.json").write_text("{not json")
    assert read_ledger(tmp_path) == {"picks": []}


def test_the_ledger_round_trips(tmp_path):
    for i in range(3):
        record(tmp_path, f"2026-W0{i}", GoodToKnow(kind="xkcd", title=str(i), url=f"u{i}"))
    data = json.loads((tmp_path / "data" / "good_to_know_seen.json").read_text())
    assert [p["url"] for p in data["picks"]] == ["u0", "u1", "u2"]


# --------------------------------------------------------------------------- pick ----


def test_pick_is_deterministic_for_a_week(cfg):
    a = pick(cfg, "2026-W36", fetcher=FakeFetcher(fail=True))
    b = pick(cfg, "2026-W36", fetcher=FakeFetcher(fail=True))
    assert a is not None and b is not None
    assert (a.kind, a.url) == (b.kind, b.url)


def test_a_dead_network_still_yields_a_pick_from_the_seed_files(cfg):
    """Two of the four sources are on disk, which is the whole point of harvesting them."""
    g = pick(cfg, "2026-W36", fetcher=FakeFetcher(fail=True))
    assert g is not None
    assert g.kind in ("motm", "ignobel")


def test_no_sources_at_all_is_not_an_error(cfg, monkeypatch):
    monkeypatch.setitem(cfg.profile, "good_to_know", {"kinds": []})
    assert pick(cfg, "2026-W36", fetcher=FakeFetcher(fail=True)) is None


def test_disabled_kinds_are_never_consulted(cfg, monkeypatch):
    monkeypatch.setitem(cfg.profile, "good_to_know", {"kinds": ["motm"]})
    for week in ("2026-W36", "2026-W37", "2026-W38"):
        g = pick(cfg, week, fetcher=FakeFetcher(fail=True))
        assert g is not None and g.kind == "motm"


# ------------------------------------------------------------------------ harvest ----


def test_reference_cleanup_strips_the_pages_own_punctuation():
    raw = "“A Paper,” A. Author, Journal, 2020. < doi.org/10.1/x > WHO TOOK PART IN THE CEREMONY: A. Author"
    cleaned = _clean_reference(raw)
    assert "WHO" not in cleaned
    assert "<" not in cleaned and ">" not in cleaned
    assert cleaned.startswith("“A Paper,”")


def test_text_closes_the_gaps_that_tag_stripping_opens():
    assert _text("<p>Outsourcing prayers to <em>India</em> .</p>") == "Outsourcing prayers to India."
    assert _text("<b>“</b>A Title<b>”</b>") == "“A Title”"


def test_harvest_survives_markup_it_has_never_seen():
    """The scrapers are the fragile part; they must fail empty, not raise."""

    class Page:
        text = "<html><body><p>nothing that looks like a prize</p></body></html>"

    class Stub:
        def get(self, url, params=None):
            return Page()

    assert harvest_ignobel(Stub()) == []
