"""
Result classes for the Gopher Orch SDK.

Provides structured result objects with status, response, and metadata.
"""

from enum import Enum
from typing import Optional


class AgentResultStatus(Enum):
    """Status of an agent operation."""

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


class AgentResult:
    """
    Result of an agent operation.

    Contains the response, status, and optional metadata.
    """

    def __init__(
        self,
        response: str,
        status: AgentResultStatus,
        iteration_count: int = 0,
        tokens_used: int = 0,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Initialize an AgentResult.

        Args:
            response: The agent's response text
            status: The result status
            iteration_count: Number of iterations performed
            tokens_used: Number of tokens consumed
            error_message: Error message if status is ERROR or TIMEOUT
        """
        self._response = response
        self._status = status
        self._iteration_count = iteration_count
        self._tokens_used = tokens_used
        self._error_message = error_message

    @property
    def response(self) -> str:
        """Get the response text."""
        return self._response

    @property
    def status(self) -> AgentResultStatus:
        """Get the result status."""
        return self._status

    @property
    def iteration_count(self) -> int:
        """Get the number of iterations."""
        return self._iteration_count

    @property
    def tokens_used(self) -> int:
        """Get the number of tokens used."""
        return self._tokens_used

    @property
    def error_message(self) -> Optional[str]:
        """Get the error message if any."""
        return self._error_message

    def is_success(self) -> bool:
        """Check if the result is successful."""
        return self._status == AgentResultStatus.SUCCESS

    def is_error(self) -> bool:
        """Check if the result is an error."""
        return self._status == AgentResultStatus.ERROR

    def is_timeout(self) -> bool:
        """Check if the result is a timeout."""
        return self._status == AgentResultStatus.TIMEOUT

    @staticmethod
    def success(
        response: str, iteration_count: int = 1, tokens_used: int = 0
    ) -> "AgentResult":
        """
        Create a successful result.

        Args:
            response: The response text
            iteration_count: Number of iterations
            tokens_used: Number of tokens used

        Returns:
            AgentResult with SUCCESS status
        """
        return AgentResult(
            response=response,
            status=AgentResultStatus.SUCCESS,
            iteration_count=iteration_count,
            tokens_used=tokens_used,
        )

    @staticmethod
    def error(message: str) -> "AgentResult":
        """
        Create an error result.

        Args:
            message: The error message

        Returns:
            AgentResult with ERROR status
        """
        return AgentResult(
            response="",
            status=AgentResultStatus.ERROR,
            error_message=message,
        )

    @staticmethod
    def timeout(message: str = "Operation timed out") -> "AgentResult":
        """
        Create a timeout result.

        Args:
            message: The timeout message

        Returns:
            AgentResult with TIMEOUT status
        """
        return AgentResult(
            response="",
            status=AgentResultStatus.TIMEOUT,
            error_message=message,
        )

    @staticmethod
    def builder() -> "AgentResultBuilder":
        """Create a new result builder."""
        return AgentResultBuilder()


class AgentResultBuilder:
    """Builder for AgentResult."""

    def __init__(self) -> None:
        self._response: str = ""
        self._status: AgentResultStatus = AgentResultStatus.SUCCESS
        self._iteration_count: int = 0
        self._tokens_used: int = 0
        self._error_message: Optional[str] = None

    def response(self, response: str) -> "AgentResultBuilder":
        """Set the response text."""
        self._response = response
        return self

    def status(self, status: AgentResultStatus) -> "AgentResultBuilder":
        """Set the status."""
        self._status = status
        return self

    def iteration_count(self, count: int) -> "AgentResultBuilder":
        """Set the iteration count."""
        self._iteration_count = count
        return self

    def tokens_used(self, tokens: int) -> "AgentResultBuilder":
        """Set the tokens used."""
        self._tokens_used = tokens
        return self

    def error_message(self, message: str) -> "AgentResultBuilder":
        """Set the error message."""
        self._error_message = message
        return self

    def build(self) -> AgentResult:
        """Build the AgentResult."""
        return AgentResult(
            response=self._response,
            status=self._status,
            iteration_count=self._iteration_count,
            tokens_used=self._tokens_used,
            error_message=self._error_message,
        )
