"""Tests for CSV path naming and atomic write."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from nse_downloader.storage import csv_path_for_dataset, write_csv_atomic


def test_csv_path_contains_date(tmp_path: Path):
    p = csv_path_for_dataset(tmp_path, "top_gainers_losers", "2026-11-06")
    assert "2026-11-06" in str(p)
    assert p.name.startswith("nse_")


def test_skip_write_when_exists(tmp_path: Path):
    path = tmp_path / "2026-11-06" / "nse_test_2026-11-06.csv"
    path.parent.mkdir(parents=True)
    path.write_text("a\n1\n", encoding="utf-8")
    df = pd.DataFrame([{"a": 2}])
    assert write_csv_atomic(df, path, refresh=False) is False
