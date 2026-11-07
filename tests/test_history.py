"""Tests for pruning old dated folders."""

from __future__ import annotations

from datetime import datetime

from nse_downloader.history import prune_old_date_folders
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def test_prune_removes_old_folders(tmp_path):
    (tmp_path / "2020-01-01").mkdir()
    (tmp_path / "2020-01-02").mkdir()
    (tmp_path / "not-a-date").mkdir()
    ref = datetime(2030, 6, 15, 12, 0, 0, tzinfo=IST)
    n = prune_old_date_folders(tmp_path, retention_days=100, now=ref)
    assert n == 2
    remaining = {p.name for p in tmp_path.iterdir() if p.is_dir()}
    assert remaining == {"not-a-date"}


def test_prune_zero_days_noop(tmp_path):
    (tmp_path / "2020-01-01").mkdir()
    assert prune_old_date_folders(tmp_path, retention_days=0) == 0
    assert (tmp_path / "2020-01-01").is_dir()
