"""Tests for AgentResult."""

import pytest
from gopher_orch.result import AgentResult, AgentResultStatus


class TestAgentResult:
    """Tests for AgentResult."""

    def test_should_create_success_result(self):
        """Test creating success result."""
        result = AgentResult.success("Hello, world!")

        assert result.response == "Hello, world!"
        assert result.status == AgentResultStatus.SUCCESS
        assert result.is_success() is True
        assert result.is_error() is False
        assert result.is_timeout() is False

    def test_should_create_error_result(self):
        """Test creating error result."""
        result = AgentResult.error("Something went wrong")

        assert result.response == ""
        assert result.error_message == "Something went wrong"
        assert result.status == AgentResultStatus.ERROR
        assert result.is_success() is False
        assert result.is_error() is True
        assert result.is_timeout() is False

    def test_should_create_timeout_result(self):
        """Test creating timeout result."""
        result = AgentResult.timeout("Operation timed out")

        assert result.response == ""
        assert result.error_message == "Operation timed out"
        assert result.status == AgentResultStatus.TIMEOUT
        assert result.is_success() is False
        assert result.is_error() is False
        assert result.is_timeout() is True

    def test_should_create_result_with_metadata_via_builder(self):
        """Test creating result with metadata via builder."""
        result = (
            AgentResult.builder()
            .response("Test response")
            .status(AgentResultStatus.SUCCESS)
            .iteration_count(5)
            .tokens_used(100)
            .build()
        )

        assert result.response == "Test response"
        assert result.status == AgentResultStatus.SUCCESS
        assert result.iteration_count == 5
        assert result.tokens_used == 100

    def test_should_have_optional_fields_default_to_zero(self):
        """Test that optional fields default to zero."""
        result = AgentResult.success("Test")

        assert result.iteration_count == 1
        assert result.tokens_used == 0


class TestAgentResultStatus:
    """Tests for AgentResultStatus enum."""

    def test_should_have_correct_values(self):
        """Test that status enum has correct values."""
        assert AgentResultStatus.SUCCESS.value == "success"
        assert AgentResultStatus.ERROR.value == "error"
        assert AgentResultStatus.TIMEOUT.value == "timeout"

    def test_should_have_distinct_values(self):
        """Test that status enum values are distinct."""
        assert AgentResultStatus.SUCCESS != AgentResultStatus.ERROR
        assert AgentResultStatus.SUCCESS != AgentResultStatus.TIMEOUT
        assert AgentResultStatus.ERROR != AgentResultStatus.TIMEOUT
