"""
LSP Tool implementation.

This module provides the LSPTool for agents to use LSP features.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, List
from enum import Enum

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tool.base import ToolDefinition, ToolContext, ToolResult
from tool.models import ToolMetadata
from lsp.models import LSPPosition
from lsp.lsp import LSP


class LSPOperation(str, Enum):
    """LSP operations supported by the tool."""
    GO_TO_DEFINITION = "goToDefinition"
    FIND_REFERENCES = "findReferences"
    HOVER = "hover"
    DOCUMENT_SYMBOL = "documentSymbol"
    WORKSPACE_SYMBOL = "workspaceSymbol"
    GO_TO_IMPLEMENTATION = "goToImplementation"


class LSPTool(ToolDefinition):
    """
    Tool for using LSP features.

    This tool allows agents to perform language intelligence operations
    like go-to-definition, find-references, hover, and more.
    """

    def __init__(self):
        super().__init__("lsp")
        self._description = None
        self._parameters_schema = None

    async def initialize(self) -> None:
        """Initialize the LSP tool."""
        operations = [op.value for op in LSPOperation]
        operations_str = ", ".join(operations)

        self._description = (
            "Perform Language Server Protocol (LSP) operations.\n\n"
            "This tool provides language intelligence features like:\n"
            "- Go to definition (jump to symbol definition)\n"
            "- Find references (find all usages of a symbol)\n"
            "- Hover (get type information and documentation)\n"
            "- Document symbols (list symbols in a file)\n"
            "- Workspace symbols (search symbols across the project)\n\n"
            f"Supported operations: {operations_str}\n\n"
            "Note: LSP servers must be installed and available for this feature to work."
        )

        self._parameters_schema = {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": operations,
                    "description": "The LSP operation to perform",
                },
                "filePath": {
                    "type": "string",
                    "description": "The absolute or relative path to the file",
                },
                "line": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "The line number (1-based, as shown in editors)",
                },
                "character": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "The character offset (1-based, as shown in editors)",
                },
            },
            "required": ["operation", "filePath", "line", "character"],
        }

    async def execute(self, args: Dict[str, Any], ctx: ToolContext) -> ToolResult:
        """
        Execute the LSP tool.

        Args:
            args: Tool arguments
            ctx: Execution context

        Returns:
            ToolResult with operation results
        """
        operation = args["operation"]
        filepath = args["filePath"]
        line = args["line"]
        character = args["character"]

        # Resolve file path
        if not os.path.isabs(filepath):
            filepath = os.path.abspath(filepath)

        # Check file exists
        if not os.path.exists(filepath):
            return ToolResult(
                title=f"LSP Error",
                output=f"File not found: {filepath}",
                metadata=ToolMetadata(error="File not found"),
            )

        # Request permission
        await ctx.ask_permission(
            permission="lsp",
            patterns=["*"],
            always=["*"],
            metadata={
                "operation": operation,
                "file": filepath,
            },
        )

        # Check for abort
        if ctx.is_aborted():
            raise RuntimeError("LSP operation aborted")

        # Initialize LSP if needed
        await LSP.init()

        # Check if LSP is available
        has_clients = await LSP.hasClients(filepath)
        if not has_clients:
            return ToolResult(
                title=f"LSP Not Available",
                output=(
                    "No LSP server is available for this file type. "
                    "LSP servers must be installed and accessible in the system PATH."
                ),
                metadata=ToolMetadata(error="No LSP server available"),
            )

        # Touch file to trigger analysis
        await LSP.touchFile(filepath, wait_for_diagnostics=True)

        # Convert to 0-based position
        position = {
            "file": filepath,
            "line": line - 1,
            "character": character - 1,
        }

        # Execute the requested operation
        result = await self._execute_operation(operation, position)

        # Format output
        filename = os.path.basename(filepath)
        title = f"{operation} {filename}:{line}:{character}"

        return ToolResult(
            title=title,
            output=self._format_result(result, operation),
            metadata=ToolMetadata(extra={"operation": operation}),
        )

    async def _execute_operation(self, operation: str, position: Dict[str, Any]) -> Any:
        """Execute a specific LSP operation."""
        if operation == LSPOperation.GO_TO_DEFINITION.value:
            return await LSP.definition(position)
        elif operation == LSPOperation.FIND_REFERENCES.value:
            return await LSP.references(position)
        elif operation == LSPOperation.HOVER.value:
            return await LSP.hover(position)
        elif operation == LSPOperation.DOCUMENT_SYMBOL.value:
            # For document symbols, we need the URI
            from pathlib import Path
            uri = Path(position["file"]).as_uri()
            return await LSP.documentSymbol(uri)
        elif operation == LSPOperation.WORKSPACE_SYMBOL.value:
            return await LSP.workspaceSymbol("")
        elif operation == LSPOperation.GO_TO_IMPLEMENTATION.value:
            # Similar to definition for now
            return await LSP.definition(position)
        else:
            return []

    def _format_result(self, result: Any, operation: str) -> str:
        """Format LSP operation result for output."""
        if not result:
            return f"No results found for {operation}"

        if isinstance(result, list):
            if len(result) == 0:
                return f"No results found for {operation}"

            # Format list of results
            lines = [f"Found {len(result)} result(s):"]
            for item in result[:20]:  # Limit to first 20 results
                if hasattr(item, "to_dict"):
                    item_dict = item.to_dict()
                elif isinstance(item, dict):
                    item_dict = item
                else:
                    item_dict = str(item)

                if "uri" in item_dict and "range" in item_dict:
                    # Format location
                    from pathlib import Path
                    try:
                        filepath = Path(item_dict["uri"])
                        lines.append(f"  - {filepath}:{item_dict['range']['start']['line']+1}")
                    except:
                        lines.append(f"  - {item_dict}")
                else:
                    lines.append(f"  - {item_dict}")

            if len(result) > 20:
                lines.append(f"  ... and {len(result) - 20} more")

            return "\n".join(lines)

        elif isinstance(result, dict):
            # Single result (like hover)
            if "contents" in result:
                return result["contents"]
            return str(result)
        else:
            return str(result)


def create_lsp_tool() -> LSPTool:
    """
    Create an LSPTool instance.

    Convenience function for creating an LSP tool.

    Returns:
        Initialized LSPTool
    """
    tool = LSPTool()
    # Note: The caller should call await tool.initialize()
    return tool
