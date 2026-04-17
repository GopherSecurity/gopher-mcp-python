"""Custom error classes for the auth module."""


class GopherAuthError(Exception):
    """Base error for auth operations."""
    pass


class TokenValidationError(GopherAuthError):
    """Token validation failed."""
    def __init__(self, message: str, error_code: int = 0):
        super().__init__(message)
        self.error_code = error_code


class InsufficientScopesError(GopherAuthError):
    """Required scopes not present."""
    def __init__(self, required_scopes: list, actual_scopes: list, message: str = ""):
        msg = message or (
            f"Insufficient scopes: required {required_scopes}, actual {actual_scopes}"
        )
        super().__init__(msg)
        self.required_scopes = required_scopes
        self.actual_scopes = actual_scopes


class JwksError(GopherAuthError):
    """JWKS fetch or parsing failed."""
    pass


class ConfigurationError(GopherAuthError):
    """Invalid configuration."""
    pass


class TokenExchangeError(GopherAuthError):
    """Token exchange failed."""
    def __init__(self, message: str, error_code: str = "", error_description: str = ""):
        super().__init__(message)
        self.error_code = error_code
        self.error_description = error_description
