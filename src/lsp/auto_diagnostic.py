"""
Automatic LSP Diagnostics System.

This module provides automatic LSP diagnostic triggering after file operations.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass

from .lsp import LSP
from ..interpreter.feature_flags import get_flags, FlagState

logger = logging.getLogger(__name__)


@dataclass
class DiagnosticRequest:
    """A pending diagnostic request."""
    filepath: str
    timestamp: float
    tool_name: str
    session_id: str


class LSPAutoDiagnostic:
    """
    Automatic LSP diagnostic trigger.

    This class manages automatic LSP diagnostics after file operations.
    It implements debouncing to avoid excessive LSP requests.
    """

    # Debounce time in seconds
    DEBOUNCE_TIME = 0.5

    # Supported file extensions (when LSP servers are available)
    SUPPORTED_EXTENSIONS = {
        ".py", ".js", ".ts", ".tsx", ".jsx",
        ".go", ".rs", ".java", ".cpp", ".c", ".h",
        ".cs", ".php", ".rb", ".swift", ".kt"
    }

    def __init__(self):
        """Initialize the auto-diagnostic system."""
        self._pending: Dict[str, DiagnosticRequest] = {}
        self._debounce_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._enabled: Optional[bool] = None

    def _check_enabled(self) -> bool:
        """
        Check if auto-diagnostics are enabled.

        Returns:
            True if enabled
        """
        if self._enabled is None:
            flags = get_flags()
            self._enabled = flags.is_enabled("lsp_implicit_integration")

        return self._enabled

    def _is_supported_file(self, filepath: str) -> bool:
        """
        Check if file type is supported.

        Args:
            filepath: Path to the file

        Returns:
            True if file type is supported
        """
        ext = Path(filepath).suffix.lower()
        return ext in self.SUPPORTED_EXTENSIONS

    async def trigger_diagnostic(
        self,
        filepath: str,
        tool_name: str,
        session_id: str,
    ) -> None:
        """
        Trigger LSP diagnostics for a file.

        This method implements debouncing - multiple rapid calls for the same
        file will only result in one diagnostic request.

        Args:
            filepath: Path to the file
            tool_name: Name of the tool that triggered this
            session_id: Current session ID
        """
        # Check if enabled
        if not self._check_enabled():
            logger.debug("LSP auto-diagnostics disabled")
            return

        # Check file type
        if not self._is_supported_file(filepath):
            logger.debug(f"Unsupported file type: {filepath}")
            return

        # Check if LSP is available
        has_lsp = await LSP.hasClients(filepath)
        if not has_lsp:
            logger.debug(f"No LSP server for: {filepath}")
            return

        # Add to pending
        async with self._lock:
            self._pending[filepath] = DiagnosticRequest(
                filepath=filepath,
                timestamp=time.time(),
                tool_name=tool_name,
                session_id=session_id,
            )

            # Reset debounce timer
            if self._debounce_task and not self._debounce_task.done():
                self._debounce_task.cancel()

            # Schedule debounced execution
            self._debounce_task = asyncio.create_task(
                self._execute_debounced()
            )

    async def _execute_debounced(self) -> None:
        """Execute pending diagnostics after debounce delay."""
        await asyncio.sleep(self.DEBOUNCE_TIME)

        async with self._lock:
            # Get pending requests
            pending = list(self._pending.values())
            self._pending.clear()

        # Execute diagnostics
        for request in pending:
            try:
                logger.info(
                    f"Running LSP diagnostics for {request.filepath} "
                    f"(triggered by {request.tool_name})"
                )
                await LSP.touchFile(request.filepath, wait=True)

                # Get diagnostics
                diagnostics = await LSP.diagnostics()
                file_diagnostics = diagnostics.get(request.filepath, [])

                if file_diagnostics:
                    logger.info(
                        f"Found {len(file_diagnostics)} diagnostic(s) for "
                        f"{request.filepath}"
                    )

                    # Trigger auto-fix if enabled
                    if get_flags().is_enabled("lsp_auto_fix"):
                        await self._trigger_auto_fix(
                            request.filepath,
                            file_diagnostics,
                            request.session_id
                        )

            except Exception as e:
                logger.error(
                    f"Error running LSP diagnostics for {request.filepath}: {e}",
                    exc_info=True
                )

    async def _trigger_auto_fix(
        self,
        filepath: str,
        diagnostics: List,
        session_id: str,
    ) -> None:
        """
        Trigger auto-fix for diagnostics.

        This will be implemented in the auto-fix component.

        Args:
            filepath: Path to the file
            diagnostics: Diagnostics to fix
            session_id: Session ID
        """
        # Import here to avoid circular dependency
        from .auto_fix import get_auto_fix

        auto_fix = get_auto_fix()

        # Convert diagnostics to list if needed
        if hasattr(diagnostics, '__iter__'):
            diag_list = list(diagnostics)
        else:
            diag_list = [diagnostics]

        result = await auto_fix.fix_diagnostics(
            filepath=filepath,
            diagnostics=diag_list,
            session_id=session_id,
        )

        if result.success and result.diagnostics_fixed > 0:
            logger.info(
                f"Auto-fixed {result.diagnostics_fixed} error(s) in {filepath}"
            )


# Global singleton
_global_auto_diagnostic: Optional[LSPAutoDiagnostic] = None


def get_auto_diagnostic() -> LSPAutoDiagnostic:
    """
    Get the global auto-diagnostic instance.

    Returns:
        LSPAutoDiagnostic instance
    """
    global _global_auto_diagnostic
    if _global_auto_diagnostic is None:
        _global_auto_diagnostic = LSPAutoDiagnostic()
    return _global_auto_diagnostic


__all__ = [
    "LSPAutoDiagnostic",
    "get_auto_diagnostic",
]
