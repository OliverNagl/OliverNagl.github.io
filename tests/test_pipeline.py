"""Dedupe, the degradation path, and end-to-end assembly."""

from __future__ import annotations

import json
from datetime import date

import pytest

from radar.dedupe import SeenStore, dedupe, find_now_published
from radar.models import SourceHealth, Stats, Triage
from radar.util import iso_week, normalise_title, week_window
from radar.work import load_deep, load_triage, safe_name

from .conftest import make_paper


class TestDedupe:
    def test_collapses_duplicates_within_one_batch(self):
        a = make_paper(id="10.1101/a", title="A designed protein nanocage")
        b = make_paper(id="10.1101/b", title="A designed protein nanocage")   # same work
        out, dropped = dedupe([a, b])
        assert len(out) == 1 and dropped == 1

    def test_short_titles_are_not_fuzzy_matched(self):
        # Normalised titles under ~20 chars collide far too easily to trust.
        a = make_paper(id="10.1101/a", title="Nanocages")
        b = make_paper(id="10.1101/b", title="Nanocages")
        out, _ = dedupe([a, b])
        assert len(out) == 2

    def test_persists_across_runs(self, tmp_path):
        p = make_paper(id="10.1101/x", title="A designed protein nanocage assembly")
        with SeenStore(tmp_path / "seen.sqlite") as store:
            out, _ = dedupe([p], store)
            assert len(out) == 1
            store.record(out, "2026-W01")
            again, dropped = dedupe([p], store)
        assert again == [] and dropped == 1

    def test_rerunning_a_week_is_idempotent_not_empty(self, tmp_path):
        """Re-running a week must reproduce it, not wipe it.

        The spec requires idempotency on the ISO week key. Without excluding the week
        being rebuilt from the seen-set, every record counts as a duplicate of itself,
        the run finds nothing new, and it silently overwrites a good digest with an
        empty one.
        """
        papers = [
            make_paper(id=f"10.1101/{i}", title=f"A designed protein nanocage number {i}")
            for i in range(5)
        ]
        with SeenStore(tmp_path / "seen.sqlite") as store:
            first, _ = dedupe(papers, store, "2026-W36")
            store.record(first, "2026-W36")
            assert len(first) == 5

            # Same week again: all five must come back.
            again, dropped = dedupe(papers, store, "2026-W36")
            assert len(again) == 5 and dropped == 0

            # A *later* week must still see them as duplicates.
            later, dropped_later = dedupe(papers, store, "2026-W37")
            assert later == [] and dropped_later == 5

    def test_forget_week_clears_only_that_week(self, tmp_path):
        with SeenStore(tmp_path / "seen.sqlite") as store:
            store.record([make_paper(id="10.1101/a", title="Cage one design study")], "2026-W35")
            store.record([make_paper(id="10.1101/b", title="Cage two design study")], "2026-W36")
            assert store.forget_week("2026-W35") == 1
            assert store.known_ids() == {"10.1101/b"}

    def test_normalise_title_ignores_case_punctuation_and_accents(self):
        assert normalise_title("Designed Protein Cages!") == normalise_title(
            "designed  protein   cages"
        )
        assert normalise_title("Björk's résumé") == normalise_title("Bjorks resume")

    def test_now_published_links_a_preprint_to_its_journal_version(self, tmp_path):
        pre = make_paper(id="10.1101/p", title="A designed protein nanocage assembly")
        with SeenStore(tmp_path / "seen.sqlite") as store:
            store.record([pre], "2026-W01")
            later = make_paper(
                id="10.1101/p", title="A designed protein nanocage assembly",
                published_doi="10.1038/s41586-026-00001-0",
            )
            found = find_now_published([later], store)
        assert len(found) == 1
        assert found[0]["journal_doi"] == "10.1038/s41586-026-00001-0"
        assert found[0]["first_seen_week"] == "2026-W01"


class TestWindow:
    def test_lookback_overlaps_the_week(self):
        start, end = week_window("2026-W36", 10)
        assert (end - start).days == 9
        assert iso_week(end) == "2026-W36"

    def test_rejects_a_malformed_week(self):
        with pytest.raises(ValueError):
            week_window("2026-36", 10)


class TestJudgementFiles:
    """Nothing from the model is trusted; bad input must degrade, never crash."""

    def _write(self, root, week, payload):
        d = root / "work" / week / "triage_out"
        d.mkdir(parents=True, exist_ok=True)
        (d / "batch_00.json").write_text(json.dumps(payload))

    def test_valid_rows_are_loaded(self, tmp_path):
        p = make_paper(id="10.1101/a")
        self._write(tmp_path, "2026-W01", [
            {"id": "10.1101/a", "category": "assembly", "relevance": 8,
             "novelty": 6, "reason": "does a thing"}
        ])
        got = load_triage(tmp_path, "2026-W01", [p])
        assert got["10.1101/a"].relevance == 8

    def test_out_of_range_ratings_are_dropped_not_clamped(self, tmp_path):
        p = make_paper(id="10.1101/a")
        self._write(tmp_path, "2026-W01", [
            {"id": "10.1101/a", "category": "assembly", "relevance": 99,
             "novelty": 6, "reason": "nonsense"}
        ])
        assert load_triage(tmp_path, "2026-W01", [p]) == {}

    def test_rows_for_unknown_ids_are_ignored(self, tmp_path):
        p = make_paper(id="10.1101/a")
        self._write(tmp_path, "2026-W01", [
            {"id": "10.1101/hallucinated", "category": "assembly", "relevance": 8,
             "novelty": 6, "reason": "not in this batch"}
        ])
        assert load_triage(tmp_path, "2026-W01", [p]) == {}

    def test_malformed_json_yields_nothing_rather_than_raising(self, tmp_path):
        d = tmp_path / "work" / "2026-W01" / "triage_out"
        d.mkdir(parents=True)
        (d / "batch_00.json").write_text("{not json at all")
        assert load_triage(tmp_path, "2026-W01", [make_paper()]) == {}

    def test_missing_directory_is_not_an_error(self, tmp_path):
        assert load_triage(tmp_path, "2026-W99", [make_paper()]) == {}
        assert load_deep(tmp_path, "2026-W99") == {}

    def test_deep_dive_action_falls_back_when_invalid(self, tmp_path):
        d = tmp_path / "work" / "2026-W01" / "deep_out"
        d.mkdir(parents=True)
        (d / "x.json").write_text(json.dumps(
            {"id": "10.1101/a", "why": "Three sentences.", "action": "devour",
             "touches": ["a", "b", "c", "d", "e"]}
        ))
        got = load_deep(tmp_path, "2026-W01")
        assert got["10.1101/a"]["action"] == "skim"
        assert len(got["10.1101/a"]["touches"]) == 4     # capped

    def test_safe_name_is_filesystem_safe_and_unique(self):
        a = safe_name("10.1101/2026.08.28.123456")
        b = safe_name("10.1101/2026.08.28.123457")
        assert "/" not in a and a != b


class TestAssembly:
    def test_degrades_to_lexical_when_there_is_no_triage(self, cfg, tmp_path):
        from radar.assemble import assemble
        from radar.prefilter import judge

        papers = [
            make_paper(id=f"10.1101/{i}", title="Designed protein nanocage assembly",
                       abstract="An icosahedral capsid self-assembly study.")
            for i in range(6)
        ]
        extras = {
            "verdicts": {p.id: judge(p, cfg) for p in papers},
            "rejected": [],
            "window": (date(2026, 1, 1), date(2026, 1, 10)),
        }
        issue = assemble(
            cfg, "2026-W02", papers,
            [SourceHealth(source="biorxiv", ok=True, fetched=500, expected_min=300)],
            Stats(fetched=6, new=6, shortlisted=6), [], extras,
        )
        assert issue.front_page                       # never empty
        assert issue.degraded
        assert all(s.degraded for s in issue.front_page)
        assert any("lexical" in n for n in issue.notes)

    def test_a_failed_source_marks_the_run_degraded(self, cfg):
        from radar.assemble import assemble
        from radar.prefilter import judge

        p = make_paper(title="Designed protein nanocage", abstract="An assembly study.")
        extras = {"verdicts": {p.id: judge(p, cfg)}, "rejected": [],
                  "window": (date(2026, 1, 1), date(2026, 1, 10))}
        issue = assemble(
            cfg, "2026-W02", [p],
            [SourceHealth(source="arxiv", ok=False, error="timeout", expected_min=80)],
            Stats(), [], extras,
            triage={p.id: Triage(id=p.id, category="assembly", relevance=8,
                                 novelty=7, reason="x")},
        )
        assert issue.degraded
        assert any("arxiv" in n for n in issue.notes)
