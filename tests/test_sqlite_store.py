"""SQLite snapshot storage."""

from __future__ import annotations

import pandas as pd

from nse_downloader.sqlite_store import SnapshotMeta, dataframe_from_snapshot, save_snapshot, connect, init_schema


def test_roundtrip_snapshot(tmp_path):
    db = tmp_path / "t.db"
    df = pd.DataFrame([{"symbol": "X", "ltp": 1.5, "perChange": 2.0}])
    save_snapshot(
        db,
        SnapshotMeta(
            dataset_id="volume-gainers-spurts",
            trade_date="2030-01-01",
            row_count=len(df),
            csv_path="/tmp/x.csv",
        ),
        df,
    )
    with connect(db) as conn:
        init_schema(conn)
        back = dataframe_from_snapshot(conn, "volume-gainers-spurts", "2030-01-01")
    assert len(back) == 1
    assert back.iloc[0]["symbol"] == "X"


def test_replaces_same_day(tmp_path):
    db = tmp_path / "t.db"
    d1 = pd.DataFrame([{"symbol": "A"}])
    d2 = pd.DataFrame([{"symbol": "B"}, {"symbol": "C"}])
    def meta(rows: int) -> SnapshotMeta:
        return SnapshotMeta(
            dataset_id="upper-band-hitters",
            trade_date="2030-02-01",
            row_count=rows,
            csv_path="/x.csv",
        )

    save_snapshot(db, meta(len(d1)), d1)
    save_snapshot(db, meta(len(d2)), d2)
    with connect(db) as conn:
        init_schema(conn)
        back = dataframe_from_snapshot(conn, "upper-band-hitters", "2030-02-01")
    assert len(back) == 2
