"""Integration-style tests with mocked network."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import pandas as pd

from nse_downloader.app import run_all
from nse_downloader.config import DATASETS, AppSettings, load_settings


FIX = Path(__file__).parent / "fixtures"


def _payload(path: str) -> dict:
    return json.loads((FIX / path).read_text(encoding="utf-8"))


@mock.patch("nse_downloader.client.NSEClient.warm_session", lambda self, k: None)
@mock.patch("nse_downloader.client.NSEClient.fetch_json")
def test_run_all_success(mock_fetch, tmp_path: Path):
    def side_effect(api_path, referer_key, params):
        if "live-analysis-variations" in api_path:
            if params and params.get("index") == "gainers":
                return _payload("variation_gainers.json")
            return _payload("variation_losers.json")
        if "price-band-hitter" in api_path:
            return _payload("upper_band.json")
        if "volume-gainers" in api_path:
            return _payload("volume_gainers.json")
        if "52weekhigh" in api_path:
            return _payload("week52_high.json")
        raise AssertionError(api_path)

    mock_fetch.side_effect = side_effect

    settings = load_settings()
    settings.output_dir = tmp_path
    settings.inter_request_delay_seconds = 0.0
    results = run_all(settings, refresh=True, dataset_filter=None)
    assert len(results) == 4
    assert all(r.success for r in results)
    for r in results:
        assert r.path and Path(r.path).is_file()
        df = pd.read_csv(r.path)
        assert len(df) >= 1


@mock.patch("nse_downloader.app.trading_date_str", lambda: "2026-01-01")
def test_duplicate_skip_without_refresh(tmp_path: Path, monkeypatch):
    """Second run same day skips network when files exist."""
    monkeypatch.setenv("NSE_OUTPUT_DIR", str(tmp_path))
    settings = load_settings()
    settings.inter_request_delay_seconds = 0.0
    out = tmp_path / "2026-01-01" / "nse_volume_gainers_spurts_2026-01-01.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"symbol": "Z", "ltp": 1, "pChange": 0}]).to_csv(out, index=False)

    with mock.patch("nse_downloader.app.NSEClient") as m:
        run_all(settings, refresh=False, dataset_filter=["volume-gainers-spurts"])
    m.assert_not_called()
