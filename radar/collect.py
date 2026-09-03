"""Fetch every source, tolerate failures, archive the raw result.

Two properties matter here and nothing else does:

1. **Per-source isolation.** One source failing degrades the digest; it never fails the
   run. Each source declares an `expected_min`; falling below it marks the run degraded and
   puts a banner on the front page. Silent under-coverage is the real danger (spec §9).
2. **Replayability.** Everything fetched is archived to `data/raw/<week>.jsonl.gz` before
   any filtering, so `radar rescore` can replay a new prompt or new weights against old
   data with no network calls. You cannot tune the thing honestly without this (spec §0.4).
"""

from __future__ import annotations

import gzip
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from .config import Config
from .models import Paper, SourceHealth
from .sources.arxiv import ArxivSource
from .sources.base import Fetcher
from .sources.biorxiv import BioRxivSource

log = logging.getLogger("radar.collect")


def build_sources(cfg: Config) -> list:
    out = []
    for name in ("biorxiv", "medrxiv"):
        s = cfg.source_cfg(name)
        if s.get("enabled", False):
            out.append(BioRxivSource(name, s, Fetcher(min_interval=0.4)))
    s = cfg.source_cfg("arxiv")
    if s.get("enabled", False):
        # The general-CS gate is pushed into the arXiv query itself, so it has to be
        # derived from the same categories.yaml terms the prefilter uses. Config stays the
        # single source of truth for what counts as a methodology paper.
        gate_terms = [
            t for c in cfg.categories if c.gate_general_cs for t in c.boost
        ]
        out.append(ArxivSource(s, gate_terms=gate_terms))
    return out


def collect(
    cfg: Config, start: date, end: date, sources: list | None = None
) -> tuple[list[Paper], list[SourceHealth]]:
    sources = sources if sources is not None else build_sources(cfg)
    health: list[SourceHealth] = []
    papers: list[Paper] = []

    def run(src):
        return src.name, src.fetch(start, end)

    # Sources are independent and mostly latency-bound; run them concurrently but keep each
    # source's own internal rate limiting intact (each holds its own Fetcher).
    with ThreadPoolExecutor(max_workers=max(1, len(sources))) as pool:
        futures = {pool.submit(run, s): s for s in sources}
        for fut, src in futures.items():
            expected = int(cfg.source_cfg(src.name).get("expected_min", 0))
            try:
                name, got = fut.result()
                papers.extend(got)
                health.append(
                    SourceHealth(
                        source=name, ok=True, fetched=len(got), expected_min=expected
                    )
                )
                log.info("%s: %d records", name, len(got))
            except Exception as exc:                      # noqa: BLE001
                log.error("%s FAILED: %s", src.name, exc)
                health.append(
                    SourceHealth(
                        source=src.name, ok=False, fetched=0,
                        expected_min=expected, error=str(exc)[:300],
                    )
                )

    health.sort(key=lambda h: h.source)
    return papers, health


def raw_path(root: Path, week: str) -> Path:
    return root / "data" / "raw" / f"{week}.jsonl.gz"


def write_raw(root: Path, week: str, papers: list[Paper]) -> Path:
    p = raw_path(root, week)
    p.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(p, "wt", encoding="utf-8") as fh:
        for paper in papers:
            fh.write(paper.model_dump_json() + "\n")
    return p


def read_raw(root: Path, week: str) -> list[Paper]:
    p = raw_path(root, week)
    if not p.exists():
        raise FileNotFoundError(f"no raw archive for {week} at {p}")
    with gzip.open(p, "rt", encoding="utf-8") as fh:
        return [Paper.model_validate_json(line) for line in fh if line.strip()]


def available_raw_weeks(root: Path) -> list[str]:
    d = root / "data" / "raw"
    if not d.exists():
        return []
    return sorted(f.name.removesuffix(".jsonl.gz") for f in d.glob("*.jsonl.gz"))


def load_raw_json(root: Path, week: str) -> list[dict]:
    """Raw records as plain dicts — used by `radar eval`, which only needs text."""
    p = raw_path(root, week)
    if not p.exists():
        return []
    with gzip.open(p, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
