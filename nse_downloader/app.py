"""Orchestration: fetch → validate → save."""

from __future__ import annotations

import csv
import logging
import time
from dataclasses import dataclass

from nse_downloader.client import NSEClient, NSEClientError
from nse_downloader.config import DATASETS, DatasetConfig, AppSettings, all_dataset_ids
from nse_downloader.history import prune_old_date_folders
from nse_downloader.logger import utc_now_iso
from nse_downloader.sqlite_store import SnapshotMeta, save_snapshot
from nse_downloader.storage import csv_path_for_dataset, trading_date_str, write_csv_atomic
from nse_downloader.validator import records_to_dataframe, validate_dataframe

logger = logging.getLogger("nse_downloader.app")


def _csv_row_count(path: str) -> int:
    try:
        with open(path, encoding="utf-8", newline="") as f:
            r = csv.reader(f)
            next(r, None)
            return sum(1 for _ in r)
    except OSError:
        return 0


@dataclass
class RunResult:
    dataset_id: str
    success: bool
    rows: int
    path: str | None
    error: str | None = None


def _file_stem(dataset_id: str) -> str:
    return dataset_id.replace("-", "_")


def run_one(
    client: NSEClient,
    settings: AppSettings,
    ds: DatasetConfig,
    *,
    refresh: bool,
    date_str: str | None = None,
    skip_exist_check: bool = False,
    store_sqlite: bool = True,
) -> RunResult:
    date_str = date_str or trading_date_str()
    path = csv_path_for_dataset(settings.output_dir, _file_stem(ds.id), date_str)
    op = f"download {ds.id}"
    if not skip_exist_check and path.exists() and not refresh:
        n = _csv_row_count(str(path))
        logger.info(
            "SKIP %s | file already exists for %s: %s | rows=%s (use --refresh to re-fetch)",
            op,
            date_str,
            path,
            n,
        )
        return RunResult(ds.id, True, n, str(path), None)
    logger.info("BEGIN %s | %s", op, utc_now_iso())
    try:
        records = client.acquire_dataset(ds)
        df = records_to_dataframe(records)
        df, warns = validate_dataframe(
            df,
            ds.required_columns,
            ds.dedupe_keys,
            ds.id,
        )
        for w in warns:
            logger.warning(w)
        if df.empty:
            logger.error("%s: validation produced no rows; not writing CSV", ds.id)
            return RunResult(ds.id, False, 0, None, "empty after validation")
        written = write_csv_atomic(df, path, refresh=refresh)
        ok = written or path.exists()
        if ok and store_sqlite and settings.sqlite_enabled and path.exists():
            try:
                save_snapshot(
                    settings.sqlite_path,
                    SnapshotMeta(
                        dataset_id=ds.id,
                        trade_date=date_str,
                        row_count=len(df),
                        csv_path=str(path),
                    ),
                    df,
                )
            except Exception:
                logger.exception("SQLite save failed for %s (CSV still saved)", ds.id)
        logger.info(
            "END %s | success=%s | rows=%s | path=%s",
            op,
            ok,
            len(df),
            path,
        )
        return RunResult(ds.id, ok, len(df), str(path), None)
    except NSEClientError as e:
        logger.exception("FAILED %s: %s", op, e)
        return RunResult(ds.id, False, 0, None, str(e))
    except Exception as e:  # noqa: BLE001 — surface unexpected bugs with full trace
        logger.exception("FAILED %s (unexpected): %s", op, e)
        return RunResult(ds.id, False, 0, None, str(e))


def run_all(
    settings: AppSettings,
    *,
    refresh: bool,
    dataset_filter: list[str] | None = None,
) -> list[RunResult]:
    ids = dataset_filter or all_dataset_ids()
    results: list[RunResult] = []
    client: NSEClient | None = None
    date_str = trading_date_str()
    try:
        fetched_any = False
        if settings.history_retention_days > 0:
            prune_old_date_folders(settings.output_dir, settings.history_retention_days)

        for ds_id in ids:
            ds = DATASETS[ds_id]
            path = csv_path_for_dataset(settings.output_dir, _file_stem(ds.id), date_str)
            if path.exists() and not refresh:
                n = _csv_row_count(str(path))
                logger.info(
                    "SKIP download %s | file already exists for %s: %s | rows=%s",
                    ds.id,
                    date_str,
                    path,
                    n,
                )
                results.append(RunResult(ds.id, True, n, str(path), None))
                continue
            if client is None:
                client = NSEClient(settings)
            if fetched_any:
                time.sleep(settings.inter_request_delay_seconds)
            results.append(
                run_one(
                    client,
                    settings,
                    ds,
                    refresh=refresh,
                    date_str=date_str,
                    skip_exist_check=True,
                    store_sqlite=settings.sqlite_enabled,
                )
            )
            fetched_any = True
    finally:
        if client is not None:
            client.close()
    return results
