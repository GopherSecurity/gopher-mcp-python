"""Loopback callback server for local OAuth authorization-code flows."""

import asyncio
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import parse_qs, urlparse


@dataclass
class OAuthLoopbackCallbackResult:
    code: str
    state: str


class OAuthLoopbackCallbackServer:
    """Small local HTTP server that captures one OAuth callback."""

    def __init__(self, state: str, path: str = "/callback", timeout_ms: int = 120000):
        self._state = state
        self._path = path
        self._timeout_ms = timeout_ms
        self._future = None
        self._loop = None
        self._pending_result = None
        self._pending_error = None

        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                return

            def do_GET(self):
                owner._handle_callback(self)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    @property
    def redirect_uri(self) -> str:
        port = self._server.server_address[1]
        return f"http://127.0.0.1:{port}{self._path}"

    async def wait_for_callback(self) -> OAuthLoopbackCallbackResult:
        self._loop = asyncio.get_running_loop()
        if self._future is None:
            self._future = self._loop.create_future()
            if self._pending_result is not None:
                self._future.set_result(self._pending_result)
            elif self._pending_error is not None:
                self._future.set_exception(RuntimeError(self._pending_error))
        try:
            return await asyncio.wait_for(
                self._future,
                timeout=self._timeout_ms / 1000,
            )
        finally:
            await self.close()

    async def close(self) -> None:
        await asyncio.get_running_loop().run_in_executor(None, self._close_sync)

    def _close_sync(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        if self._thread.is_alive():
            self._thread.join(timeout=1)

    def _handle_callback(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urlparse(handler.path)
        if parsed.path != self._path:
            _respond(handler, 404, "OAuth callback path was not found.")
            return

        params = parse_qs(parsed.query)
        state = _first(params.get("state"))
        if state != self._state:
            self._settle_error("OAuth callback state mismatch.")
            _respond(handler, 400, "OAuth callback state mismatch.")
            return

        error = _first(params.get("error"))
        if error is not None:
            description = _first(params.get("error_description"))
            detail = f"{error}: {description}" if description else error
            message = f"OAuth callback returned error: {detail}"
            self._settle_error(message)
            _respond(handler, 400, message)
            return

        code = _first(params.get("code"))
        if not code:
            self._settle_error("OAuth callback is missing code.")
            _respond(handler, 400, "OAuth callback is missing code.")
            return

        self._settle_result(OAuthLoopbackCallbackResult(code=code, state=state))
        _respond(handler, 200, "OAuth authorization complete. You may close this tab.")

    def _settle_result(self, result: OAuthLoopbackCallbackResult) -> None:
        self._pending_result = result
        if self._loop is None or self._future is None or self._future.done():
            return
        self._loop.call_soon_threadsafe(self._future.set_result, result)

    def _settle_error(self, message: str) -> None:
        self._pending_error = message
        if self._loop is None or self._future is None or self._future.done():
            return
        self._loop.call_soon_threadsafe(self._future.set_exception, RuntimeError(message))


async def create_oauth_loopback_callback_server(
    state: str,
    path: str = "/callback",
    timeout_ms: int = 120000,
) -> OAuthLoopbackCallbackServer:
    """Create and start a loopback OAuth callback server."""
    return OAuthLoopbackCallbackServer(state=state, path=path, timeout_ms=timeout_ms)


def _respond(handler: BaseHTTPRequestHandler, status: int, body: str) -> None:
    data = (
        "<!doctype html><title>OAuth</title><p>"
        f"{_escape_html(body)}</p>"
    ).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _first(values) -> Optional[str]:
    return values[0] if values else None


def _escape_html(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
