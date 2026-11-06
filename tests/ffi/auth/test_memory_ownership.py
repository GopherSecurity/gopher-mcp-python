"""Auth allocation cleanup, including failure and invalid UTF-8 paths."""

import ctypes
from types import SimpleNamespace

import pytest

from gopher_mcp_python.ffi.auth import loader, oauth_client
from gopher_mcp_python.ffi.auth._memory import read_owned_string


class Allocations:
    def __init__(self):
        self.buffers = []
        self.freed = []

    def getter(self, content, status=0):
        def get(*args):
            buffer = ctypes.create_string_buffer(content)
            self.buffers.append(buffer)
            pointer = ctypes.cast(args[-1], ctypes.POINTER(ctypes.c_char_p))
            pointer[0] = ctypes.cast(buffer, ctypes.c_char_p)
            return status

        return get

    def free(self, pointer):
        self.freed.append(ctypes.cast(pointer, ctypes.c_void_p).value)

    def check(self):
        assert sorted(self.freed) == sorted(
            ctypes.addressof(buf) for buf in self.buffers
        )


@pytest.mark.parametrize(
    "content,status", [(b"hello", 0), (b"", 0), (b"partial", 1), (b"\xff", 0)]
)
def test_owned_strings_are_freed_on_success_error_and_decode_failure(content, status):
    allocations = Allocations()
    funcs = {
        "get": allocations.getter(content, status),
        "free_string": allocations.free,
    }
    if content == b"\xff":
        with pytest.raises(UnicodeDecodeError):
            read_owned_string(funcs, "get")
    else:
        result = read_owned_string(funcs, "get")
        assert result == (content.decode() if content and not status else None)
    allocations.check()


def test_metadata_parse_failure_releases_native_string(monkeypatch):
    allocations = Allocations()
    monkeypatch.setattr(
        loader,
        "get_auth_functions",
        lambda: {
            "metadata_build_protected_resource": allocations.getter(b"not json"),
            "free_string": allocations.free,
        },
    )
    with pytest.raises(ValueError):
        loader.gopher_auth_build_protected_resource_metadata("resource", "issuer")
    allocations.check()


def test_foreign_call_exception_releases_partially_written_string():
    allocations = Allocations()
    getter = allocations.getter(b"partial")

    def fail(output):
        getter(output)
        raise RuntimeError("foreign call failed")

    with pytest.raises(RuntimeError, match="foreign call failed"):
        read_owned_string({"get": fail, "free_string": allocations.free}, "get")
    allocations.check()


@pytest.mark.parametrize("invalid_utf8", [False, True])
@pytest.mark.parametrize("registration", [False, True])
def test_oauth_response_frees_copied_strings_and_response(
    monkeypatch, invalid_utf8, registration
):
    allocations = Allocations()
    responses = []

    def create(output, *args):
        ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p)).contents.value = 123
        return 0

    def refresh(handle, token, output):
        ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p)).contents.value = 456
        return 0

    funcs = {
        "oauth_client_create": create,
        "oauth_client_destroy": lambda handle: None,
        "oauth_refresh_token": refresh,
        "token_response_is_success": lambda response: True,
        "token_response_get_access_token": allocations.getter(
            b"\xff" if invalid_utf8 else b"access"
        ),
        "token_response_get_refresh_token": allocations.getter(b"refresh"),
        "token_response_get_token_type": allocations.getter(b"Bearer"),
        "token_response_destroy": lambda response: responses.append(response.value),
        "oauth_register_client": lambda handle, *args: refresh(handle, None, args[-1]),
        "registration_response_is_success": lambda response: True,
        "registration_response_get_client_id": allocations.getter(
            b"\xff" if invalid_utf8 else b"client"
        ),
        "registration_response_get_client_secret": allocations.getter(b"secret"),
        "registration_response_destroy": lambda response: responses.append(
            response.value
        ),
        "free_string": allocations.free,
    }
    monkeypatch.setattr(oauth_client, "get_auth_functions", lambda: funcs)
    monkeypatch.setattr(loader, "get_auth_functions", lambda: funcs)
    monkeypatch.setattr(oauth_client, "is_auth_available", lambda: True)
    with oauth_client.GopherOAuthClient("endpoint", "client") as client:
        operation = (
            (lambda: client.register_client("endpoint", "name", ["redirect"]))
            if registration
            else lambda: client.refresh_token("refresh")
        )
        if invalid_utf8:
            with pytest.raises(UnicodeDecodeError):
                operation()
        else:
            response = operation()
            if registration:
                assert response.client_id == "client"
                assert response.client_secret == "secret"
            else:
                assert response.access_token == "access"
                assert response.refresh_token == "refresh"
    assert responses == [456]
    allocations.check()


@pytest.mark.parametrize("registration", [False, True])
@pytest.mark.parametrize("getter_available", [False, True])
def test_oauth_getters_use_loader_bindings_and_preserve_optional_fallbacks(
    monkeypatch, registration, getter_available
):
    allocations = Allocations()
    responses = []

    def create(output, *args):
        ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p)).contents.value = 123
        return 0

    def response(*args):
        ctypes.cast(args[-1], ctypes.POINTER(ctypes.c_void_p)).contents.value = 456
        return 0

    exports = {
        "gopher_auth_init": lambda: 0,
        "gopher_auth_oauth_client_create": create,
        "gopher_auth_oauth_client_destroy": lambda handle: 0,
        "gopher_auth_oauth_refresh_token": response,
        "gopher_auth_token_response_is_success": lambda handle: True,
        "gopher_auth_token_response_get_access_token": allocations.getter(b"access"),
        "gopher_auth_token_response_destroy": lambda handle: responses.append(
            handle.value
        ),
        "gopher_auth_oauth_register_client": response,
        "gopher_auth_registration_response_is_success": lambda handle: False,
        "gopher_auth_registration_response_destroy": lambda handle: responses.append(
            handle.value
        ),
        "gopher_auth_free_string": lambda pointer: allocations.free(pointer),
    }
    if getter_available:
        exports.update(
            {
                "gopher_auth_token_response_get_token_type": allocations.getter(
                    b"DPoP"
                ),
                "gopher_auth_registration_response_get_error": allocations.getter(
                    b"invalid_redirect_uri"
                ),
            }
        )
    # Exercise the actual signature setup and export map, rather than supplying
    # a hand-built get_auth_functions() result that could hide missing entries.
    monkeypatch.setattr(loader, "_lib", SimpleNamespace(**exports))
    monkeypatch.setattr(loader, "_lib_available", True)
    monkeypatch.setattr(loader, "_functions_setup", False)
    monkeypatch.setattr(loader, "_auth_functions_available", False)
    funcs = loader.get_auth_functions()
    for key in ("token_response_get_token_type", "registration_response_get_error"):
        if getter_available:
            assert funcs[key].argtypes == [
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_char_p),
            ]
            assert funcs[key].restype is ctypes.c_int32
        else:
            assert funcs[key] is None

    with oauth_client.GopherOAuthClient("endpoint", "client") as client:
        if registration:
            result = client.register_client("endpoint", "name", ["redirect"])
            assert not result.success
            assert result.error == (
                "invalid_redirect_uri" if getter_available else None
            )
        else:
            result = client.refresh_token("refresh")
            assert result.success
            assert result.token_type == ("DPoP" if getter_available else "Bearer")
    assert responses == [456]
    allocations.check()
