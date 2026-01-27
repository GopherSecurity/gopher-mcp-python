"""Result classes for agent query execution."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AgentResultStatus(Enum):
    """Status of agent query execution."""

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class AgentResult:
    """Result from agent query execution."""

    response: str
    status: AgentResultStatus
    iteration_count: Optional[int] = None
    tokens_used: Optional[int] = None

    @property
    def is_success(self) -> bool:
        """Check if the result is successful."""
        return self.status == AgentResultStatus.SUCCESS

    @classmethod
    def success(cls, response: str) -> "AgentResult":
        """Create a successful result."""
        return cls(response=response, status=AgentResultStatus.SUCCESS)

    @classmethod
    def error(cls, message: str) -> "AgentResult":
        """Create an error result."""
        return cls(response=message, status=AgentResultStatus.ERROR)

    @classmethod
    def timeout(cls, message: str) -> "AgentResult":
        """Create a timeout result."""
        return cls(response=message, status=AgentResultStatus.TIMEOUT)
