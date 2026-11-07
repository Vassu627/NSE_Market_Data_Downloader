"""Scheduler helpers."""

from __future__ import annotations

from datetime import datetime

from nse_downloader.scheduler import parse_ist_hh_mm, seconds_until_next_run
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def test_parse_time():
    assert parse_ist_hh_mm("09:15") == (9, 15)


def test_seconds_until_next_same_day():
    now = datetime(2030, 1, 1, 8, 0, 0, tzinfo=IST)
    s = seconds_until_next_run(9, 15, now=now)
    assert 4400 < s < 4600  # 75 minutes from 08:00 to 09:15 IST
