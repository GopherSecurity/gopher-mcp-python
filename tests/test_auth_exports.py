"""Import contract tests for public auth exports."""


def test_root_exports_auth_ffi_helpers():
    from gopher_mcp_python import (
        AutoRefreshResult,
        GopherAuthClient,
        GopherAuthConfig,
        GopherOAuthClient,
        GopherSessionManager,
        GopherValidationOptions,
        gopher_auth_auto_refresh,
        gopher_auth_build_protected_resource_metadata,
        gopher_auth_extract_bearer_token,
        gopher_auth_url_encode,
        gopher_auth_validate_all_scopes,
        gopher_create_validation_options,
        gopher_generate_www_authenticate_header_v2,
    )

    assert AutoRefreshResult is not None
    assert GopherAuthClient is not None
    assert GopherAuthConfig is not None
    assert GopherOAuthClient is not None
    assert GopherSessionManager is not None
    assert GopherValidationOptions is not None
    assert callable(gopher_auth_auto_refresh)
    assert callable(gopher_auth_build_protected_resource_metadata)
    assert callable(gopher_auth_extract_bearer_token)
    assert callable(gopher_auth_url_encode)
    assert callable(gopher_auth_validate_all_scopes)
    assert callable(gopher_create_validation_options)
    assert callable(gopher_generate_www_authenticate_header_v2)


def test_root_exports_reusable_auth_aliases():
    from gopher_mcp_python import (
        GopherAuth,
        GopherAuthBaseError,
        InsufficientScopesError,
        TokenExchangeError,
        TokenValidationError,
        has_all_scopes,
        has_any_scope,
        has_scope,
    )
    from gopher_mcp_python.auth import GopherAuthError

    assert GopherAuth is not None
    assert GopherAuthBaseError is GopherAuthError
    assert issubclass(InsufficientScopesError, GopherAuthBaseError)
    assert issubclass(TokenExchangeError, GopherAuthBaseError)
    assert issubclass(TokenValidationError, GopherAuthBaseError)
    assert callable(has_all_scopes)
    assert callable(has_any_scope)
    assert callable(has_scope)


def test_auth_package_exports_ffi_helpers():
    from gopher_mcp_python.auth import (
        AutoRefreshResult,
        GopherAuthClient,
        GopherAuthConfig,
        GopherOAuthClient,
        GopherSessionManager,
        GopherValidationOptions,
        gopher_auth_auto_refresh,
        gopher_auth_build_protected_resource_metadata,
        gopher_auth_extract_bearer_token,
        gopher_auth_url_encode,
        gopher_auth_validate_all_scopes,
        gopher_create_validation_options,
        gopher_generate_www_authenticate_header_v2,
    )

    assert AutoRefreshResult is not None
    assert GopherAuthClient is not None
    assert GopherAuthConfig is not None
    assert GopherOAuthClient is not None
    assert GopherSessionManager is not None
    assert GopherValidationOptions is not None
    assert callable(gopher_auth_auto_refresh)
    assert callable(gopher_auth_build_protected_resource_metadata)
    assert callable(gopher_auth_extract_bearer_token)
    assert callable(gopher_auth_url_encode)
    assert callable(gopher_auth_validate_all_scopes)
    assert callable(gopher_create_validation_options)
    assert callable(gopher_generate_www_authenticate_header_v2)
