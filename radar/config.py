"""Config loading. Everything lab-specific lives in `config/`; no code change should ever
be needed to retarget the radar at another group (spec §0.2, §10)."""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .util import compile_terms

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True, eq=False)
class Category:
    id: str
    name: str
    weight: float
    description: str
    boost: dict[str, float] = field(default_factory=dict)
    gate_general_cs: bool = False

    @functools.cached_property
    def boost_patterns(self) -> list[tuple[str, float, "re.Pattern[str]"]]:
        return [(t, w, p) for (t, p), w in zip(compile_terms(self.boost), self.boost.values())]


@dataclass(frozen=True)
class Config:
    root: Path
    profile: dict[str, Any]
    categories_raw: dict[str, Any]
    sources: dict[str, Any]

    # --- derived -----------------------------------------------------------------

    @functools.cached_property
    def categories(self) -> list[Category]:
        return [
            Category(
                id=c["id"],
                name=c["name"],
                weight=float(c["weight"]),
                description=c.get("description", "").strip(),
                boost={k.lower(): float(v) for k, v in (c.get("boost") or {}).items()},
                gate_general_cs=bool(c.get("gate_general_cs", False)),
            )
            for c in self.categories_raw["categories"]
        ]

    @functools.cached_property
    def category_by_id(self) -> dict[str, Category]:
        return {c.id: c for c in self.categories}

    @functools.cached_property
    def hard_include(self) -> list[str]:
        return [p.lower() for p in self.categories_raw.get("hard_include_phrases", [])]

    @functools.cached_property
    def must_any(self) -> list[str]:
        return [p.lower() for p in self.categories_raw.get("must_any", [])]

    @functools.cached_property
    def hard_exclude(self) -> list[str]:
        return [p.lower() for p in self.categories_raw.get("hard_exclude", [])]

    @functools.cached_property
    def general_cs_gate(self) -> dict[str, list[str]]:
        """Tiered gate for the general-CS arXiv categories. See categories.yaml."""
        g = self.categories_raw.get("general_cs_gate") or {}
        return {
            "strong": [t.lower() for t in g.get("strong", [])],
            "weak_needs_domain": [t.lower() for t in g.get("weak_needs_domain", [])],
            "domain": [t.lower() for t in g.get("domain", [])],
        }

    @functools.cached_property
    def hard_include_patterns(self):
        return compile_terms(self.hard_include)

    @functools.cached_property
    def must_any_patterns(self):
        return compile_terms(self.must_any)

    @functools.cached_property
    def hard_exclude_patterns(self):
        return compile_terms(self.hard_exclude)

    @functools.cached_property
    def gate_patterns(self) -> dict[str, list]:
        return {k: compile_terms(v) for k, v in self.general_cs_gate.items()}

    @functools.cached_property
    def venue_tiers(self) -> dict[str, float]:
        """Flattened to `lowercased venue name -> tier`."""
        out: dict[str, float] = {}
        for tier, venues in (self.categories_raw.get("venue_tiers") or {}).items():
            for v in venues:
                out[v.lower()] = float(tier)
        return out

    @functools.cached_property
    def weights(self) -> dict[str, float]:
        return {k: float(v) for k, v in self.profile["weights"].items()}

    @functools.cached_property
    def watchlist(self) -> dict[str, str]:
        """`normalised key -> original entry`, e.g. `"king n" -> "King NP"`.

        Matching on surname + first initial only: author strings arrive in wildly
        different shapes across sources ("King, N.P.", "Neil P. King", "King NP") and
        over-precise matching would silently drop the highest-value channel we have.
        """
        out = {}
        for entry in self.sources.get("watchlist_authors", []):
            out[normalise_author(entry)] = entry
        return out

    @functools.cached_property
    def open_threads(self) -> list[str]:
        return list(self.profile.get("open_threads", []))

    def source_cfg(self, name: str) -> dict[str, Any]:
        return self.sources.get(name, {}) or {}


def normalise_author(name: str) -> str:
    """Reduce an author string to `surname + first initial`, lowercased.

    Handles "King NP", "King, Neil P.", "Neil P. King" and "N. P. King".
    """
    name = name.strip().replace(".", " ")
    if not name:
        return ""
    if "," in name:
        surname, rest = name.split(",", 1)
        initial = next((c for c in rest if c.isalpha()), "")
        return f"{surname.strip().lower()} {initial.lower()}".strip()

    parts = [p for p in name.split() if p]
    if len(parts) == 1:
        return parts[0].lower()

    # "King NP" — trailing token is an all-caps initial block.
    last = parts[-1]
    if last.isupper() and len(last) <= 3:
        return f"{' '.join(parts[:-1]).lower()} {last[0].lower()}"

    # "Neil P. King" / "N P King" — surname last, first initial from the first token.
    return f"{last.lower()} {parts[0][0].lower()}"


def load_config(root: Path | str | None = None, config_dir: Path | str | None = None) -> Config:
    root = Path(root) if root else REPO_ROOT
    cdir = Path(config_dir) if config_dir else root / "config"
    return Config(
        root=root,
        profile=yaml.safe_load((cdir / "profile.yaml").read_text()),
        categories_raw=yaml.safe_load((cdir / "categories.yaml").read_text()),
        sources=yaml.safe_load((cdir / "sources.yaml").read_text()),
    )
