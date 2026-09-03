"""Source protocol plus the shared, deliberately polite HTTP client.

Every source is isolated: one failing degrades the digest, it never fails the run
(spec §9). Sources raise freely; `collect.py` catches per-source.
"""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any, Protocol

import httpx

from ..models import Paper

log = logging.getLogger("radar.sources")

USER_AGENT = "research-radar/0.1 (+https://olivernagl.github.io; mailto:olnagl@ethz.ch)"


class Source(Protocol):
    name: str

    def fetch(self, start: date, end: date) -> list[Paper]: ...


class Fetcher:
    """A tiny retrying HTTP client.

    bioRxiv rate-limits under sustained polling — a live check of eleven consecutive
    category queries had one fail transiently — so every source goes through this.
    """

    def __init__(
        self,
        *,
        timeout: float = 40.0,
        retries: int = 4,
        min_interval: float = 0.0,
    ) -> None:
        self.client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,     # arXiv 301s plain http to https
        )
        self.retries = retries
        self.min_interval = min_interval
        self._last_call = 0.0

    def _throttle(self) -> None:
        if self.min_interval <= 0:
            return
        wait = self.min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)

    def get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        last: Exception | None = None
        for attempt in range(self.retries):
            self._throttle()
            try:
                r = self.client.get(url, params=params)
                self._last_call = time.monotonic()
                if r.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError(
                        f"{r.status_code}", request=r.request, response=r
                    )
                r.raise_for_status()
                return r
            except Exception as exc:                      # noqa: BLE001 - retried below
                last = exc
                self._last_call = time.monotonic()
                backoff = 1.5 * (2**attempt)
                log.debug("retry %s/%s for %s after %s", attempt + 1, self.retries, url, exc)
                time.sleep(backoff)
        raise RuntimeError(f"GET {url} failed after {self.retries} attempts: {last}")

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        return self.get(url, params).json()

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "Fetcher":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
