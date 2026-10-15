"""Tests for scripts/keepalive.py."""

from __future__ import annotations

import httpx
import pytest
from unittest.mock import MagicMock, patch

from scripts.keepalive import ping_health_endpoint, main


def test_ping_health_endpoint_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {"status": "ok", "uptime_seconds": 120, "database": "connected"}

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        res = ping_health_endpoint("https://my-app.onrender.com")
        assert res is True
        mock_client.get.assert_called_once()
        called_url = mock_client.get.call_args[0][0]
        assert called_url == "https://my-app.onrender.com/health"


def test_ping_health_endpoint_already_has_health():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"content-type": "application/json"}
    mock_resp.json.return_value = {"status": "ok"}

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        res = ping_health_endpoint("https://my-app.onrender.com/health")
        assert res is True
        called_url = mock_client.get.call_args[0][0]
        assert called_url == "https://my-app.onrender.com/health"


def test_ping_health_endpoint_failure():
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"
    mock_resp.headers = {"content-type": "text/plain"}

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        res = ping_health_endpoint("https://my-app.onrender.com")
        assert res is False


def test_ping_health_endpoint_timeout():
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.side_effect = httpx.ConnectTimeout("Timed out")
        mock_client_cls.return_value = mock_client

        res = ping_health_endpoint("https://my-app.onrender.com")
        assert res is False


def test_main_cli_missing_url(monkeypatch):
    monkeypatch.setattr("sys.argv", ["keepalive.py"])
    monkeypatch.delenv("RENDER_APP_URL", raising=False)
    exit_code = main()
    assert exit_code == 1


def test_main_cli_success(monkeypatch):
    monkeypatch.setattr("sys.argv", ["keepalive.py", "--url", "https://demo.onrender.com"])
    with patch("scripts.keepalive.ping_health_endpoint", return_value=True):
        exit_code = main()
        assert exit_code == 0
