"""Optional failure notifications (webhook)."""

from __future__ import annotations

import json
import logging
from typing import Any

import requests

logger = logging.getLogger("nse_downloader.notifications")


def notify_failures(
    webhook_url: str | None,
    failures: list[dict[str, Any]],
    timeout: tuple[float, float] = (5.0, 15.0),
) -> None:
    if not webhook_url or not failures:
        return
    payload = {
        "event": "nse_downloader_failures",
        "failed_count": len(failures),
        "failures": failures,
    }
    try:
        r = requests.post(
            webhook_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=timeout,
        )
        if not r.ok:
            logger.warning("Webhook POST %s -> HTTP %s", webhook_url, r.status_code)
        else:
            logger.info("Webhook notified for %s failed dataset(s)", len(failures))
    except requests.RequestException as e:
        logger.warning("Webhook failed: %s", e)
