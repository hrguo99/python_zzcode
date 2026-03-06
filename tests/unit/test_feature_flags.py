"""
Unit tests for Feature Flags system.
"""

import os
import pytest
from interpreter.feature_flags import FeatureFlags, FlagState, get_flags, set_flags


class TestFeatureFlags:
    """Test FeatureFlags functionality."""

    def test_default_values(self):
        """Test that flags have correct default values."""
        flags = FeatureFlags()

        assert flags.lsp_implicit_integration == FlagState.EXPERIMENTAL
        assert flags.lsp_auto_fix == FlagState.EXPERIMENTAL
        assert flags.lsp_explicit_tool == FlagState.ENABLED

    def test_is_enabled(self):
        """Test is_enabled method."""
        flags = FeatureFlags()

        # lsp_explicit_tool should be enabled by default
        assert flags.is_enabled("lsp_explicit_tool") is True

        # lsp_implicit_integration should not be enabled (it's experimental)
        assert flags.is_enabled("lsp_implicit_integration") is False

    def test_is_experimental(self):
        """Test is_experimental method."""
        flags = FeatureFlags()

        assert flags.is_experimental("lsp_implicit_integration") is True
        assert flags.is_experimental("lsp_auto_fix") is True
        assert flags.is_experimental("lsp_explicit_tool") is False

    def test_is_disabled(self):
        """Test is_disabled method."""
        flags = FeatureFlags()

        assert flags.is_disabled("lsp_implicit_integration") is False
        assert flags.is_disabled("lsp_auto_fix") is False
        assert flags.is_disabled("lsp_explicit_tool") is False

    def test_enable(self):
        """Test enable method."""
        flags = FeatureFlags()

        flags.enable("lsp_implicit_integration")
        assert flags.is_enabled("lsp_implicit_integration") is True
        assert flags.is_experimental("lsp_implicit_integration") is False

    def test_disable(self):
        """Test disable method."""
        flags = FeatureFlags()

        flags.disable("lsp_explicit_tool")
        assert flags.is_enabled("lsp_explicit_tool") is False
        assert flags.is_disabled("lsp_explicit_tool") is True

    def test_from_config(self):
        """Test creating flags from config dict."""
        config = {
            "lsp_implicit_integration": "enabled",
            "lsp_auto_fix": "disabled",
        }

        flags = FeatureFlags.from_config(config)

        assert flags.is_enabled("lsp_implicit_integration") is True
        assert flags.is_disabled("lsp_auto_fix") is True

    def test_from_config_bool(self):
        """Test creating flags from config dict with bool values."""
        config = {
            "lsp_implicit_integration": True,
            "lsp_auto_fix": False,
        }

        flags = FeatureFlags.from_config(config)

        assert flags.is_enabled("lsp_implicit_integration") is True
        assert flags.is_disabled("lsp_auto_fix") is True

    def test_to_dict(self):
        """Test converting flags to dict."""
        flags = FeatureFlags()
        flags.enable("lsp_implicit_integration")

        result = flags.to_dict()

        assert "lsp_implicit_integration" in result
        assert result["lsp_implicit_integration"] == "enabled"

    def test_environment_variable_override(monkeypatch):
        """Test environment variable override."""
        # Set environment variable
        monkeypatch.setenv("OPENCODE_FLAG_LSP_IMPLICIT_INTEGRATION", "enabled")

        flags = FeatureFlags()

        assert flags.is_enabled("lsp_implicit_integration") is True

    def test_environment_variable_override_false(monkeypatch):
        """Test environment variable override with false."""
        monkeypatch.setenv("OPENCODE_FLAG_LSP_AUTO_FIX", "false")

        flags = FeatureFlags()

        assert flags.is_disabled("lsp_auto_fix") is True

    def test_global_singleton(self):
        """Test global singleton instance."""
        flags1 = get_flags()
        flags2 = get_flags()

        assert flags1 is flags2

    def test_set_global_flags(self):
        """Test setting global flags."""
        custom_flags = FeatureFlags()
        custom_flags.enable("lsp_implicit_integration")

        set_flags(custom_flags)

        result = get_flags()
        assert result.is_enabled("lsp_implicit_integration") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
