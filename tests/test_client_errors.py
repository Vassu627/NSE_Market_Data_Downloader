"""Tests for HTTP client error handling (mocked)."""

from __future__ import annotations

from unittest import mock

import pytest
import requests

from nse_downloader.client import NSEClient, NSEClientError
from nse_downloader.config import AppSettings


def _settings() -> AppSettings:
    return AppSettings(
        base_url="https://www.nseindia.com",
        session_init_path="/market-data/top-gainers-losers",
        timeout=(1.0, 1.0),
        max_retries=2,
        backoff_factor_seconds=0.01,
        inter_request_delay_seconds=0.0,
        output_dir=mock.MagicMock(),
        sqlite_enabled=False,
        sqlite_path=mock.MagicMock(),
        notify_webhook_url=None,
        history_retention_days=0,
    )


@mock.patch("nse_downloader.client.NSEClient._request_with_retries")
def test_fetch_json_raises_on_non_json(mock_req):
    mock_resp = mock.MagicMock()
    mock_resp.ok = True
    mock_resp.json.side_effect = ValueError("bad")
    mock_req.return_value = mock_resp
    c = NSEClient(_settings())
    with pytest.raises(NSEClientError):
        c.fetch_json("/api/foo", "top-gainers-losers", None)


@mock.patch("nse_downloader.client.NSEClient._request_with_retries")
def test_fetch_json_http_error(mock_req):
    mock_resp = mock.MagicMock()
    mock_resp.ok = False
    mock_resp.status_code = 403
    mock_req.return_value = mock_resp
    c = NSEClient(_settings())
    with pytest.raises(NSEClientError):
        c.fetch_json("/api/foo", "top-gainers-losers", None)


@mock.patch("nse_downloader.client.requests.Session.request")
def test_request_retries_on_status(mock_request):
    ok = mock.MagicMock()
    ok.status_code = 200
    ok.json.return_value = {}
    fail = mock.MagicMock()
    fail.status_code = 503
    mock_request.side_effect = [fail, ok]
    c = NSEClient(_settings())
    r = c._request_with_retries("GET", "https://example.com", headers={}, params=None)
    assert r.status_code == 200


@mock.patch("nse_downloader.client.requests.Session.request")
def test_request_raises_after_retries(mock_request):
    mock_request.side_effect = requests.Timeout("timeout")
    c = NSEClient(_settings())
    with pytest.raises(NSEClientError):
        c._request_with_retries("GET", "https://example.com", headers={}, params=None)
