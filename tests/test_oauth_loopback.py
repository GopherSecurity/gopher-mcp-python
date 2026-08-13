"""Tests for OAuth loopback callback server."""

import asyncio
import urllib.request

import pytest

from gopher_mcp_python.oauth_loopback import create_oauth_loopback_callback_server


def test_loopback_receives_code_and_state() -> None:
    asyncio.run(_test_loopback_receives_code_and_state())


async def _test_loopback_receives_code_and_state() -> None:
    server = await create_oauth_loopback_callback_server(
        state="state",
        timeout_ms=1000,
    )

    async def send_callback():
        urllib.request.urlopen(f"{server.redirect_uri}?code=abc&state=state").read()

    task = asyncio.create_task(server.wait_for_callback())
    await send_callback()
    result = await task

    assert result.code == "abc"
    assert result.state == "state"


def test_loopback_rejects_wrong_state() -> None:
    asyncio.run(_test_loopback_rejects_wrong_state())


async def _test_loopback_rejects_wrong_state() -> None:
    server = await create_oauth_loopback_callback_server(
        state="state",
        timeout_ms=1000,
    )
    task = asyncio.create_task(server.wait_for_callback())

    with pytest.raises(Exception):
        urllib.request.urlopen(f"{server.redirect_uri}?code=abc&state=wrong").read()
    with pytest.raises(RuntimeError, match="state mismatch"):
        await task
