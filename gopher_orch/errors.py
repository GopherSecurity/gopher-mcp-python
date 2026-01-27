"""Exception classes for gopher-orch SDK."""

from typing import Optional


class AgentException(Exception):
    """Base exception class for agent operations."""

    def __init__(self, message: str, code: Optional[str] = None):
        super().__init__(message)
        self.code = code


class ConnectionException(AgentException):
    """Exception for connection-related errors."""

    pass


class ApiKeyException(AgentException):
    """Exception for API key related errors."""

    pass


class TimeoutException(AgentException):
    """Exception for timeout errors."""

    pass
