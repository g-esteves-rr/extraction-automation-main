import os
import json
import pytest
from unittest.mock import patch, MagicMock

from utils.notifications import (
    _build_payload,
    send_notification,
)


@pytest.fixture
def base_env(monkeypatch):
    monkeypatch.setenv("NOTIFY_URL", "http://test-notify.local")
    monkeypatch.setenv("SERVER_NAME", "TEST_SERVER")


def test_build_payload_basic(base_env):
    payload = _build_payload(
        report="duk008",
        status="SUCCESS",
        message="All good",
    )

    assert payload["report"] == "DUK008"
    assert payload["status"] == "SUCCESS"
    assert payload["source_server"] == "TEST_SERVER"
    assert "`All good`" in payload["extra"]


def test_build_payload_empty_message(base_env):
    payload = _build_payload(
        report="ic01",
        status="FAIL",
        message="",
    )

    assert payload["extra"] == ""


@patch("utils.notifications.requests.post")
def test_send_notification_success(mock_post, base_env):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    send_notification("duk008", "SUCCESS", "ok")

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    payload = json.loads(kwargs["data"])

    assert payload["report"] == "DUK008"
    assert payload["status"] == "SUCCESS"


@patch("utils.notifications.requests.post")
def test_send_notification_http_error(mock_post, base_env):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Server error"
    mock_post.return_value = mock_response

    # Must not raise
    send_notification("duk008", "FAIL", "error")


@patch("utils.notifications.requests.post", side_effect=Exception("boom"))
def test_send_notification_exception_is_ignored(mock_post, base_env):
    # Must not raise
    send_notification("duk008", "FAIL", "exception case")


def test_send_notification_missing_env(monkeypatch):
    monkeypatch.delenv("NOTIFY_URL", raising=False)
    monkeypatch.delenv("SERVER_NAME", raising=False)

    # Must not raise
    send_notification("duk008", "SUCCESS", "no env")
