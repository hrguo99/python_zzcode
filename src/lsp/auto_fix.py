"""
Automatic Code Fix System using LSP Code Actions.

This module provides automatic error fixing using LSP Code Actions.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from .models import LSPDiagnostic
from .lsp import LSP
from ..interpreter.feature_flags import get_flags

logger = logging.getLogger(__name__)


@dataclass
class FixResult:
    """Result of a fix operation."""
    filepath: str
    diagnostics_fixed: int
    actions_applied: int
    success: bool
    error: Optional[str] = None


class AutoFixExecutor:
    """
    Automatic code fix executor.

    This class handles automatic code fixing using LSP Code Actions.
    """

    # Safe action kinds that can be auto-applied
    SAFE_ACTION_KINDS = {
        "quickfix.fixAll",
        "source.fixAll",
        "source.organizeImports",
    }

    def __init__(self):
        """Initialize the auto-fix executor."""
        self._enabled: Optional[bool] = None
        self._pending_fixes: Dict[str, List[LSPDiagnostic]] = {}

    def _check_enabled(self) -> bool:
        """
        Check if auto-fix is enabled.

        Returns:
            True if enabled
        """
        if self._enabled is None:
            flags = get_flags()
            self._enabled = flags.is_enabled("lsp_auto_fix")

        return self._enabled

    async def fix_diagnostics(
        self,
        filepath: str,
        diagnostics: List[LSPDiagnostic],
        session_id: str,
    ) -> FixResult:
        """
        Attempt to fix diagnostics automatically.

        Args:
            filepath: Path to the file
            diagnostics: List of diagnostics to fix
            session_id: Session ID (for tracking)

        Returns:
            FixResult with fix outcome
        """
        if not self._check_enabled():
            return FixResult(
                filepath=filepath,
                diagnostics_fixed=0,
                actions_applied=0,
                success=False,
                error="Auto-fix disabled",
            )

        if not diagnostics:
            return FixResult(
                filepath=filepath,
                diagnostics_fixed=0,
                actions_applied=0,
                success=True,
            )

        try:
            # Get LSP client
            manager = LSP.get_manager()
            client = await manager.get_client_for_file(filepath)

            if not client:
                return FixResult(
                    filepath=filepath,
                    diagnostics_fixed=0,
                    actions_applied=0,
                    success=False,
                    error="No LSP client available",
                )

            # Request code actions for each diagnostic
            total_fixed = 0
            total_actions = 0

            for diagnostic in diagnostics:
                # Check if diagnostic has a to_dict method
                diag_dict = (
                    diagnostic.to_dict() if hasattr(diagnostic, 'to_dict')
                    else diagnostic
                )

                actions = await client.request_code_actions(
                    filepath=filepath,
                    range=diagnostic.range,
                    context={
                        "diagnostics": [diag_dict],
                    },
                )

                # Filter safe actions
                safe_actions = [
                    action for action in actions
                    if self._is_safe_action(action)
                ]

                if safe_actions:
                    # Apply the first safe action
                    action = safe_actions[0]
                    applied = await self._apply_action(client, filepath, action)

                    if applied:
                        total_fixed += 1
                        total_actions += 1

            logger.info(
                f"Auto-fix complete for {filepath}: "
                f"{total_fixed}/{len(diagnostics)} fixed, "
                f"{total_actions} actions applied"
            )

            return FixResult(
                filepath=filepath,
                diagnostics_fixed=total_fixed,
                actions_applied=total_actions,
                success=True,
            )

        except Exception as e:
            logger.error(
                f"Error auto-fixing {filepath}: {e}",
                exc_info=True
            )
            return FixResult(
                filepath=filepath,
                diagnostics_fixed=0,
                actions_applied=0,
                success=False,
                error=str(e),
            )

    def _is_safe_action(self, action: Dict[str, Any]) -> bool:
        """
        Check if an action is safe to auto-apply.

        Args:
            action: Code action to check

        Returns:
            True if safe
        """
        # Check action kind
        kind = action.get("kind", "")
        if kind in self.SAFE_ACTION_KINDS:
            return True

        # Check for "quickfix" in kind
        if "quickfix" in kind.lower():
            return True

        return False

    async def _apply_action(
        self,
        client,
        filepath: str,
        action: Dict[str, Any],
    ) -> bool:
        """
        Apply a code action.

        Args:
            client: LSP client
            filepath: Path to the file
            action: Action to apply

        Returns:
            True if successful
        """
        try:
            # Check if action has an edit
            if "edit" in action:
                edit = action["edit"]
                return await client.apply_edit(edit)

            # Some actions need to be executed as commands
            if "command" in action:
                command = action["command"]
                # This would require executing the command
                # For now, skip command-based actions
                logger.debug(f"Skipping command-based action: {command}")
                return False

            return False

        except Exception as e:
            logger.error(f"Error applying action: {e}")
            return False


# Global singleton
_global_auto_fix: Optional[AutoFixExecutor] = None


def get_auto_fix() -> AutoFixExecutor:
    """
    Get the global auto-fix executor instance.

    Returns:
        AutoFixExecutor instance
    """
    global _global_auto_fix
    if _global_auto_fix is None:
        _global_auto_fix = AutoFixExecutor()
    return _global_auto_fix


__all__ = [
    "AutoFixExecutor",
    "FixResult",
    "get_auto_fix",
]
