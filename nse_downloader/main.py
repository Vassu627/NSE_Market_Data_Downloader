"""CLI entry point for NSE market data downloader."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from nse_downloader import __version__
from nse_downloader.app import run_all
from nse_downloader.config import load_settings, resolve_dataset_arg, all_dataset_ids
from nse_downloader.logger import setup_logging
from nse_downloader.notifications import notify_failures
from nse_downloader.scheduler import parse_ist_hh_mm, run_daily_ist, schedule_main_argv

logger = logging.getLogger("nse_downloader.main")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="nse-downloader",
        description="Download NSE live-analysis datasets to dated CSV files.",
    )
    p.add_argument(
        "--dataset",
        "-d",
        default="all",
        help=(
            "Dataset id or alias: all | top-gainers-losers | upper-band-hitters | "
            "volume-gainers-spurts | 52-week-high-equity-market (underscore "
            "aliases also accepted)"
        ),
    )
    p.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=None,
        help="Output directory (default: from config/settings.yaml or env NSE_OUTPUT_DIR)",
    )
    p.add_argument(
        "--refresh",
        action="store_true",
        help="Overwrite CSV if it already exists for today's date folder",
    )
    p.add_argument(
        "--sqlite",
        choices=("on", "off"),
        default=None,
        help="Mirror each CSV snapshot to SQLite (overrides config/settings.yaml)",
    )
    p.add_argument(
        "--sqlite-path",
        type=Path,
        default=None,
        help="SQLite database file path (default: from config or NSE_SQLITE_PATH)",
    )
    p.add_argument(
        "--notify-webhook",
        default=None,
        metavar="URL",
        help="POST JSON on any dataset failure (overrides notify_webhook_url in config)",
    )
    p.add_argument(
        "--history-retention-days",
        type=int,
        default=None,
        metavar="N",
        help="Delete output/<date>/ folders older than N days (0=off; default: config)",
    )
    p.add_argument(
        "--schedule-daily",
        metavar="HH:MM",
        default=None,
        help="Loop: run at this wall time in Asia/Kolkata every day (IST)",
    )
    p.add_argument(
        "--run-now",
        action="store_true",
        help="With --schedule-daily: run once immediately, then wait for the next scheduled time",
    )
    p.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to settings YAML (default: ./config/settings.yaml)",
    )
    p.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _run_once(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    if args.output_dir is not None:
        settings.output_dir = args.output_dir
    if args.sqlite == "on":
        settings.sqlite_enabled = True
    elif args.sqlite == "off":
        settings.sqlite_enabled = False
    if args.sqlite_path is not None:
        settings.sqlite_path = args.sqlite_path
    if args.notify_webhook is not None:
        settings.notify_webhook_url = args.notify_webhook or None
    if args.history_retention_days is not None:
        settings.history_retention_days = max(0, args.history_retention_days)

    resolved = resolve_dataset_arg(args.dataset)
    if resolved is None:
        logger.error("Unknown dataset: %s", args.dataset)
        return 2

    if resolved == "all":
        target_ids = all_dataset_ids()
    else:
        target_ids = [resolved]

    results = run_all(settings, refresh=args.refresh, dataset_filter=target_ids)
    failures = [r for r in results if not r.success]
    for r in results:
        status = "OK" if r.success else "FAIL"
        logger.info("SUMMARY | %s | %s | rows=%s | %s | %s", status, r.dataset_id, r.rows, r.path, r.error or "")

    if failures and settings.notify_webhook_url:
        payload = [
            {
                "dataset": r.dataset_id,
                "error": r.error,
                "rows": r.rows,
                "path": r.path,
            }
            for r in failures
        ]
        notify_failures(settings.notify_webhook_url, payload, timeout=settings.timeout)

    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    setup_logging(verbose=args.verbose)

    if args.schedule_daily:
        try:
            h, m = parse_ist_hh_mm(args.schedule_daily)
        except ValueError as e:
            logger.error("Invalid --schedule-daily: %s", e)
            return 2

        # Strip scheduler-only flags from nested argv to avoid infinite recursion
        filtered: list[str] = []
        skip_next = False
        for a in sys.argv[1:]:
            if skip_next:
                skip_next = False
                continue
            if a == "--schedule-daily":
                skip_next = True
                continue
            if a.startswith("--schedule-daily="):
                continue
            if a == "--run-now":
                continue
            filtered.append(a)

        def job_fixed() -> int:
            return schedule_main_argv(filtered)

        if args.run_now:
            logger.info("Running once now (--run-now); then following daily schedule")
            code = job_fixed()
            logger.info("Initial run exit code %s", code)

        run_daily_ist(h, m, job_fixed)
        return 0

    return _run_once(args)


if __name__ == "__main__":
    sys.exit(main())
