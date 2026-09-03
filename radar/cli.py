"""`radar` command line.

The pipeline is split so the deterministic stages always run on their own, with no model
involved:

    radar collect    fetch -> dedupe -> prefilter -> raw archive -> work/ prompt files
    radar select     apply triage answers, write the deep-dive and blindspot prompts
    radar assemble   validate the judgement files, rank, write data/ + digests/ + the site
    radar run        all of the above  (--no-llm skips judgement entirely)

The three-step form is what the weekly Routine drives: it runs `collect`, answers the
prompt files in `work/`, runs `select`, answers again, then runs `assemble`.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click

from .assemble import assemble, gather
from .config import load_config
from .render.markdown import write_markdown
from .render.rss import write_feed
from .render.site import build_site
from .store import prune_raw, read_all_issues, write_index, write_issue, write_status
from .util import current_week, week_end

STATE = "work/{week}/state.json"


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)-7s %(name)-22s %(message)s",
        stream=sys.stderr,
    )
    # httpx logs every request at INFO, which drowns out the funnel we actually want to see.
    logging.getLogger("httpx").setLevel(logging.WARNING)


def _print_funnel(stats, health) -> None:
    click.echo("")
    click.echo("  funnel")
    click.echo(f"    fetched      {stats.fetched:>7,}")
    click.echo(f"    new          {stats.new:>7,}")
    click.echo(f"    shortlisted  {stats.shortlisted:>7,}")
    click.echo(f"    rejected     {stats.rejected:>7,}   (retained for the blindspot pool)")
    click.echo("")
    click.echo("  sources")
    for h in health:
        mark = "ok  " if h.ok else "FAIL"
        flag = "  ← under expected minimum" if h.under_covered else ""
        detail = f"  {h.error}" if h.error else ""
        click.echo(f"    {mark} {h.source:<10} {h.fetched:>6,}{flag}{detail}")


def _save_state(cfg, week: str, shortlist, health, stats, now_published, extras) -> None:
    """Persist what `collect` learned so `select` and `assemble` need no refetch."""
    p = cfg.root / STATE.format(week=week)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {
                "week": week,
                "shortlist_ids": [s.id for s in shortlist],
                "rejected_ids": [s.id for s in extras["rejected"]],
                "health": [h.model_dump() for h in health],
                "stats": stats.model_dump(),
                "now_published": [n.model_dump() for n in now_published],
                "window": [extras["window"][0].isoformat(), extras["window"][1].isoformat()],
            },
            indent=2,
        )
    )


def _finalise(cfg, week: str, issue) -> None:
    write_issue(cfg.root, issue)
    write_markdown(cfg.root, issue)
    write_status(cfg.root, issue)
    issues = read_all_issues(cfg.root)
    write_index(cfg.root, issues)
    write_feed(cfg, issues)
    build_site(cfg, week)

    removed = prune_raw(cfg.root, int(cfg.profile.get("retention", {}).get("raw_months", 6)))
    if removed:
        click.echo(f"pruned {len(removed)} raw archives past retention")

    click.echo(f"\nwrote data/issues/{week}.json, digests/{week}.md and the site")
    if issue.degraded:
        click.secho("run was DEGRADED:", fg="yellow")
        for n in issue.notes:
            click.secho(f"  - {n}", fg="yellow")


@click.group()
@click.option("--root", type=click.Path(path_type=Path), default=None, help="Repo root.")
@click.option("--config", "config_dir", type=click.Path(path_type=Path), default=None,
              help="Config directory (default: <root>/config). Use to run a second profile.")
@click.option("-v", "--verbose", is_flag=True)
@click.pass_context
def cli(ctx: click.Context, root: Path | None, config_dir: Path | None, verbose: bool) -> None:
    _setup_logging(verbose)
    ctx.obj = load_config(root, config_dir)


# --------------------------------------------------------------------- one-shot ----


@cli.command()
@click.option("--week", default=None, help="ISO week, e.g. 2026-W36. Default: current week.")
@click.option("--no-llm", is_flag=True, help="Skip judgement; rank lexically. No tokens spent.")
@click.option("--cached", is_flag=True, help="Replay data/raw/<week>.jsonl.gz instead of fetching.")
@click.option("--dry-run", is_flag=True, help="Print the funnel and stop; write nothing.")
@click.pass_obj
def run(cfg, week: str | None, no_llm: bool, cached: bool, dry_run: bool) -> None:
    """Run the whole weekly pipeline in one go."""
    week = week or current_week()
    click.echo(f"radar: {week}  (window ends {week_end(week)})")

    shortlist, health, stats, now_published, extras = gather(cfg, week, use_cache=cached)
    _print_funnel(stats, health)

    if dry_run:
        click.echo("\ndry run: nothing written")
        return

    triage = deep = blindspot = None
    if not no_llm:
        from .work import load_blindspot, load_deep, load_triage

        triage = load_triage(cfg.root, week, shortlist)
        deep = load_deep(cfg.root, week)
        blindspot = _blindspot_from_answers(cfg, week, extras)

    issue = assemble(
        cfg, week, shortlist, health, stats, now_published, extras,
        triage=triage, deep=deep, blindspot=blindspot,
    )
    _finalise(cfg, week, issue)


# ----------------------------------------------------------------- three-phase ----


@cli.command()
@click.option("--week", default=None)
@click.option("--cached", is_flag=True, help="Replay the raw archive instead of fetching.")
@click.pass_obj
def collect(cfg, week: str | None, cached: bool) -> None:
    """Fetch and filter, then write the triage prompts into work/<week>/."""
    from .blindspot import sample
    from .work import prepare_blindspot, prepare_triage

    week = week or current_week()
    click.echo(f"radar collect: {week}")

    shortlist, health, stats, now_published, extras = gather(cfg, week, use_cache=cached)
    _print_funnel(stats, health)
    _save_state(cfg, week, shortlist, health, stats, now_published, extras)

    batches = prepare_triage(cfg, week, shortlist)
    pool = sample(extras["rejected"], extras["verdicts"], cfg, seed=hash(week) & 0xFFFF)
    prepare_blindspot(cfg, week, pool)

    click.echo(f"\nwrote {len(batches)} triage batches to work/{week}/triage/")
    click.echo(f"wrote the blindspot prompt over {len(pool)} rejected records")
    click.echo(f"\nnext: answer each batch into work/{week}/triage_out/, then `radar select`")


@cli.command()
@click.option("--week", default=None)
@click.pass_obj
def select(cfg, week: str | None) -> None:
    """Apply the triage answers and write the deep-dive prompts."""
    from .collect import read_raw
    from .rank import build_scored, select_front_page
    from .work import load_triage, prepare_deep

    week = week or current_week()
    state = json.loads((cfg.root / STATE.format(week=week)).read_text())
    papers = {p.id: p for p in read_raw(cfg.root, week)}
    shortlist = [papers[i] for i in state["shortlist_ids"] if i in papers]

    from .prefilter import judge

    verdicts = {p.id: judge(p, cfg) for p in shortlist}
    triage = load_triage(cfg.root, week, shortlist)
    click.echo(f"triage: {len(triage)} of {len(shortlist)} shortlisted papers have judgement")

    scored = [build_scored(p, verdicts[p.id], triage.get(p.id), cfg) for p in shortlist]
    n = int(cfg.profile["front_page"].get("deep_dive_n", 15))
    top = sorted(scored, key=lambda s: s.score, reverse=True)[:n]
    written = prepare_deep(cfg, week, [papers[s.id] for s in top])

    click.echo(f"wrote {len(written)} deep-dive prompts to work/{week}/deep/")
    click.echo(f"\nnext: answer each into work/{week}/deep_out/, then `radar assemble`")


@cli.command(name="assemble")
@click.option("--week", default=None)
@click.option("--keep-work", is_flag=True, help="Do not delete work/<week>/ afterwards.")
@click.pass_obj
def assemble_cmd(cfg, week: str | None, keep_work: bool) -> None:
    """Validate the judgement files, rank, and write everything."""
    from .collect import read_raw
    from .models import NowPublished, SourceHealth, Stats
    from .prefilter import judge
    from .work import clear, load_deep, load_triage

    week = week or current_week()
    state = json.loads((cfg.root / STATE.format(week=week)).read_text())
    papers = {p.id: p for p in read_raw(cfg.root, week)}
    shortlist = [papers[i] for i in state["shortlist_ids"] if i in papers]
    rejected = [papers[i] for i in state["rejected_ids"] if i in papers]

    from datetime import date as _date

    extras = {
        "verdicts": {p.id: judge(p, cfg) for p in [*shortlist, *rejected]},
        "rejected": rejected,
        "window": (_date.fromisoformat(state["window"][0]), _date.fromisoformat(state["window"][1])),
    }
    health = [SourceHealth(**h) for h in state["health"]]
    stats = Stats(**state["stats"])
    now_published = [NowPublished(**n) for n in state["now_published"]]

    issue = assemble(
        cfg, week, shortlist, health, stats, now_published, extras,
        triage=load_triage(cfg.root, week, shortlist),
        deep=load_deep(cfg.root, week),
        blindspot=_blindspot_from_answers(cfg, week, extras),
    )
    _finalise(cfg, week, issue)

    if not keep_work:
        clear(cfg.root, week)


def _blindspot_from_answers(cfg, week: str, extras: dict):
    """Turn the blindspot answer file into a Scored entry, if there is one."""
    from .rank import build_scored
    from .work import load_blindspot

    pool = {p.id: p for p in extras["rejected"]}
    answer = load_blindspot(cfg.root, week, pool)
    if not answer:
        return None
    paper = pool[answer["id"]]
    s = build_scored(paper, extras["verdicts"][paper.id], None, cfg)
    s.why = answer["why"] or s.reason
    s.connection = answer["connection"]
    s.confidence = answer["confidence"]
    s.action = answer["action"]
    return s


# --------------------------------------------------------------------- tuning ----


@cli.command(name="eval")
@click.option("--offline", is_flag=True, help="Use only the eval/cache; never hit the network.")
@click.option("--json", "as_json", is_flag=True, help="Print the raw report instead of a summary.")
@click.pass_obj
def eval_cmd(cfg, offline: bool, as_json: bool) -> None:
    """Check the filter against eval/goldset.yaml and price any suggested changes."""
    from .evaluate import run_eval, write_report

    report = run_eval(cfg, offline=offline)
    write_report(cfg.root, report)

    if as_json:
        click.echo(json.dumps(report, indent=2))
        return

    click.echo("")
    for p in report["papers"]:
        status = p.get("status", "?")
        colour = {"pass": "green", "weak": "yellow", "fail": "red"}.get(status, "white")
        click.secho(f"  [{status.upper():>10}] {p.get('title', '')[:76]}", fg=colour)
        if p.get("note"):
            click.echo(f"               {p['note']}")
        for step in p.get("chain", []):
            click.echo(f"               · {step}")
        if p.get("rescue_hint"):
            click.secho(f"               → {p['rescue_hint']}", fg="cyan")
        click.echo("")

    if report["checked"]:
        click.echo(f"  {report['passed']}/{report['checked']} would surface "
                   f"(recall {report['recall']})")
    if report["unresolved"]:
        click.secho(f"  unresolved identifiers: {', '.join(report['unresolved'])}", fg="yellow")

    if report["suggestions"]:
        click.echo("\n  suggested terms — each priced against the archived weeks:\n")
        for s in report["suggestions"]:
            click.echo(
                f"    {s['term']:<34} recovers {s['recovers']}, "
                f"admits +{s['admits_per_week']}/week  [{s['verdict']}]"
            )
        click.echo("\n  Nothing is applied automatically. Edit config/categories.yaml yourself.")


@cli.command()
@click.option("--min-age-days", default=60, show_default=True)
@click.option("--max-age-days", default=190, show_default=True)
@click.option("--citations", "citation_threshold", default=5, show_default=True,
              help="Citation count that makes a rejected paper a miss.")
@click.pass_obj
def audit(cfg, min_age_days: int, max_age_days: int, citation_threshold: int) -> None:
    """Recall audit: what did the filter reject 2-6 months ago that has since mattered?"""
    from .audit import run_audit, write_audit

    report = run_audit(
        cfg, min_age_days=min_age_days, max_age_days=max_age_days,
        citation_threshold=citation_threshold,
    )
    write_audit(cfg.root, report)

    if report.get("note"):
        click.echo(report["note"])
        return

    click.echo(f"\n  checked {report['checked']} rejected papers from "
               f"{len(report['weeks'])} weeks")
    click.secho(f"  {report['miss_count']} crossed the bar\n",
                fg="red" if report["miss_count"] else "green")

    for m in report["misses"][:20]:
        click.echo(f"    {m['cited_by_count']:>4} cites  {m['title'][:66]}")
        click.secho(f"               rejected because: {m['rejected_because']}", fg="yellow")
        if m["in_tracked_journal"]:
            click.echo(f"               now in {m['venue']}")

    if report["misses_by_rule"]:
        click.echo("\n  misses by rule — which rule is costing you the most recall:")
        for rule, n in report["misses_by_rule"].items():
            click.echo(f"    {n:>4}  {rule}")


# --------------------------------------------------------------------- utility ----


@cli.command()
@click.option("--week", default=None, help="Week to feature on the front page.")
@click.pass_obj
def render(cfg, week: str | None) -> None:
    """Re-render the site, digests and feed from data/. Never touches the network."""
    issues = read_all_issues(cfg.root)
    for issue in issues:
        write_markdown(cfg.root, issue)
    write_index(cfg.root, issues)
    write_feed(cfg, issues)
    written = build_site(cfg, week)
    click.echo(f"rendered {len(issues)} issues -> {len(written)} files")


@cli.command()
@click.option("--week", default=None)
@click.pass_obj
def status(cfg, week: str | None) -> None:
    """What still needs an answer in work/<week>/ — the Routine polls this."""
    from .work import pending

    week = week or current_week()
    p = pending(cfg.root, week)
    click.echo(json.dumps(p, indent=2))
    done = (
        p["triage_prompts"] > 0
        and p["triage_answers"] >= p["triage_prompts"]
        and p["deep_answers"] >= p["deep_prompts"]
    )
    click.echo("ready for assemble" if done else "still waiting on answers")


@cli.command()
@click.pass_obj
def weeks(cfg) -> None:
    """List the archived weeks."""
    from .collect import available_raw_weeks
    from .store import all_weeks

    raw = set(available_raw_weeks(cfg.root))
    for w in all_weeks(cfg.root):
        click.echo(f"  {w}  {'raw ✔' if w in raw else 'raw —'}")


@cli.command(name="current-week")
def current_week_cmd() -> None:
    """Print the current ISO week key."""
    click.echo(current_week())


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
