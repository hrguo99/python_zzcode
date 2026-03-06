"""
Unit tests for LSP Auto-Diagnostic system.
"""

import pytest
import asyncio
from pathlib import Path
from lsp.auto_diagnostic import LSPAutoDiagnostic, get_auto_diagnostic


class TestLSPAutoDiagnostic:
    """Test LSPAutoDiagnostic functionality."""

    @pytest.fixture
    def auto_diagnostic(self):
        """Create an LSPAutoDiagnostic instance."""
        return LSPAutoDiagnostic()

    def test_supported_extensions(self, auto_diagnostic):
        """Test that supported file extensions are correct."""
        assert ".py" in auto_diagnostic.SUPPORTED_EXTENSIONS
        assert ".js" in auto_diagnostic.SUPPORTED_EXTENSIONS
        assert ".ts" in auto_diagnostic.SUPPORTED_EXTENSIONS
        assert ".go" in auto_diagnostic.SUPPORTED_EXTENSIONS
        assert ".rs" in auto_diagnostic.SUPPORTED_EXTENSIONS

    def test_is_supported_file(self, auto_diagnostic):
        """Test _is_supported_file method."""
        assert auto_diagnostic._is_supported_file("test.py") is True
        assert auto_diagnostic._is_supported_file("test.js") is True
        assert auto_diagnostic._is_supported_file("test.txt") is False
        assert auto_diagnostic._is_supported_file("test.md") is False

    @pytest.mark.asyncio
    async def test_trigger_diagnostic_unsupported_file(self, auto_diagnostic, monkeypatch):
        """Test that unsupported files are skipped."""
        # Disable the feature flag check by mocking
        from interpreter import feature_flags
        monkeypatch.setattr(
            feature_flags.FeatureFlags,
            "is_enabled",
            lambda self, name: True
        )

        # This should not raise any error
        await auto_diagnostic.trigger_diagnostic(
            filepath="test.txt",
            tool_name="write",
            session_id="test_session",
        )

        # Check that no pending request was added
        assert len(auto_diagnostic._pending) == 0

    @pytest.mark.asyncio
    async def test_trigger_diagnostic_disabled_flag(self, auto_diagnostic):
        """Test that diagnostic is not triggered when flag is disabled."""
        # Flag is disabled by default for this test
        from interpreter import feature_flags
        flags = feature_flags.get_flags()
        flags.disable("lsp_implicit_integration")

        await auto_diagnostic.trigger_diagnostic(
            filepath="test.py",
            tool_name="write",
            session_id="test_session",
        )

        # Check that no pending request was added
        assert len(auto_diagnostic._pending) == 0

    def test_debounce_time(self, auto_diagnostic):
        """Test that debounce time is set correctly."""
        assert auto_diagnostic.DEBOUNCE_TIME == 0.5

    @pytest.mark.asyncio
    async def test_multiple_rapid_calls_debounced(self, auto_diagnostic, monkeypatch):
        """Test that rapid calls are debounced."""
        # Enable flag
        from interpreter import feature_flags
        monkeypatch.setattr(
            feature_flags.FeatureFlags,
            "is_enabled",
            lambda self, name: True
        )

        # Mock LSP.hasClients to return True
        from lsp import lsp
        monkeypatch.setattr(lsp.LSP, "hasClients", lambda filepath: asyncio.sleep(0).then(lambda _: True))

        # Trigger multiple rapid calls
        await auto_diagnostic.trigger_diagnostic("test.py", "write", "session1")
        await auto_diagnostic.trigger_diagnostic("test.py", "write", "session2")
        await auto_diagnostic.trigger_diagnostic("test.py", "write", "session3")

        # Should only have one pending request
        assert len(auto_diagnostic._pending) == 1

    def test_global_singleton(self):
        """Test global singleton instance."""
        diag1 = get_auto_diagnostic()
        diag2 = get_auto_diagnostic()

        assert diag1 is diag2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
