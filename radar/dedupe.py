"""Cross-week dedupe against `data/seen.sqlite`.

The 10-day lookback deliberately overlaps the 7-day week (spec §9), so most of what a run
fetches has been seen before. Dedupe on DOI *and* on a normalised title, because the same
work legitimately arrives with different identifiers — a bioRxiv preprint and its arXiv
mirror, or a preprint and its journal version.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from .models import Paper
from .util import normalise_title

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen (
    id            TEXT PRIMARY KEY,
    norm_title    TEXT NOT NULL,
    doi           TEXT,
    first_week    TEXT NOT NULL,
    first_seen    TEXT NOT NULL,
    source        TEXT NOT NULL,
    published_doi TEXT
);
CREATE INDEX IF NOT EXISTS idx_seen_norm_title ON seen(norm_title);
CREATE INDEX IF NOT EXISTS idx_seen_doi        ON seen(doi);
CREATE INDEX IF NOT EXISTS idx_seen_week       ON seen(first_week);
"""


class SeenStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "SeenStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self.conn.close()

    # --- reads --------------------------------------------------------------------

    def known_ids(self) -> set[str]:
        return {r[0] for r in self.conn.execute("SELECT id FROM seen")}

    def known_titles(self) -> set[str]:
        return {r[0] for r in self.conn.execute("SELECT norm_title FROM seen")}

    def known_dois(self) -> set[str]:
        return {
            r[0].lower()
            for r in self.conn.execute("SELECT doi FROM seen WHERE doi IS NOT NULL")
        }

    def week_of(self, paper_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT first_week FROM seen WHERE id = ?", (paper_id,)
        ).fetchone()
        return row[0] if row else None

    def find_by_doi(self, doi: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM seen WHERE lower(doi) = ?", (doi.lower(),)
        ).fetchone()

    # --- writes -------------------------------------------------------------------

    def record(self, papers: list[Paper], week: str) -> None:
        self.conn.executemany(
            """INSERT OR IGNORE INTO seen
               (id, norm_title, doi, first_week, first_seen, source, published_doi)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    p.id,
                    normalise_title(p.title),
                    p.doi,
                    week,
                    date.today().isoformat(),
                    p.source,
                    p.published_doi,
                )
                for p in papers
            ],
        )
        # A preprint we already knew may have acquired a journal DOI since; keep it current
        # so the "now published" strip can fire.
        self.conn.executemany(
            "UPDATE seen SET published_doi = ? WHERE id = ? AND published_doi IS NULL",
            [(p.published_doi, p.id) for p in papers if p.published_doi],
        )
        self.conn.commit()


def dedupe(papers: list[Paper], store: SeenStore | None = None) -> tuple[list[Paper], int]:
    """Return (new papers, number dropped).

    Within-batch duplicates are collapsed first (the same work often arrives from two
    sources in one run), then anything already in the store is dropped.
    """
    seen_ids = store.known_ids() if store else set()
    seen_titles = store.known_titles() if store else set()
    seen_dois = store.known_dois() if store else set()

    batch_ids: set[str] = set()
    batch_titles: set[str] = set()
    batch_dois: set[str] = set()

    out: list[Paper] = []
    dropped = 0

    for p in papers:
        nt = normalise_title(p.title)
        doi_l = p.doi.lower() if p.doi else None

        duplicate = (
            p.id in seen_ids
            or p.id in batch_ids
            # Very short normalised titles are collision-prone; require real substance.
            or (len(nt) > 20 and (nt in seen_titles or nt in batch_titles))
            or (doi_l and (doi_l in seen_dois or doi_l in batch_dois))
        )
        if duplicate:
            dropped += 1
            continue

        batch_ids.add(p.id)
        if len(nt) > 20:
            batch_titles.add(nt)
        if doi_l:
            batch_dois.add(doi_l)
        out.append(p)

    return out, dropped


def find_now_published(papers: list[Paper], store: SeenStore) -> list[dict]:
    """Preprints we reported in an earlier week that have since appeared in a journal.

    bioRxiv gives this linkage for free via its `published` field, so it costs one pass
    over the corpus. Reported as a one-line strip rather than as new items (spec §2).
    """
    out = []
    for p in papers:
        if not p.published_doi or not p.doi:
            continue
        row = store.find_by_doi(p.doi)
        if row is None:
            continue
        out.append(
            {
                "preprint_doi": p.doi,
                "journal_doi": p.published_doi,
                "title": p.title,
                "journal": "",
                "first_seen_week": row["first_week"],
            }
        )
    return out
