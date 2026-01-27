"""Tests for AgentResult."""

from gopher_orch.result import AgentResult, AgentResultStatus


class TestAgentResult:
    """Tests for AgentResult dataclass."""

    def test_success_result(self):
        """Test creating a success result."""
        result = AgentResult.success("Hello, world!")

        assert result.response == "Hello, world!"
        assert result.status == AgentResultStatus.SUCCESS
        assert result.is_success is True

    def test_error_result(self):
        """Test creating an error result."""
        result = AgentResult.error("Something went wrong")

        assert result.response == "Something went wrong"
        assert result.status == AgentResultStatus.ERROR
        assert result.is_success is False

    def test_timeout_result(self):
        """Test creating a timeout result."""
        result = AgentResult.timeout("Operation timed out")

        assert result.response == "Operation timed out"
        assert result.status == AgentResultStatus.TIMEOUT
        assert result.is_success is False

    def test_result_with_metadata(self):
        """Test creating result with metadata."""
        result = AgentResult(
            response="Test response",
            status=AgentResultStatus.SUCCESS,
            iteration_count=5,
            tokens_used=100,
        )

        assert result.response == "Test response"
        assert result.status == AgentResultStatus.SUCCESS
        assert result.iteration_count == 5
        assert result.tokens_used == 100

    def test_optional_fields_default_to_none(self):
        """Test that optional fields default to None for factory methods."""
        result = AgentResult.success("Test")

        assert result.iteration_count is None
        assert result.tokens_used is None


class TestAgentResultStatus:
    """Tests for AgentResultStatus enum."""

    def test_status_values(self):
        """Test enum values exist."""
        assert AgentResultStatus.SUCCESS is not None
        assert AgentResultStatus.ERROR is not None
        assert AgentResultStatus.TIMEOUT is not None

    def test_status_are_distinct(self):
        """Test status values are distinct."""
        assert AgentResultStatus.SUCCESS != AgentResultStatus.ERROR
        assert AgentResultStatus.SUCCESS != AgentResultStatus.TIMEOUT
        assert AgentResultStatus.ERROR != AgentResultStatus.TIMEOUT
