"""
URL and schema configuration for NSE datasets.

Page URLs (human-readable) are listed in README; API paths are what the site
loads after session cookies are established.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import yaml

# Pages corresponding to each dataset (for Referer header and documentation)
PAGE_URLS: Mapping[str, str] = {
    "top-gainers-losers": "https://www.nseindia.com/market-data/top-gainers-losers",
    "upper-band-hitters": "https://www.nseindia.com/market-data/upper-band-hitters",
    "volume-gainers-spurts": "https://www.nseindia.com/market-data/volume-gainers-spurts",
    "52-week-high-equity-market": "https://www.nseindia.com/market-data/52-week-high-equity-market",
}


def _nifty_variation_records(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Extract NIFTY index rows from live-analysis-variations API."""
    block = payload.get("NIFTY")
    if not isinstance(block, Mapping):
        return []
    data = block.get("data")
    if not isinstance(data, list):
        return []
    out: list[dict[str, Any]] = []
    for row in data:
        if isinstance(row, Mapping):
            out.append(dict(row))
    return out


def _records_upper_band(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    upper = payload.get("upper")
    if not isinstance(upper, Mapping):
        return []
    all_sec = upper.get("AllSec")
    if not isinstance(all_sec, Mapping):
        return []
    data = all_sec.get("data")
    if not isinstance(data, list):
        return []
    return [dict(r) for r in data if isinstance(r, Mapping)]


def _records_simple_data(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if not isinstance(data, list):
        return []
    return [dict(r) for r in data if isinstance(r, Mapping)]


@dataclass(frozen=True)
class DatasetConfig:
    """One downloadable dataset."""

    id: str
    description: str
    api_paths: tuple[str, ...]
    # Builds query string; None means no query
    query_builder: Callable[[], str | None]
    extractor: Callable[[Mapping[str, Any]], list[dict[str, Any]]]
    required_columns: tuple[str, ...]
    dedupe_keys: tuple[str, ...]
    referer_page_key: str
    # Optional post-extraction: add constant columns
    enrich: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None = None


def _enrich_top_variation(side: str) -> Callable[[list[dict[str, Any]]], list[dict[str, Any]]]:
    def _go(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for r in rows:
            r["variation_side"] = side
        return rows

    return _go


def _combine_gainers_losers(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Not used as extractor — gainers/losers need two HTTP calls; see client."""
    return []


DEFAULT_REQUIRED: dict[str, tuple[str, ...]] = {
    "top-gainers-losers": ("symbol", "series", "ltp", "perChange"),
    "upper-band-hitters": ("symbol", "series", "ltp", "pChange"),
    "volume-gainers-spurts": ("symbol", "ltp", "pChange"),
    "52-week-high-equity-market": ("symbol", "ltp", "pChange"),
}

DATASETS: dict[str, DatasetConfig] = {
    "top-gainers-losers": DatasetConfig(
        id="top-gainers-losers",
        description="NIFTY top gainers and losers (single CSV with variation_side)",
        api_paths=("/api/live-analysis-variations",),
        query_builder=lambda: None,  # overridden in client for two fetches
        extractor=_combine_gainers_losers,
        required_columns=DEFAULT_REQUIRED["top-gainers-losers"],
        dedupe_keys=("symbol", "series", "variation_side"),
        referer_page_key="top-gainers-losers",
        enrich=None,
    ),
    "upper-band-hitters": DatasetConfig(
        id="upper-band-hitters",
        description="Securities hitting the upper price band (All securities)",
        api_paths=("/api/live-analysis-price-band-hitter",),
        query_builder=lambda: None,
        extractor=_records_upper_band,
        required_columns=DEFAULT_REQUIRED["upper-band-hitters"],
        dedupe_keys=("symbol", "series"),
        referer_page_key="upper-band-hitters",
    ),
    "volume-gainers-spurts": DatasetConfig(
        id="volume-gainers-spurts",
        description="Volume gainers / spurts",
        api_paths=("/api/live-analysis-volume-gainers",),
        query_builder=lambda: None,
        extractor=_records_simple_data,
        required_columns=DEFAULT_REQUIRED["volume-gainers-spurts"],
        dedupe_keys=("symbol",),
        referer_page_key="volume-gainers-spurts",
    ),
    "52-week-high-equity-market": DatasetConfig(
        id="52-week-high-equity-market",
        description="New 52-week high — equity market",
        api_paths=("/api/live-analysis-data-52weekhighstock",),
        query_builder=lambda: None,
        extractor=_records_simple_data,
        required_columns=DEFAULT_REQUIRED["52-week-high-equity-market"],
        dedupe_keys=("symbol", "series"),
        referer_page_key="52-week-high-equity-market",
    ),
}

# CLI aliases → canonical id
DATASET_ALIASES: dict[str, str] = {
    "all": "all",
    "top_gainers_losers": "top-gainers-losers",
    "top-gainers-losers": "top-gainers-losers",
    "upper_band_hitters": "upper-band-hitters",
    "upper-band-hitters": "upper-band-hitters",
    "volume_gainers_spurts": "volume-gainers-spurts",
    "volume-gainers-spurts": "volume-gainers-spurts",
    "52_week_high_equity_market": "52-week-high-equity-market",
    "52-week-high-equity-market": "52-week-high-equity-market",
    "52_week_high": "52-week-high-equity-market",
}


@dataclass
class AppSettings:
    base_url: str
    session_init_path: str
    timeout: tuple[float, float]
    max_retries: int
    backoff_factor_seconds: float
    inter_request_delay_seconds: float
    output_dir: Path
    sqlite_enabled: bool
    sqlite_path: Path
    notify_webhook_url: str | None
    history_retention_days: int


def _default_settings_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config" / "settings.yaml"


def load_settings(path: Path | None = None) -> AppSettings:
    p = path or _default_settings_path()
    raw: dict[str, Any] = {}
    if p.is_file():
        with p.open(encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    base_url = os.environ.get("NSE_BASE_URL", raw.get("base_url", "https://www.nseindia.com"))
    session_init = os.environ.get("NSE_SESSION_INIT_PATH", raw.get("session_init_path", ""))
    to = raw.get("timeout", [8, 25])
    timeout = (float(to[0]), float(to[1]))
    max_retries = int(os.environ.get("NSE_MAX_RETRIES", raw.get("max_retries", 4)))
    backoff = float(raw.get("backoff_factor_seconds", 1.5))
    delay = float(raw.get("inter_request_delay_seconds", 0.6))
    out = Path(os.environ.get("NSE_OUTPUT_DIR", raw.get("output_dir", "output")))
    sqlite_default = bool(raw.get("sqlite", {}).get("enabled", False))
    sqlite_enabled = os.environ.get("NSE_SQLITE", "").lower() in ("1", "true", "yes")
    if "NSE_SQLITE" not in os.environ:
        sqlite_enabled = sqlite_default
    sp = raw.get("sqlite", {}).get("path", "output/nse_snapshots.db")
    sqlite_path = Path(os.environ.get("NSE_SQLITE_PATH", sp))
    webhook = os.environ.get("NSE_NOTIFY_WEBHOOK", raw.get("notify_webhook_url") or "") or None
    if webhook == "":
        webhook = None
    retention = int(os.environ.get("NSE_HISTORY_RETENTION_DAYS", raw.get("history_retention_days", 0)))
    return AppSettings(
        base_url=base_url.rstrip("/"),
        session_init_path=session_init,
        timeout=timeout,
        max_retries=max_retries,
        backoff_factor_seconds=backoff,
        inter_request_delay_seconds=delay,
        output_dir=out,
        sqlite_enabled=sqlite_enabled,
        sqlite_path=sqlite_path,
        notify_webhook_url=webhook,
        history_retention_days=retention,
    )


def resolve_dataset_arg(name: str) -> str | None:
    """Return canonical dataset id, 'all', or None if unknown."""
    key = name.strip().lower().replace(" ", "-")
    if key in DATASET_ALIASES:
        return DATASET_ALIASES[key]
    if key in DATASETS:
        return key
    return None


def all_dataset_ids() -> list[str]:
    return list(DATASETS.keys())
