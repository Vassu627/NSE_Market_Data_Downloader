"""Prune old dated CSV folders under the output directory."""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

logger = logging.getLogger("nse_downloader.history")

IST = ZoneInfo("Asia/Kolkata")


def prune_old_date_folders(output_dir: Path, retention_days: int, *, now: datetime | None = None) -> int:
    """
    Remove subdirectories named YYYY-MM-DD older than retention_days (IST calendar).
    Returns number of directories removed.
    """
    if retention_days <= 0:
        return 0
    output_dir = Path(output_dir)
    if not output_dir.is_dir():
        return 0
    dt = now or datetime.now(IST)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    else:
        dt = dt.astimezone(IST)
    cutoff = dt.date() - timedelta(days=retention_days)
    removed = 0
    for child in output_dir.iterdir():
        if not child.is_dir():
            continue
        name = child.name
        try:
            day = datetime.strptime(name, "%Y-%m-%d").date()
        except ValueError:
            continue
        if day < cutoff:
            try:
                shutil.rmtree(child)
                removed += 1
                logger.info("Pruned old output folder: %s", child)
            except OSError as e:
                logger.warning("Could not prune %s: %s", child, e)
    if removed:
        logger.info("Pruned %s dated folder(s) older than %s days", removed, retention_days)
    return removed
