"""Atomic CSV storage with date-based filenames (IST calendar date)."""

from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

logger = logging.getLogger("nse_downloader.storage")

IST = ZoneInfo("Asia/Kolkata")


def trading_date_str(now: datetime | None = None) -> str:
    """YYYY-MM-DD in Asia/Kolkata (assignment: one run per calendar trading day)."""
    dt = now or datetime.now(IST)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    else:
        dt = dt.astimezone(IST)
    return dt.strftime("%Y-%m-%d")


def csv_path_for_dataset(output_dir: Path, dataset_file_stem: str, date_str: str) -> Path:
    safe = dataset_file_stem.replace("/", "-")
    return output_dir / date_str / f"nse_{safe}_{date_str}.csv"


def write_csv_atomic(df: pd.DataFrame, path: Path, refresh: bool) -> bool:
    """
    Write CSV atomically. If path exists and refresh is False, skip and return False.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not refresh:
        logger.info("Skip write; file already exists: %s (use --refresh to overwrite)", path)
        return False

    fd, tmp_name = tempfile.mkstemp(suffix=".csv", dir=path.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as tmp:
            df.to_csv(tmp, index=False)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    logger.info("Wrote %s rows -> %s", len(df), path)
    return True
