"""Tests for OAuth browser opener helpers."""

import pytest

from gopher_mcp_python.oauth_browser import _command_for_platform, open_authorization_url


def test_selects_command_by_platform() -> None:
    assert _command_for_platform("darwin") == "open"
    assert _command_for_platform("win32") == "cmd"
    assert _command_for_platform("linux") == "xdg-open"


def test_opens_url_with_injected_opener(monkeypatch) -> None:
    opened_urls = []
    monkeypatch.setattr("sys.platform", "darwin")

    result = open_authorization_url(
        "https://auth.example.com/authorize",
        opener=lambda url: opened_urls.append(url) or True,
    )

    assert result == {
        "opened": True,
        "url": "https://auth.example.com/authorize",
        "command": "open",
    }
    assert opened_urls == ["https://auth.example.com/authorize"]


def test_open_browser_false_does_not_open() -> None:
    def opener(url):
        raise AssertionError("opener should not run")

    assert open_authorization_url(
        "https://auth.example.com/authorize",
        open_browser=False,
        opener=opener,
    ) == {
        "opened": False,
        "url": "https://auth.example.com/authorize",
    }


def test_failed_open_includes_authorization_url() -> None:
    def opener(url):
        raise OSError("missing command")

    with pytest.raises(
        RuntimeError,
        match="Failed to open OAuth authorization URL https://auth.example.com/authorize",
    ):
        open_authorization_url("https://auth.example.com/authorize", opener=opener)
