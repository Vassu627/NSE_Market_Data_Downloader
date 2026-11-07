"""Unit tests for JSON extractors in config."""

from __future__ import annotations

import json
from pathlib import Path

from nse_downloader.config import DATASETS, _records_simple_data, _records_upper_band


FIX = Path(__file__).parent / "fixtures"


def test_upper_band_extractor_dedupe_input_size():
    raw = json.loads((FIX / "upper_band.json").read_text(encoding="utf-8"))
    rows = _records_upper_band(raw)
    assert len(rows) == 2


def test_volume_and_52w_simple_data():
    v = json.loads((FIX / "volume_gainers.json").read_text(encoding="utf-8"))
    h = json.loads((FIX / "week52_high.json").read_text(encoding="utf-8"))
    assert len(_records_simple_data(v)) == 1
    assert len(_records_simple_data(h)) == 1


def test_all_datasets_defined():
    assert set(DATASETS.keys()) == {
        "top-gainers-losers",
        "upper-band-hitters",
        "volume-gainers-spurts",
        "52-week-high-equity-market",
    }
