"""HTTP session, retries, and JSON extraction for NSE APIs."""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Mapping
from urllib.parse import urlparse

import requests

from nse_downloader.config import (
    PAGE_URLS,
    DATASETS,
    DatasetConfig,
    AppSettings,
    _nifty_variation_records,
)
from nse_downloader.logger import utc_now_iso

logger = logging.getLogger("nse_downloader.client")


class NSEClientError(Exception):
    """Raised when acquisition fails after retries or response is unusable."""


def _browser_headers(referer: str) -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": referer,
        "Origin": "https://www.nseindia.com",
        "Connection": "keep-alive",
    }


class NSEClient:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._session = requests.Session()

    def warm_session(self, referer_path_key: str) -> None:
        """Load a market-data HTML page to obtain cookies (Akamai)."""
        page_url = PAGE_URLS.get(referer_path_key, PAGE_URLS["top-gainers-losers"])
        cfg = self._settings.session_init_path.strip()
        if cfg.startswith("http"):
            init_path = urlparse(cfg).path
        elif cfg.startswith("/"):
            init_path = cfg
        else:
            init_path = urlparse(page_url).path
        if not init_path.startswith("/"):
            init_path = "/" + init_path.lstrip("/")
        init_url = self._settings.base_url + init_path
        headers = _browser_headers(page_url)
        logger.info("Session warm-up GET %s", init_url)
        r = self._request_with_retries("GET", init_url, headers=headers, params=None)
        if not r.ok:
            logger.warning("Session warm-up HTTP %s for %s", r.status_code, init_url)

    def close(self) -> None:
        self._session.close()

    def _sleep_backoff(self, attempt: int) -> None:
        base = self._settings.backoff_factor_seconds * (2 ** max(0, attempt - 1))
        jitter = random.uniform(0, 0.35)
        time.sleep(base + jitter)

    def _request_with_retries(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str] | None,
    ) -> requests.Response:
        last_exc: Exception | None = None
        for attempt in range(1, self._settings.max_retries + 1):
            try:
                logger.debug("%s %s attempt=%s params=%s", method, url, attempt, params)
                r = self._session.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    timeout=self._settings.timeout,
                )
                if r.status_code in (429, 500, 502, 503, 504):
                    logger.warning(
                        "%s %s -> HTTP %s (attempt %s/%s)",
                        method,
                        url,
                        r.status_code,
                        attempt,
                        self._settings.max_retries,
                    )
                    if attempt < self._settings.max_retries:
                        self._sleep_backoff(attempt)
                        continue
                return r
            except requests.RequestException as e:
                last_exc = e
                logger.warning(
                    "%s %s failed: %s (attempt %s/%s)",
                    method,
                    url,
                    e,
                    attempt,
                    self._settings.max_retries,
                )
                if attempt < self._settings.max_retries:
                    self._sleep_backoff(attempt)
                    continue
                raise NSEClientError(f"Request failed after retries: {url}") from e
        if last_exc:
            raise NSEClientError(f"Request failed: {url}") from last_exc
        raise NSEClientError(f"Unreachable: {url}")

    def fetch_json(self, path: str, referer_page_key: str, params: dict[str, str] | None) -> Any:
        referer = PAGE_URLS.get(referer_page_key, PAGE_URLS["top-gainers-losers"])
        url = self._settings.base_url + path
        headers = _browser_headers(referer)
        r = self._request_with_retries("GET", url, headers=headers, params=params)
        if not r.ok:
            raise NSEClientError(f"HTTP {r.status_code} for {url}")
        try:
            return r.json()
        except ValueError as e:
            raise NSEClientError(f"Invalid JSON from {url}") from e

    def acquire_dataset(self, ds: DatasetConfig) -> list[dict[str, Any]]:
        """Return list of row dicts for one dataset."""
        self.warm_session(ds.referer_page_key)

        if ds.id == "top-gainers-losers":
            return self._acquire_top_gainers_losers(ds)

        if len(ds.api_paths) != 1:
            raise NSEClientError(f"Unexpected api_paths for {ds.id}")
        payload = self.fetch_json(ds.api_paths[0], ds.referer_page_key, None)
        if not isinstance(payload, Mapping):
            raise NSEClientError(f"Expected JSON object for {ds.id}")
        rows = ds.extractor(payload)
        if ds.enrich:
            rows = ds.enrich(rows)
        logger.info(
            "[%s] fetched at %s | records=%s",
            ds.id,
            utc_now_iso(),
            len(rows),
        )
        return rows

    def _acquire_top_gainers_losers(self, ds: DatasetConfig) -> list[dict[str, Any]]:
        path = "/api/live-analysis-variations"
        out: list[dict[str, Any]] = []
        for idx, side in (("gainers", "gainer"), ("loosers", "loser")):
            payload = self.fetch_json(path, ds.referer_page_key, {"index": idx})
            if not isinstance(payload, Mapping):
                raise NSEClientError("top-gainers-losers: expected object")
            rows = _nifty_variation_records(payload)
            for r in rows:
                r = dict(r)
                r["variation_side"] = side
                out.append(r)
            logger.info(
                "[%s] %s at %s | records=%s",
                ds.id,
                side,
                utc_now_iso(),
                len(rows),
            )
        return out
