"""The blindspot channel (spec §4).

The failure this addresses: the radar gets better at finding what you already know you
want, and correspondingly worse at everything else.

The sample must come from the *rejected* pool. A pick drawn from the shortlist would just
be the sixth-best hit, which is not a blindspot — it is a rounding error on the front page.
"""

from __future__ import annotations

import logging
import random

from .config import Config
from .models import Paper, PrefilterVerdict

log = logging.getLogger("radar.blindspot")


def _stratum(paper: Paper) -> str:
    """The quota bucket a paper belongs to, matching the keys in sources.yaml."""
    if paper.source == "arxiv":
        return f"arxiv:{paper.subject}"
    if paper.source in ("biorxiv", "medrxiv"):
        return f"{paper.source}_other"
    return paper.source


def sample(
    rejected: list[Paper],
    verdicts: dict[str, PrefilterVerdict],
    cfg: Config,
    *,
    seed: int | None = None,
) -> list[Paper]:
    """A stratified sample of the rejected pool.

    Two biases are deliberate:

    * **Guaranteed quotas** for sources that are structurally under-weighted in the main
      funnel — `cond-mat.soft`, `physics.bio-ph`, non-protein biology. Left to chance they
      would almost never appear, because the main funnel is built to ignore them.
    * **Low lexical overlap is over-represented.** A record that *nearly* passed the filter
      is the least interesting thing in this pool: it is a near-miss on what you already
      look for. The genuinely useful blindspot candidate is the one that matched nothing.
    """
    rng = random.Random(seed)
    quotas: dict[str, int] = cfg.sources.get("blindspot_quota") or {}
    target = int(cfg.sources.get("blindspot_sample_size", 150))

    buckets: dict[str, list[Paper]] = {}
    for p in rejected:
        buckets.setdefault(_stratum(p), []).append(p)

    def pick(pool: list[Paper], n: int) -> list[Paper]:
        """Weighted draw favouring low lexical overlap, without replacement."""
        if n <= 0 or not pool:
            return []
        if len(pool) <= n:
            return list(pool)
        weights = []
        for p in pool:
            v = verdicts.get(p.id)
            score = v.lexical_score if v else 0.0
            # Monotonically decreasing in lexical score, and never zero, so a near-miss can
            # still be drawn — just rarely.
            weights.append(1.0 / (1.0 + score))
        chosen: list[Paper] = []
        pool = list(pool)
        weights = list(weights)
        for _ in range(n):
            total = sum(weights)
            if total <= 0:
                break
            r = rng.uniform(0, total)
            acc = 0.0
            for i, w in enumerate(weights):
                acc += w
                if acc >= r:
                    chosen.append(pool.pop(i))
                    weights.pop(i)
                    break
        return chosen

    out: list[Paper] = []
    taken: set[str] = set()

    # Quotas first, so the under-weighted sources cannot be squeezed out by volume.
    for stratum, n in quotas.items():
        got = pick(buckets.get(stratum, []), n)
        out.extend(got)
        taken.update(p.id for p in got)
        if stratum not in buckets:
            log.debug("blindspot quota %s: nothing in the pool this week", stratum)

    # Fill the remainder from everything not already taken.
    remaining = [p for p in rejected if p.id not in taken]
    out.extend(pick(remaining, target - len(out)))

    rng.shuffle(out)      # order should not leak the stratum back to the model
    log.info(
        "blindspot sample: %d of %d rejected records across %d strata",
        len(out), len(rejected), len(buckets),
    )
    return out
