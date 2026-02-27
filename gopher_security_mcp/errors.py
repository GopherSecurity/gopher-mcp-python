"""
Custom error classes for the Gopher Security MCP SDK.

Provides typed exceptions for different error conditions:
- AgentError: Base class for all agent-related errors
- ApiKeyError: Invalid or missing API key
- ConnectionError: Network or connection failures
- TimeoutError: Operation timed out
"""


class AgentError(Exception):
    """Base exception for agent-related errors."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ApiKeyError(AgentError):
    """Exception raised when API key is invalid or missing."""

    def __init__(self, message: str = "Invalid or missing API key") -> None:
        super().__init__(message)


class ConnectionError(AgentError):
    """Exception raised when connection to server fails."""

    def __init__(self, message: str = "Connection failed") -> None:
        super().__init__(message)


class TimeoutError(AgentError):
    """Exception raised when operation times out."""

    def __init__(self, message: str = "Operation timed out") -> None:
        super().__init__(message)
