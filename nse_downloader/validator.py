"""Validate and normalize tabular market data before persistence."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger("nse_downloader.validator")


def records_to_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    return pd.DataFrame.from_records(records)


def validate_dataframe(
    df: pd.DataFrame,
    required_columns: tuple[str, ...],
    dedupe_keys: tuple[str, ...],
    dataset_id: str,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Ensure required columns exist, drop duplicate rows by dedupe_keys.
    Returns (possibly empty) DataFrame and list of warning messages.
    """
    warnings: list[str] = []
    if df.empty:
        warnings.append(f"{dataset_id}: empty DataFrame after parsing")
        return df, warnings

    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        warnings.append(f"{dataset_id}: missing required columns: {missing}")

    extra = [c for c in df.columns if c not in required_columns]
    if extra:
        logger.debug("%s: extra columns preserved: %s", dataset_id, extra)

    keys = [k for k in dedupe_keys if k in df.columns]
    if keys:
        before = len(df)
        df = df.drop_duplicates(subset=keys, keep="first")
        dropped = before - len(df)
        if dropped:
            msg = f"{dataset_id}: dropped {dropped} duplicate row(s) on keys {keys}"
            warnings.append(msg)
            logger.info(msg)

    return df, warnings
