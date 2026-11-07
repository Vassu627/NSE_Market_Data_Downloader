"""Tests for validation and deduplication."""

from __future__ import annotations

import pandas as pd

from nse_downloader.validator import validate_dataframe


def test_validate_drops_duplicates():
    df = pd.DataFrame(
        [
            {"symbol": "A", "series": "EQ", "ltp": 1, "perChange": 1},
            {"symbol": "A", "series": "EQ", "ltp": 2, "perChange": 2},
        ]
    )
    out, warns = validate_dataframe(
        df,
        ("symbol", "series", "ltp", "perChange"),
        ("symbol", "series"),
        "test",
    )
    assert len(out) == 1
    assert any("duplicate" in w.lower() for w in warns)


def test_validate_missing_columns_warns():
    df = pd.DataFrame([{"symbol": "A"}])
    out, warns = validate_dataframe(
        df,
        ("symbol", "series", "ltp", "perChange"),
        ("symbol",),
        "test",
    )
    assert not out.empty
    assert any("missing" in w.lower() for w in warns)
