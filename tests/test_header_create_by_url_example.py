"""Tests for the header create_by_url example runtime options."""

import importlib.util
from pathlib import Path


def _load_example_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "examples"
        / "header"
        / "create_by_url.py"
    )
    spec = importlib.util.spec_from_file_location("header_create_by_url_example", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_token_mode_omits_empty_access_token(monkeypatch) -> None:
    module = _load_example_module()
    monkeypatch.delenv("GOPHER_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("GOPHER_HEADER_MODE", raising=False)

    options = module.runtime_options_from_env()

    assert "access_token" not in options
    assert options["headers"]["x-gopher-example"] == "header-create-by-url"
    assert "Authorization" not in options["headers"]


def test_token_mode_includes_non_empty_access_token(monkeypatch) -> None:
    module = _load_example_module()
    monkeypatch.setenv("GOPHER_ACCESS_TOKEN", "abc123")
    monkeypatch.delenv("GOPHER_HEADER_MODE", raising=False)

    options = module.runtime_options_from_env()

    assert options["access_token"] == "abc123"
    assert options["headers"]["x-gopher-example"] == "header-create-by-url"
    assert "Authorization" not in options["headers"]


def test_headers_mode_omits_empty_authorization_header(monkeypatch) -> None:
    module = _load_example_module()
    monkeypatch.setenv("GOPHER_HEADER_MODE", "headers")
    monkeypatch.delenv("GOPHER_ACCESS_TOKEN", raising=False)

    options = module.runtime_options_from_env()

    assert "access_token" not in options
    assert "Authorization" not in options["headers"]
