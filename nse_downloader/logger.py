"""Logging setup for the NSE downloader."""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def setup_logging(log_dir: Path | None = None, verbose: bool = False) -> logging.Logger:
    """
    Configure root logger: console always; optional file under log_dir.
    """
    log_dir = log_dir or Path("logs")
    level = logging.DEBUG if verbose else logging.INFO

    fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    handlers: list[logging.Handler] = []

    # Prefer UTF-8 so log messages with symbols from NSE do not crash on Windows cp1252
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(fmt, datefmt))
    handlers.append(console)

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "nse_downloader.log"
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(fmt, datefmt))
        handlers.append(fh)
    except OSError:
        pass

    logging.basicConfig(level=logging.DEBUG, handlers=handlers, force=True)
    return logging.getLogger("nse_downloader")
