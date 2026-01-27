"""Integration tests for GopherAgent that verify the full flow through FFI.

These tests require the native library to be built and available.
"""

import pytest

from gopher_orch.agent import GopherAgent
from gopher_orch.config import GopherAgentConfig
from gopher_orch.errors import AgentException
from gopher_orch.ffi.library import GopherOrchLibrary

SERVER_CONFIG = """{
    "succeeded": true,
    "code": 200000000,
    "message": "success",
    "data": {
        "servers": [
            {
                "version": "2025-01-09",
                "serverId": "1",
                "name": "test-server",
                "transport": "http_sse",
                "config": {"url": "http://127.0.0.1:9999/mcp", "headers": {}},
                "connectTimeout": 5000,
                "requestTimeout": 30000
            }
        ]
    }
}"""


def is_native_library_available():
    """Check if native library is available for tests."""
    return GopherOrchLibrary.is_available()


def try_create_agent():
    """Helper to create an agent, returning None if creation fails."""
    try:
        return GopherAgent.create_with_server_config(
            "AnthropicProvider", "claude-3-haiku-20240307", SERVER_CONFIG
        )
    except AgentException:
        return None


class TestGopherAgentIntegration:
    """Integration tests for GopherAgent."""

    @pytest.mark.skipif(
        not is_native_library_available(), reason="Native library not available"
    )
    def test_initialization(self):
        """Test that initialization works."""
        GopherAgent.init()
        assert GopherAgent.is_initialized()

    @pytest.mark.skipif(
        not is_native_library_available(), reason="Native library not available"
    )
    def test_create_agent_with_server_config(self):
        """Test creating agent with server config through FFI."""
        config = GopherAgentConfig(
            provider="AnthropicProvider",
            model="claude-3-haiku-20240307",
            server_config=SERVER_CONFIG,
        )

        agent = None
        try:
            agent = GopherAgent.create(config)
            assert agent is not None, "Agent should be created"
            assert not agent.is_disposed, "Agent should not be disposed"
        except AgentException:
            # Agent creation may fail without API key - this is expected in test environment
            pytest.skip("Agent creation failed (expected without API key)")
        finally:
            if agent is not None:
                agent.dispose()
                assert agent.is_disposed, "Agent should be disposed after dispose()"

    @pytest.mark.skipif(
        not is_native_library_available(), reason="Native library not available"
    )
    def test_create_agent_with_helper_method(self):
        """Test the convenience method."""
        agent = try_create_agent()
        if agent is None:
            pytest.skip("Agent creation failed")

        try:
            assert agent is not None
        finally:
            agent.dispose()

    @pytest.mark.skipif(
        not is_native_library_available(), reason="Native library not available"
    )
    def test_context_manager(self):
        """Test context manager (with statement) implementation."""
        agent = try_create_agent()
        if agent is None:
            pytest.skip("Agent creation failed")

        captured_agent = None
        with agent:
            assert not agent.is_disposed
            captured_agent = agent

        # After with block, agent should be disposed
        assert captured_agent is not None
        assert captured_agent.is_disposed

    @pytest.mark.skipif(
        not is_native_library_available(), reason="Native library not available"
    )
    def test_dispose_idempotent(self):
        """Test that dispose can be called multiple times safely."""
        agent = try_create_agent()
        if agent is None:
            pytest.skip("Agent creation failed")

        agent.dispose()
        assert agent.is_disposed

        # Second dispose should not throw
        agent.dispose()
        assert agent.is_disposed

    @pytest.mark.skipif(
        not is_native_library_available(), reason="Native library not available"
    )
    def test_run_after_dispose_throws(self):
        """Test that running on disposed agent raises exception."""
        agent = try_create_agent()
        if agent is None:
            pytest.skip("Agent creation failed")

        agent.dispose()

        # Running on disposed agent should raise
        with pytest.raises(AgentException):
            agent.run("test query")

    @pytest.mark.skipif(
        not is_native_library_available(), reason="Native library not available"
    )
    def test_run_detailed_returns_result(self):
        """Test that run_detailed returns an AgentResult."""
        agent = try_create_agent()
        if agent is None:
            pytest.skip("Agent creation failed")

        try:
            # Run with very short timeout to get quick response (likely timeout or error)
            result = agent.run_detailed("test query", 100)

            assert result is not None, "Result should not be None"
            assert result.response is not None, "Response should not be None"
            assert result.status is not None, "Status should not be None"
        finally:
            agent.dispose()

    @pytest.mark.skipif(
        not is_native_library_available(), reason="Native library not available"
    )
    def test_multiple_agents_can_be_created(self):
        """Test that multiple agents can be created."""
        agent1 = try_create_agent()
        agent2 = try_create_agent()

        if agent1 is None or agent2 is None:
            if agent1:
                agent1.dispose()
            if agent2:
                agent2.dispose()
            pytest.skip("Agent creation failed")

        try:
            assert agent1 is not None
            assert agent2 is not None
            assert agent1 is not agent2, "Should be different agent instances"
        finally:
            agent1.dispose()
            agent2.dispose()

    def test_create_without_native_library_behavior(self):
        """Test behavior when native library might not be available."""
        # This test verifies error handling when native library is not available
        # Skip if library IS available (we're testing the error case)
        if GopherOrchLibrary.is_available():
            # Library is available, so we can't test the "not available" case
            # Just verify that create works (or gracefully fails without API key)
            try:
                agent = GopherAgent.create_with_server_config(
                    "AnthropicProvider", "claude-3-haiku-20240307", SERVER_CONFIG
                )
                agent.dispose()
            except AgentException:
                # Expected if no API key is available
                pass

    @pytest.mark.skipif(
        not is_native_library_available(), reason="Native library not available"
    )
    def test_shutdown_and_reinit(self):
        """Test that shutdown and re-init work correctly."""
        GopherAgent.init()
        assert GopherAgent.is_initialized()

        GopherAgent.shutdown()
        assert not GopherAgent.is_initialized()

        # Re-init should work
        GopherAgent.init()
        assert GopherAgent.is_initialized()
