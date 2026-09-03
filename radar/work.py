"""The LLM boundary, expressed as files rather than as a code path.

`radar collect` writes prompt files into `work/<week>/`. Something then writes answer files
back. That something can be:

* the scheduled Claude Code Routine, reading the prompts and writing JSON directly — which
  is how this radar runs, and needs no API key anywhere in the repo; or
* `radar triage --llm=api`, filling exactly the same files from the Anthropic SDK.

Because the contract is files, switching between the two is a flag rather than a rewrite,
and every deterministic stage stays runnable and testable with no model at all.

Nothing here trusts its input. Every answer file is schema-validated, and anything missing
or malformed degrades that paper to lexical scoring instead of failing the run (spec §9).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path

from pydantic import ValidationError

from .config import Config
from .models import Paper, Triage

log = logging.getLogger("radar.work")

TRIAGE_BATCH_SIZE = 25
VALID_ACTIONS = {"read", "skim", "track", "cite"}
VALID_CONFIDENCE = {"low", "medium", "high"}


def work_dir(root: Path, week: str) -> Path:
    return root / "work" / week


def safe_name(paper_id: str) -> str:
    """A filesystem-safe, collision-free stem for a paper id (DOIs contain slashes)."""
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", paper_id).strip("_")[:60]
    digest = hashlib.sha1(paper_id.encode()).hexdigest()[:8]
    return f"{slug}-{digest}"


# --------------------------------------------------------------------- prompts ----


def _paper_block(p: Paper, n: int, max_abstract: int = 1000) -> str:
    """One paper as the model sees it.

    `max_abstract` is the single biggest lever on run cost. The prefilter always matches
    on the full abstract, so trimming here changes only how much the model reads to make
    a coarse 0-10 call — never what gets screened.
    """
    authors = ", ".join(p.authors[:8]) + (" et al." if len(p.authors) > 8 else "")
    abstract = p.abstract[:max_abstract]
    if len(p.abstract) > max_abstract:
        abstract += " […]"
    return (
        f"### [{n}] id: {p.id}\n"
        f"- title: {p.title}\n"
        f"- authors: {authors}\n"
        f"- venue: {p.venue} ({p.source}) · {p.date.isoformat()} · subject: {p.subject or '—'}\n"
        f"- code released: {'yes' if p.code_url else 'no'}\n"
        f"- abstract: {abstract or '(no abstract available)'}\n"
    )


def _abstract_budget(cfg: Config, key: str, default: int) -> int:
    return int((cfg.profile.get("budget") or {}).get(key, default))


def prepare_triage(cfg: Config, week: str, shortlist: list[Paper]) -> list[Path]:
    """Write the triage batches. One file per 25 abstracts, each self-contained."""
    wd = work_dir(cfg.root, week)
    out_dir = wd / "triage"
    out_dir.mkdir(parents=True, exist_ok=True)
    (wd / "triage_out").mkdir(parents=True, exist_ok=True)

    instructions = (cfg.root / "config" / "prompts" / "triage.md").read_text()
    taxonomy = "\n".join(
        f"- `{c.id}` — {c.name}: {' '.join(c.description.split())}" for c in cfg.categories
    )

    max_abs = _abstract_budget(cfg, "triage_abstract_chars", 1000)
    written = []
    batches = [
        shortlist[i : i + TRIAGE_BATCH_SIZE]
        for i in range(0, len(shortlist), TRIAGE_BATCH_SIZE)
    ]
    for i, batch in enumerate(batches):
        body = "\n".join(_paper_block(p, n, max_abs) for n, p in enumerate(batch, 1))
        text = (
            f"{instructions}\n\n"
            f"## Categories\n\n{taxonomy}\n\n"
            f"## Write your answer to\n\n"
            f"`work/{week}/triage_out/batch_{i:02d}.json`\n\n"
            f"## Papers ({len(batch)})\n\n{body}"
        )
        p = out_dir / f"batch_{i:02d}.md"
        p.write_text(text)
        written.append(p)

    manifest = {
        "week": week,
        "batches": len(batches),
        "papers": len(shortlist),
        "ids": [p.id for p in shortlist],
    }
    (wd / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return written


def prepare_deep(cfg: Config, week: str, papers: list[Paper]) -> list[Path]:
    """One deep-dive prompt per paper, carrying the open threads so the model can say
    which of *your* questions the paper touches (spec §3)."""
    wd = work_dir(cfg.root, week)
    out_dir = wd / "deep"
    out_dir.mkdir(parents=True, exist_ok=True)
    (wd / "deep_out").mkdir(parents=True, exist_ok=True)

    instructions = (cfg.root / "config" / "prompts" / "deep_dive.md").read_text()
    threads = "\n".join(f"- {t}" for t in cfg.open_threads)

    written = []
    for p in papers:
        name = safe_name(p.id)
        text = (
            f"{instructions}\n\n"
            f"## The reader's open threads\n\n{threads}\n\n"
            f"## Write your answer to\n\n`work/{week}/deep_out/{name}.json`\n\n"
            # Only ~15 of these, and this is the pass whose output people read.\n            f"## Paper\n\n{_paper_block(p, 1, max_abstract=4000)}"
        )
        f = out_dir / f"{name}.md"
        f.write_text(text)
        written.append(f)
    return written


def prepare_blindspot(cfg: Config, week: str, sample: list[Paper]) -> Path:
    """One prompt over the stratified sample from the *rejected* pool.

    A blindspot pick drawn from the shortlist would just be the sixth-best hit, so this
    prompt deliberately asks a different question from triage (spec §4).
    """
    wd = work_dir(cfg.root, week)
    wd.mkdir(parents=True, exist_ok=True)
    instructions = (cfg.root / "config" / "prompts" / "blindspot.md").read_text()
    threads = "\n".join(f"- {t}" for t in cfg.open_threads)
    max_abs = _abstract_budget(cfg, "blindspot_abstract_chars", 900)
    body = "\n".join(_paper_block(p, n, max_abs) for n, p in enumerate(sample, 1))
    text = (
        f"{instructions}\n\n"
        f"## The reader's current problems\n\n{threads}\n\n"
        f"## Write your answer to\n\n`work/{week}/blindspot_out.json`\n\n"
        f"## Candidates ({len(sample)})\n\n{body}"
    )
    p = wd / "blindspot.md"
    p.write_text(text)
    return p


# --------------------------------------------------------------------- answers ----


def _iter_json(dir_: Path):
    if not dir_.exists():
        return
    for f in sorted(dir_.glob("*.json")):
        try:
            yield f, json.loads(f.read_text())
        except json.JSONDecodeError as exc:
            log.warning("invalid JSON in %s: %s", f.name, exc)


def load_triage(root: Path, week: str, shortlist: list[Paper]) -> dict[str, Triage]:
    """Read and validate triage answers.

    Returns only the entries that survived validation. `assemble` fills the gaps
    lexically, so a batch the model mangled costs you that batch's judgement and nothing
    more.
    """
    valid_ids = {p.id for p in shortlist}
    out: dict[str, Triage] = {}
    seen_files = 0

    for f, payload in _iter_json(work_dir(root, week) / "triage_out"):
        seen_files += 1
        rows = payload if isinstance(payload, list) else payload.get("papers", [])
        if not isinstance(rows, list):
            log.warning("%s: expected a list of rows", f.name)
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                t = Triage.model_validate(row)
            except ValidationError as exc:
                log.warning("%s: dropping invalid row %s (%s)", f.name, row.get("id"), exc.error_count())
                continue
            if t.id not in valid_ids:
                log.warning("%s: row for unknown id %s", f.name, t.id)
                continue
            out[t.id] = t

    missing = len(valid_ids) - len(out)
    if seen_files == 0:
        log.warning("no triage output found for %s — ranking will be lexical", week)
    elif missing:
        log.warning("%d of %d shortlisted papers have no valid triage row", missing, len(valid_ids))
    return out


def load_deep(root: Path, week: str) -> dict[str, dict]:
    """Read deep-dive answers, keyed by paper id.

    Deep-dive output only decorates a card; it never changes the ordering. A missing file
    costs the one-line "why" and nothing else.
    """
    out: dict[str, dict] = {}
    for f, payload in _iter_json(work_dir(root, week) / "deep_out"):
        if not isinstance(payload, dict):
            log.warning("%s: expected an object", f.name)
            continue
        pid = payload.get("id")
        if not pid:
            log.warning("%s: missing id", f.name)
            continue
        why = (payload.get("why") or "").strip()
        if not why:
            log.warning("%s: missing why", f.name)
            continue
        action = payload.get("action")
        out[pid] = {
            "why": why,
            "touches": [t for t in (payload.get("touches") or []) if isinstance(t, str)][:4],
            "action": action if action in VALID_ACTIONS else "skim",
        }
    return out


def load_blindspot(root: Path, week: str, pool: dict[str, Paper]) -> dict | None:
    """Read the single blindspot pick, if one was produced and it names a real paper."""
    f = work_dir(root, week) / "blindspot_out.json"
    if not f.exists():
        return None
    try:
        payload = json.loads(f.read_text())
    except json.JSONDecodeError as exc:
        log.warning("invalid blindspot JSON: %s", exc)
        return None
    if not isinstance(payload, dict):
        return None

    pid = payload.get("id")
    if pid not in pool:
        log.warning("blindspot names unknown id %r — dropping", pid)
        return None
    conf = payload.get("confidence")
    return {
        "id": pid,
        "why": (payload.get("why") or "").strip(),
        "connection": (payload.get("connection") or "").strip(),
        "confidence": conf if conf in VALID_CONFIDENCE else "low",
        "action": payload.get("action") if payload.get("action") in VALID_ACTIONS else "track",
    }


def clear(root: Path, week: str) -> None:
    """Remove the scratch prompts once their answers are folded into the issue JSON."""
    import shutil

    wd = work_dir(root, week)
    if wd.exists():
        shutil.rmtree(wd)


def pending(root: Path, week: str) -> dict[str, int]:
    """What still needs an answer — the Routine uses this to know when it is done."""
    wd = work_dir(root, week)

    def count(sub: str) -> int:
        d = wd / sub
        return len(list(d.glob("*.md"))) if d.exists() else 0

    def answered(sub: str) -> int:
        d = wd / sub
        return len(list(d.glob("*.json"))) if d.exists() else 0

    return {
        "triage_prompts": count("triage"),
        "triage_answers": answered("triage_out"),
        "deep_prompts": count("deep"),
        "deep_answers": answered("deep_out"),
        "blindspot_prompt": 1 if (wd / "blindspot.md").exists() else 0,
        "blindspot_answer": 1 if (wd / "blindspot_out.json").exists() else 0,
    }
