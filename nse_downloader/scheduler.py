"""
Run the downloader once per day at a fixed IST wall-clock time.

Lightweight alternative to OS cron / Task Scheduler for bonus points.
"""

from __future__ import annotations

import logging
import sys
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger("nse_downloader.scheduler")

IST = ZoneInfo("Asia/Kolkata")


def parse_ist_hh_mm(s: str) -> tuple[int, int]:
    parts = s.strip().split(":")
    if len(parts) != 2:
        raise ValueError("Expected HH:MM")
    h, m = int(parts[0]), int(parts[1])
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("Invalid time")
    return h, m


def seconds_until_next_run(hour: int, minute: int, now: datetime | None = None) -> float:
    """Seconds until the next occurrence of hour:minute in IST (today or tomorrow)."""
    n = now or datetime.now(IST)
    if n.tzinfo is None:
        n = n.replace(tzinfo=IST)
    else:
        n = n.astimezone(IST)
    target = n.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= n:
        target += timedelta(days=1)
    return (target - n).total_seconds()


def run_daily_ist(
    hour: int,
    minute: int,
    job: Callable[[], int],
    *,
    stop_after_first: bool = False,
) -> None:
    """
    Sleep until next IST slot, run job(), repeat.

    job should return process exit code (0 ok).
    Set stop_after_first=True for tests.
    """
    logger.info("Scheduler: daily at %02d:%02d IST (Asia/Kolkata); Ctrl+C to stop", hour, minute)
    while True:
        wait = seconds_until_next_run(hour, minute)
        logger.info(
            "Next run in %.0f seconds (~%.1f hours)",
            wait,
            wait / 3600.0,
        )
        try:
            time.sleep(wait)
        except KeyboardInterrupt:
            logger.info("Scheduler stopped (KeyboardInterrupt).")
            return
        try:
            code = job()
            logger.info("Scheduled run finished with exit code %s", code)
        except Exception:
            logger.exception("Scheduled job raised")
        if stop_after_first:
            return


def schedule_main_argv(argv: list[str]) -> int:
    """Import main lazily to avoid cycles; run with given argv (no --schedule-daily)."""
    from nse_downloader.main import main

    return main(argv)
