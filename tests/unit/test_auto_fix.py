"""
Unit tests for LSP Auto-Fix system.
"""

import pytest
from lsp.auto_fix import AutoFixExecutor, FixResult, get_auto_fix
from lsp.models import LSPDiagnostic, LSPRange, LSPPosition


class TestAutoFixExecutor:
    """Test AutoFixExecutor functionality."""

    @pytest.fixture
    def auto_fix(self):
        """Create an AutoFixExecutor instance."""
        return AutoFixExecutor()

    def test_safe_action_kinds(self, auto_fix):
        """Test that safe action kinds are defined."""
        assert "quickfix.fixAll" in auto_fix.SAFE_ACTION_KINDS
        assert "source.fixAll" in auto_fix.SAFE_ACTION_KINDS
        assert "source.organizeImports" in auto_fix.SAFE_ACTION_KINDS

    def test_is_safe_action(self, auto_fix):
        """Test _is_safe_action method."""
        # Safe actions
        assert auto_fix._is_safe_action({"kind": "quickfix.fixAll"}) is True
        assert auto_fix._is_safe_action({"kind": "source.fixAll"}) is True
        assert auto_fix._is_safe_action({"kind": "source.organizeImports"}) is True
        assert auto_fix._is_safe_action({"kind": "quickfix.something"}) is True

        # Unsafe actions
        assert auto_fix._is_safe_action({"kind": "refactor.extract"}) is False
        assert auto_fix._is_safe_action({"kind": "source.rename"}) is False
        assert auto_fix._is_safe_action({}) is False

    def test_check_enabled_disabled(self, auto_fix):
        """Test _check_enabled when flag is disabled."""
        from interpreter import feature_flags
        flags = feature_flags.get_flags()
        flags.disable("lsp_auto_fix")

        assert auto_fix._check_enabled() is False

    def test_fix_diagnostics_disabled(self, auto_fix):
        """Test that fix_diagnostics returns error when disabled."""
        from interpreter import feature_flags
        flags = feature_flags.get_flags()
        flags.disable("lsp_auto_fix")

        diagnostic = LSPDiagnostic(
            range=LSPRange(
                start=LSPPosition(0, 0),
                end=LSPPosition(0, 10),
            ),
            message="Test error",
        )

        result = asyncio.run(auto_fix.fix_diagnostics(
            filepath="test.py",
            diagnostics=[diagnostic],
            session_id="test_session",
        ))

        assert result.success is False
        assert result.error == "Auto-fix disabled"
        assert result.diagnostics_fixed == 0

    def test_fix_diagnostics_empty_list(self, auto_fix, monkeypatch):
        """Test that empty diagnostics list is handled correctly."""
        from interpreter import feature_flags
        monkeypatch.setattr(
            feature_flags.FeatureFlags,
            "is_enabled",
            lambda self, name: True
        )

        result = asyncio.run(auto_fix.fix_diagnostics(
            filepath="test.py",
            diagnostics=[],
            session_id="test_session",
        ))

        assert result.success is True
        assert result.diagnostics_fixed == 0
        assert result.actions_applied == 0

    def test_fix_result_dataclass(self):
        """Test FixResult dataclass."""
        result = FixResult(
            filepath="test.py",
            diagnostics_fixed=5,
            actions_applied=3,
            success=True,
        )

        assert result.filepath == "test.py"
        assert result.diagnostics_fixed == 5
        assert result.actions_applied == 3
        assert result.success is True
        assert result.error is None

    def test_fix_result_with_error(self):
        """Test FixResult with error."""
        result = FixResult(
            filepath="test.py",
            diagnostics_fixed=0,
            actions_applied=0,
            success=False,
            error="Test error",
        )

        assert result.success is False
        assert result.error == "Test error"

    def test_global_singleton(self):
        """Test global singleton instance."""
        fix1 = get_auto_fix()
        fix2 = get_auto_fix()

        assert fix1 is fix2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
