"""HTTP fetch có retry/backoff/timeout + User-Agent từ env (CRAWLER_USER_AGENT)."""

from __future__ import annotations

import os
import time

import httpx

_UA = os.getenv("CRAWLER_USER_AGENT", "bizino-vrg-bot/1.0 (+market-data)")
_TIMEOUT = float(os.getenv("CRAWLER_TIMEOUT", "15"))


def _get(url: str, *, retries: int = 3, backoff: float = 1.5, **kw: object) -> httpx.Response:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            resp = httpx.get(
                url,
                headers={"User-Agent": _UA},
                timeout=_TIMEOUT,
                follow_redirects=True,
                **kw,  # type: ignore[arg-type]
            )
            resp.raise_for_status()
            return resp
        except Exception as exc:  # noqa: BLE001 - cô lập, thử lại
            last = exc
            if attempt < retries - 1:
                time.sleep(backoff ** attempt)
    assert last is not None
    raise last


def fetch_text(url: str, **kw: object) -> str:
    return _get(url, **kw).text


def fetch_json(url: str, **kw: object) -> dict:
    return _get(url, **kw).json()
