"""Webhook notifications."""

from __future__ import annotations

from unittest import mock

from nse_downloader.notifications import notify_failures


@mock.patch("nse_downloader.notifications.requests.post")
def test_notify_skips_when_empty(mock_post):
    notify_failures("https://example.com/hook", [])
    mock_post.assert_not_called()


@mock.patch("nse_downloader.notifications.requests.post")
def test_notify_posts_payload(mock_post):
    mock_post.return_value.ok = True
    failures = [{"dataset": "x", "error": "e", "rows": 0, "path": None}]
    notify_failures("https://example.com/hook", failures, timeout=(1.0, 2.0))
    mock_post.assert_called_once()
    call_kw = mock_post.call_args.kwargs
    assert "data" in call_kw
