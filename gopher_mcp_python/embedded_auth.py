"""Python host adapter for native multi-source MCP authorization."""

import asyncio
import concurrent.futures
import inspect
import json
import threading
import time
import uuid
import webbrowser
from urllib.parse import urlsplit
from .errors import AgentError, TimeoutError
from .ffi.embedded_auth import EmbeddedAuthBindings, UNAVAILABLE
from .runtime_options import GopherAgentTokenRecord, normalize_runtime_options


def _timeout(settings, name, default, maximum):
    value = settings.get(name, default)
    if type(value) is not int or not 100 <= value <= maximum:
        raise AgentError("Invalid assemble authorization timeout")
    return value


def _settings(options, inventory):
    oauth = options.oauth
    settings = dict(oauth.assemble or {}) if oauth else {}
    allowed = {
        "identity_namespace",
        "on_authorization_url",
        "on_progress",
        "cancel_event",
        "timeout_ms",
        "network_timeout_ms",
        "discovery_timeout_ms",
        "allow_loopback_http",
        "clients",
    }
    if settings.keys() - allowed:
        raise AgentError("Unknown assemble authorization option")
    identity = settings.get("identity_namespace")
    if identity is not None and (
        not isinstance(identity, str) or not identity.strip() or "\0" in identity
    ):
        raise AgentError("Invalid assemble identity namespace")
    if oauth and oauth.token_store and not identity:
        raise AgentError("Custom assemble token stores require identity_namespace")
    for key in ("on_authorization_url", "on_progress"):
        if settings.get(key) is not None and not callable(settings[key]):
            raise AgentError("Invalid authorization callback")
    cancel = settings.get("cancel_event")
    if cancel is not None and not callable(getattr(cancel, "is_set", None)):
        raise AgentError("cancel_event must support is_set()")
    if type(settings.get("allow_loopback_http", False)) is not bool:
        raise AgentError("Invalid allow_loopback_http")
    clients = settings.get("clients", {})
    if not isinstance(clients, dict):
        raise AgentError("Invalid assemble clients")
    clients = (
        {
            key: dict(value)
            for key, value in clients.items()
            if isinstance(key, str) and isinstance(value, dict)
        }
        if all(isinstance(k, str) and isinstance(v, dict) for k, v in clients.items())
        else None
    )
    if clients is None:
        raise AgentError("Invalid assemble clients")
    for client in clients.values():
        if client.keys() - {
            "client_id",
            "client_secret",
            "token_endpoint_auth_method",
            "scopes",
        }:
            raise AgentError("Invalid assemble client option")
        if (
            not isinstance(client.get("client_id"), str)
            or not client["client_id"]
            or "\0" in client["client_id"]
        ):
            raise AgentError("Invalid assemble client ID")
        if client.get(
            "token_endpoint_auth_method",
            "client_secret_post" if client.get("client_secret") else "none",
        ) not in ("none", "client_secret_post"):
            raise AgentError("Unsupported assemble client authentication")
        if "client_secret" in client and not isinstance(client["client_secret"], str):
            raise AgentError("Invalid assemble client secret")
        if "scopes" in client and (
            not isinstance(client["scopes"], list)
            or any(not isinstance(s, str) for s in client["scopes"])
        ):
            raise AgentError("Invalid assemble scopes")
    if oauth and oauth.scopes is not None:
        for source in json.loads(inventory)["data"]["servers"]:
            key = next(
                (source[k] for k in ("id", "serverId", "server_id") if k in source),
                source["name"],
            )
            clients[key] = dict({"scopes": oauth.scopes}, **clients.get(key, {}))
    native = dict(
        identity_namespace=identity or str(uuid.uuid4()),
        external_store=bool(oauth and oauth.token_store),
        authorization_timeout_ms=_timeout(settings, "timeout_ms", 600000, 1800000),
        network_timeout_ms=_timeout(settings, "network_timeout_ms", 10000, 30000),
        discovery_timeout_ms=_timeout(settings, "discovery_timeout_ms", 30000, 120000),
        allow_loopback_http=settings.get("allow_loopback_http", False),
        clients=clients,
    )
    return settings, native


def store_key(binding):
    fields = (
        "identity_namespace",
        "source",
        "issuer",
        "resource",
        "scopes",
        "client_identity",
    )
    if not isinstance(binding, dict) or any(
        not isinstance(binding.get(k), str) for k in fields
    ):
        raise AgentError("Invalid authorization store binding")
    return "gopher-embedded-v1:" + json.dumps(
        [binding[k] for k in fields], separators=(",", ":"), ensure_ascii=False
    )


async def service_store(store, request):
    key = store_key(request["binding"])
    if request["operation"] == "get":
        token = await store.get(key)
        grant = getattr(token, "embedded_grant", None) if token else None
        return {"found": True, "grant": grant} if grant else {"found": False}
    if request["operation"] == "put":
        grant = request["grant"]
        await store.set(
            key,
            GopherAgentTokenRecord(
                access_token=grant["access_token"],
                refresh_token=grant.get("refresh_token"),
                expires_at=grant["expires_at"] * 1000,
                embedded_grant=grant,
            ),
        )
        return {"ok": True}
    if request["operation"] == "erase" and callable(getattr(store, "delete", None)):
        await store.delete(key)
        return {"ok": True}
    raise AgentError("Unsupported authorization token-store request")


class EmbeddedAgentSession:
    """Own a persistent daemon host loop until native context disposal.

    The caller retains native agent ownership. Only this host thread accesses
    the context; close signals it rather than racing polls against release.
    """

    def __init__(
        self, library, inventory, provider, model, options, callback_loop=None
    ):
        self.library = library
        self.inventory = inventory
        self.provider, self.model = provider, model
        self.options = options
        self.settings, self.native_options = _settings(options, inventory)
        self.bindings = EmbeddedAuthBindings(library)
        caps = self.bindings.capabilities()
        if not caps:
            raise AgentError(UNAVAILABLE)
        if self.native_options["external_store"] and not caps.get("async_store"):
            raise AgentError(UNAVAILABLE)
        self.callback_loop = callback_loop
        self.ready = concurrent.futures.Future()
        self.stopped = threading.Event()
        self.stop = threading.Event()
        self.failure = None
        self.thread = threading.Thread(
            target=self._thread_main, name="gopher-mcp-authorization", daemon=True
        )
        self.thread.start()

    def _thread_main(self):
        try:
            asyncio.run(self._run())
        except BaseException:
            self.failure = self.failure or AgentError(
                "AUTH_FAILED: native authorization host failed"
            )
            if not self.ready.done():
                self.ready.set_exception(self.failure)
        finally:
            self.stopped.set()

    async def _invoke(self, function, *args):
        # Sync presentation callbacks may block. Do not strand native cleanup
        # or creation deadlines by joining application callback threads.
        future = concurrent.futures.Future()

        def invoke():
            try:
                result = function(*args)
                if inspect.isawaitable(result):
                    loop = self.callback_loop or self._loop

                    async def wait():
                        return await result

                    pending = asyncio.run_coroutine_threadsafe(wait(), loop)
                    future.add_done_callback(
                        lambda done: pending.cancel() if done.cancelled() else None
                    )

                    def complete(done):
                        if future.done():
                            return
                        try:
                            future.set_result(done.result())
                        except BaseException as exc:
                            future.set_exception(exc)

                    pending.add_done_callback(complete)
                elif not future.done():
                    future.set_result(result)
            except BaseException as exc:
                if not future.done():
                    future.set_exception(exc)

        threading.Thread(
            target=invoke, daemon=True, name="gopher-mcp-host-callback"
        ).start()
        return await asyncio.wrap_future(future)

    async def _present(self, event):
        url = event.get("url", "")
        parts = urlsplit(url)
        if (
            parts.scheme != "http"
            or parts.hostname not in ("localhost", "127.0.0.1", "::1")
            or parts.username
            or parts.password
        ):
            raise AgentError("Invalid native authorization page URL")
        presenter = self.settings.get("on_authorization_url")
        if presenter:
            await self._invoke(presenter, url, event.get("flow", "assemble"))
        elif self.options.oauth and self.options.oauth.open_browser is False:
            raise AgentError(
                "AUTH_PRESENTATION_REQUIRED: provide on_authorization_url when browser launch is disabled"
            )
        elif not await self._invoke(webbrowser.open, url):
            raise AgentError(
                "AUTH_PRESENTATION_REQUIRED: provide on_authorization_url for manual authorization"
            )

    async def _run(self):
        self._loop = asyncio.get_running_loop()
        context = self.bindings.create(
            self.inventory, self.native_options, normalize_runtime_options(self.options)
        )
        pending = {}
        presented = False
        authorized = False
        transferred = False
        agent_ready = False
        deadline = (
            time.monotonic()
            + sum(
                self.native_options[k]
                for k in (
                    "authorization_timeout_ms",
                    "network_timeout_ms",
                    "discovery_timeout_ms",
                )
            )
            / 1000
        )

        def schedule(key, coroutine):
            if key in pending:
                raise AgentError("Invalid duplicate native authorization request")
            pending[key] = asyncio.create_task(coroutine)

        async def store_request(request):
            async def invoke_store():
                try:
                    return await service_store(self.options.oauth.token_store, request)
                except Exception:
                    return {"ok": False}

            result = await self._invoke(invoke_store)
            context.complete_store(request["id"], result)

        try:
            context.start()
            while not self.stop.is_set():
                cancel = self.settings.get("cancel_event")
                if not transferred and cancel is not None and cancel.is_set():
                    raise AgentError("AUTH_CANCELLED: authorization cancelled")
                if not transferred and time.monotonic() > deadline:
                    raise TimeoutError("Assemble authorization timed out")
                for key, task in list(pending.items()):
                    if task.done():
                        del pending[key]
                        try:
                            task.result()
                        except AgentError as exc:
                            if str(exc).startswith("AUTH_PRESENTATION_REQUIRED:"):
                                raise
                            raise AgentError(
                                "AUTH_HOST_CALLBACK: authorization host callback failed"
                            ) from None
                        except BaseException:
                            raise AgentError(
                                "AUTH_HOST_CALLBACK: authorization host callback failed"
                            ) from None
                for _ in range(16):
                    request = context.store_request()
                    if request is None:
                        break
                    if not self.native_options["external_store"]:
                        raise AgentError("Unexpected native token-store request")
                    schedule("store:" + request["id"], store_request(request))
                for _ in range(64):
                    event = context.event()
                    if event is None:
                        break
                    kind = event.get("type")
                    if kind == "page" and not presented:
                        presented = True
                        schedule("page", self._present(event))
                    elif kind == "progress" and self.settings.get("on_progress"):
                        rows = event.get("sources", [])
                        if not isinstance(rows, list) or any(
                            not isinstance(row, dict)
                            or not isinstance(row.get("source"), str)
                            or not isinstance(row.get("state"), str)
                            for row in rows
                        ):
                            raise AgentError("Invalid native authorization progress")
                        safe = [
                            {"source": r["source"], "state": r["state"]} for r in rows
                        ]
                        # Notifications may overlap; each receives only public fields.
                        schedule(
                            "progress:" + str(uuid.uuid4()),
                            self._invoke(self.settings["on_progress"], safe),
                        )
                    elif kind == "authorized" and not authorized:
                        authorized = True
                        context.create_agent(self.provider, self.model)
                    elif kind == "agent_ready":
                        if not authorized:
                            raise AgentError("Invalid native authorization state")
                        agent_ready = True
                    elif kind in ("failed", "cancelled"):
                        raise AgentError(
                            "AUTH_CANCELLED: authorization cancelled"
                            if kind == "cancelled"
                            else "AUTH_FAILED: native authorization or agent creation failed"
                        )
                if agent_ready and not transferred and not pending:
                    handle = context.take_agent()
                    transferred = True
                    self.ready.set_result(handle)
                    if not self.native_options["external_store"]:
                        break
                await asyncio.sleep(0.01)
            if not transferred:
                raise AgentError("AUTH_CANCELLED: authorization cancelled")
        except BaseException as exc:
            context.cancel()
            self.failure = (
                exc
                if isinstance(exc, AgentError)
                else AgentError(
                    "AUTH_HOST_CALLBACK: authorization host integration failed"
                )
            )
            if not self.ready.done():
                self.ready.set_exception(self.failure)
        finally:
            for task in pending.values():
                task.cancel()
            if pending:
                await asyncio.gather(*pending.values(), return_exceptions=True)
            context.close()

    def check(self):
        if self.failure:
            raise self.failure

    def close(self):
        self.stop.set()
        if threading.current_thread() is not self.thread:
            self.thread.join()

    def wait_ready(self):
        return self.ready.result()
