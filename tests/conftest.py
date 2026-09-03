from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from radar.config import load_config
from radar.models import Paper

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def cfg():
    return load_config(REPO)


def make_paper(**kw) -> Paper:
    base = dict(
        id="10.1101/2026.01.01.000001",
        title="A title",
        abstract="An abstract.",
        authors=["Doe J"],
        date=date(2026, 1, 1),
        source="biorxiv",
        venue="bioRxiv",
        subject="biochemistry",
    )
    base.update(kw)
    # Every real source sets both; mirror that so DOI-based dedupe is exercised honestly.
    if "doi" not in kw and str(base["id"]).startswith("10."):
        base["doi"] = base["id"]
    return Paper(**base)


@pytest.fixture
def paper():
    return make_paper
