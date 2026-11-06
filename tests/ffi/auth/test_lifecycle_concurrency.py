"""Deterministic auth lifetime tests without network or real native handles."""

import ctypes
import gc
import threading
import weakref
from concurrent.futures import ThreadPoolExecutor

import pytest

from gopher_mcp_python.ffi.auth import auth_client, config_loader, loader
from gopher_mcp_python.ffi.auth import oauth_client, session_manager, validation_options
from gopher_mcp_python.ffi.auth.auto_refresh import gopher_auth_auto_refresh
from gopher_mcp_python.ffi.auth.loader import GopherAuthValidationResult


@pytest.fixture
def functions(monkeypatch):
    next_handle = iter(range(1000, 2000))
    destroyed = []

    def create(output, *args):
        ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p)).contents.value = next(
            next_handle
        )
        return 0

    funcs = {
        name: create
        for name in (
            "client_create",
            "options_create",
            "oauth_client_create",
            "session_manager_create",
        )
    }
    for name in (
        "client_destroy",
        "options_destroy",
        "oauth_client_destroy",
        "session_manager_destroy",
        "config_destroy",
    ):
        funcs[name] = lambda handle, name=name: destroyed.append((name, handle.value))
    for module in (
        auth_client,
        oauth_client,
        session_manager,
        validation_options,
        config_loader,
    ):
        monkeypatch.setattr(module, "get_auth_functions", lambda: funcs)
        monkeypatch.setattr(module, "load_library", lambda: True)
        monkeypatch.setattr(module, "is_auth_available", lambda: True)
    monkeypatch.setattr(loader, "get_auth_functions", lambda: funcs)
    monkeypatch.setattr(auth_client, "_auth_initialized", True)
    return funcs, destroyed


def make_owner(kind):
    if kind == "client":
        return auth_client.GopherAuthClient("http://unused/jwks", "issuer")
    if kind == "options":
        return validation_options.GopherValidationOptions()
    if kind == "oauth":
        return oauth_client.GopherOAuthClient("http://unused/token", "client")
    if kind == "session":
        return session_manager.GopherSessionManager()
    return config_loader.GopherAuthConfig(ctypes.c_void_p(999))


@pytest.mark.parametrize(
    "kind,function,method,args",
    [
        ("client", "client_set_option", "set_option", ("key", "value")),
        ("options", "options_set_scopes", "set_scopes", (["read"],)),
        ("oauth", "oauth_refresh_token", "refresh_token", ("refresh",)),
        ("session", "session_has_valid_token", "has_valid_token", ("session",)),
        ("config", "config_get_int", "get_int", ("port",)),
    ],
)
def test_destroy_waits_for_native_operation(functions, kind, function, method, args):
    funcs, destroyed = functions
    entered, finish, destroying = (threading.Event() for _ in range(3))

    def native(*args):
        entered.set()
        assert finish.wait(5)
        assert destroyed == []
        return 0

    funcs[function] = native
    owner = make_owner(kind)

    def destroy():
        destroying.set()
        owner.destroy()

    with ThreadPoolExecutor(max_workers=8) as pool:
        operation = pool.submit(getattr(owner, method), *args)
        try:
            assert entered.wait(5)
            cleanup = pool.submit(destroy)
            assert destroying.wait(5)
            assert not cleanup.done()
        finally:
            finish.set()
        operation.result(5)
        cleanup.result(5)
        list(pool.map(lambda _: owner.destroy(), range(12)))
    assert len(destroyed) == 1
    assert owner.is_destroyed()
    with pytest.raises(RuntimeError, match="destroyed"):
        getattr(owner, method)(*args)


def test_validation_borrows_client_and_options_together(functions):
    funcs, destroyed = functions
    entered, finish = threading.Event(), threading.Event()

    def validate(client, token, options, output):
        entered.set()
        assert finish.wait(5)
        assert destroyed == []
        ctypes.cast(
            output, ctypes.POINTER(GopherAuthValidationResult)
        ).contents.valid = True
        return 0

    funcs["validate_token"] = validate
    client, options = make_owner("client"), make_owner("options")
    with ThreadPoolExecutor(max_workers=3) as pool:
        result = pool.submit(client.validate_token, "token", options=options)
        try:
            assert entered.wait(5)
            cleanups = [pool.submit(owner.destroy) for owner in (client, options)]
            assert destroyed == []
        finally:
            finish.set()
        assert result.result(5).valid
        for cleanup in cleanups:
            cleanup.result(5)
    assert len(destroyed) == 2


def test_auto_refresh_borrows_all_three_objects(functions, monkeypatch):
    import importlib

    module = importlib.import_module("gopher_mcp_python.ffi.auth.auto_refresh")
    funcs, destroyed = functions
    entered, finish = threading.Event(), threading.Event()

    def refresh(*args):
        entered.set()
        assert finish.wait(5)
        assert destroyed == []
        return 0

    funcs["auto_refresh"] = refresh
    monkeypatch.setattr(module, "get_auth_functions", lambda: funcs)
    owners = [make_owner(kind) for kind in ("client", "oauth", "session")]
    with ThreadPoolExecutor(max_workers=4) as pool:
        result = pool.submit(gopher_auth_auto_refresh, *owners, "session")
        try:
            assert entered.wait(5)
            cleanups = [pool.submit(owner.destroy) for owner in owners]
            assert destroyed == []
        finally:
            finish.set()
        result.result(5)
        for cleanup in cleanups:
            cleanup.result(5)
    assert len(destroyed) == 3


def test_reentrant_destroy_defers_until_borrow_ends(functions):
    funcs, destroyed = functions
    owner = make_owner("client")
    with owner.borrow_handle() as handle:
        owner.destroy()
        assert owner.is_destroyed()
        assert handle.value == 1000
        assert not destroyed
        with pytest.raises(RuntimeError, match="destroyed"):
            owner.get_handle()
    assert len(destroyed) == 1
    owner.destroy()
    assert len(destroyed) == 1


def test_auth_shutdown_preserves_other_live_objects(functions):
    funcs, destroyed = functions
    shutdowns = []
    funcs["auth_shutdown"] = lambda: shutdowns.append(1) or 0
    owner = make_owner("client")
    try:
        assert auth_client.gopher_shutdown_auth_library() is False
        assert not shutdowns
    finally:
        owner.destroy()
    assert auth_client.gopher_shutdown_auth_library() is True
    assert shutdowns == [1]


def test_concurrent_auth_init_calls_native_once(functions, monkeypatch):
    funcs, destroyed = functions
    calls = []
    funcs["auth_init"] = lambda: calls.append(1) or 0
    monkeypatch.setattr(auth_client, "_auth_initialized", False)
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert all(
            pool.map(lambda _: auth_client.gopher_init_auth_library(), range(32))
        )
    assert calls == [1]


def test_concurrent_loader_publishes_one_library(monkeypatch):
    entered, finish = threading.Event(), threading.Event()
    loads = []

    def load(path):
        loads.append(path)
        entered.set()
        assert finish.wait(5)
        return object()

    monkeypatch.setattr(loader, "_lib", None)
    monkeypatch.setattr(loader, "_lib_available", False)
    monkeypatch.setattr(loader, "_get_search_paths", lambda: [])
    monkeypatch.setattr(loader.ctypes, "CDLL", load)
    monkeypatch.delenv("GOPHER_MCP_PYTHON_LIBRARY_PATH", raising=False)
    monkeypatch.delenv("GOPHER_ORCH_LIBRARY_PATH", raising=False)
    monkeypatch.delenv("GOPHER_AUTH_LIBRARY_PATH", raising=False)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(loader.load_library) for _ in range(8)]
        try:
            assert entered.wait(5)
            assert loader._lib is None
        finally:
            finish.set()
        assert all(future.result(5) for future in futures)
    assert len(loads) == 1


@pytest.mark.parametrize("kind", ["client", "options", "oauth", "session", "config"])
def test_forgotten_auth_objects_release_handles(functions, kind):
    funcs, destroyed = functions
    owner = make_owner(kind)
    reference = weakref.ref(owner)
    del owner
    gc.collect()
    assert reference() is None
    assert len(destroyed) == 1


def test_high_level_shutdown_waits_for_compound_validation(functions, monkeypatch):
    from gopher_mcp_python.auth.gopher_auth import GopherAuth
    from gopher_mcp_python.ffi.auth.types import TokenPayload

    funcs, destroyed = functions
    entered, finish, shutting_down = (threading.Event() for _ in range(3))

    def validate(handle, token, options, output):
        entered.set()
        assert finish.wait(5)
        assert not destroyed
        ctypes.cast(
            output, ctypes.POINTER(GopherAuthValidationResult)
        ).contents.valid = True
        return 0

    funcs["validate_token"] = validate
    client = make_owner("client")

    def extract_payload(token):
        # Shutdown may be waiting, but an admitted compound validation can
        # finish its nested read operations before the client is destroyed.
        assert client.get_handle()
        assert not destroyed
        return TokenPayload(subject="subject", scopes="read")

    monkeypatch.setattr(client, "extract_payload", extract_payload)

    auth = GopherAuth(auth_disabled=True)
    auth.initialize()
    auth._auth_client = client

    def shutdown():
        shutting_down.set()
        auth.shutdown()

    with ThreadPoolExecutor(max_workers=2) as pool:
        validation = pool.submit(auth.validate_token, "token")
        try:
            assert entered.wait(5)
            cleanup = pool.submit(shutdown)
            assert shutting_down.wait(5)
            assert not cleanup.done()
        finally:
            finish.set()
        validation.result(5)
        cleanup.result(5)
    assert len(destroyed) == 1


def test_independent_auth_objects_can_execute_concurrently(functions):
    funcs, destroyed = functions
    entered, finish = threading.Event(), threading.Event()
    first, second = make_owner("session"), make_owner("session")

    def native(handle, *args):
        if handle.value == first._handle.value:
            entered.set()
            assert finish.wait(5)
        return 0

    funcs["session_has_valid_token"] = native
    with ThreadPoolExecutor(max_workers=2) as pool:
        active = pool.submit(first.has_valid_token, "session")
        try:
            assert entered.wait(5)
            pool.submit(second.has_valid_token, "session").result(5)
        finally:
            finish.set()
            first.destroy()
            second.destroy()
        active.result(5)


def test_same_client_and_options_validate_concurrently_until_last_call_exits(functions):
    funcs, destroyed = functions
    entered = threading.Barrier(3)
    finish = {token: threading.Event() for token in (b"first", b"second")}

    def validate(handle, token, options, output):
        entered.wait(5)
        assert finish[token].wait(5)
        assert not destroyed
        ctypes.cast(
            output, ctypes.POINTER(GopherAuthValidationResult)
        ).contents.valid = True
        return 0

    funcs["validate_token"] = validate
    client, options = make_owner("client"), make_owner("options")
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            first = pool.submit(client.validate_token, "first", options)
            second = pool.submit(client.validate_token, "second", options)
            try:
                # Both calls must reach native execution before either returns.
                entered.wait(5)
                cleanups = [pool.submit(owner.destroy) for owner in (client, options)]
                for owner in (client, options):
                    with owner._operation_condition:
                        assert owner._operation_condition.wait_for(
                            lambda: owner._closing, timeout=5
                        )
                with pytest.raises(RuntimeError, match="destroyed"):
                    client.validate_token("late", options)
                finish[b"first"].set()
                assert first.result(5).valid
                assert not destroyed
                assert all(not cleanup.done() for cleanup in cleanups)
            finally:
                for event in finish.values():
                    event.set()
            assert second.result(5).valid
            for cleanup in cleanups:
                cleanup.result(5)
    finally:
        client.destroy()
        options.destroy()
    assert len(destroyed) == 2


def test_high_level_validations_overlap_on_one_auth_instance(functions, monkeypatch):
    from gopher_mcp_python.auth.gopher_auth import GopherAuth
    from gopher_mcp_python.ffi.auth.types import TokenPayload

    funcs, destroyed = functions
    entered, finish = threading.Barrier(3), threading.Event()

    def validate(handle, token, options, output):
        entered.wait(5)
        assert finish.wait(5)
        ctypes.cast(
            output, ctypes.POINTER(GopherAuthValidationResult)
        ).contents.valid = True
        return 0

    funcs["validate_token"] = validate
    client = make_owner("client")
    monkeypatch.setattr(
        client,
        "extract_payload",
        lambda token: TokenPayload(subject=token, scopes="read"),
    )
    auth = GopherAuth(auth_disabled=True)
    auth.initialize()
    auth._auth_client = client
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [
                pool.submit(auth.validate_token, token, ["read"])
                for token in ("first", "second")
            ]
            try:
                entered.wait(5)
            finally:
                finish.set()
            assert {result.result(5).subject for result in results} == {
                "first",
                "second",
            }
    finally:
        auth.shutdown()
    assert len(destroyed) == 1


@pytest.mark.parametrize(
    "kind,function,method,args",
    [
        ("client", "client_set_option", "set_option", ("cache_duration", "10")),
        ("options", "options_set_scopes", "set_scopes", (["read"],)),
    ],
)
def test_mutation_waits_for_shared_validation(functions, kind, function, method, args):
    funcs, destroyed = functions
    entered, finish, changing, changed = (threading.Event() for _ in range(4))

    def validate(handle, token, options, output):
        entered.set()
        assert finish.wait(5)
        assert not changed.is_set()
        return 0

    funcs["validate_token"] = validate
    funcs[function] = lambda *args: changed.set() or 0
    client, options = make_owner("client"), make_owner("options")
    owner = client if kind == "client" else options

    def mutate():
        changing.set()
        return getattr(owner, method)(*args)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            validation = pool.submit(client.validate_token, "token", options)
            try:
                assert entered.wait(5)
                mutation = pool.submit(mutate)
                assert changing.wait(5)
                assert not changed.is_set()
                assert not mutation.done()
            finally:
                finish.set()
            validation.result(5)
            mutation.result(5)
        assert changed.is_set()
    finally:
        client.destroy()
        options.destroy()


def test_one_oauth_client_still_serializes_curl_operations(functions):
    funcs, destroyed = functions
    entered, finish, second_started = (threading.Event() for _ in range(3))
    calls = []

    def refresh(handle, token, output):
        calls.append(token)
        if token == b"first":
            entered.set()
            assert finish.wait(5)
        return 1

    funcs["oauth_refresh_token"] = refresh
    client = make_owner("oauth")

    def second():
        second_started.set()
        return client.refresh_token("second")

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(client.refresh_token, "first")
            try:
                assert entered.wait(5)
                following = pool.submit(second)
                assert second_started.wait(5)
                assert calls == [b"first"]
                assert not following.done()
            finally:
                finish.set()
            first.result(5)
            following.result(5)
        assert calls == [b"first", b"second"]
    finally:
        client.destroy()
