"""Tool factory for creating tools with minimal boilerplate."""

from typing import Dict, Any, Callable, List
from dataclasses import dataclass


@dataclass
class ToolSpec:
    """Specification for creating a tool."""
    name: str
    description: str
    properties: Dict[str, Any] = None
    required: List[str] = None

    def __post_init__(self):
        if self.properties is None:
            self.properties = {}
        if self.required is None:
            self.required = []


class ToolFactory:
    """Factory for creating tools with common patterns."""

    @staticmethod
    def create_lsp_tools(lsp_manager) -> Dict[str, Any]:
        """Create LSP tools with minimal duplication."""
        from ai_sdk.tool import Tool as AI_SDK_Tool

        # Define LSP tool specifications
        specs = [
            ToolSpec(
                name="lsp:diagnostics",
                description="Get LSP diagnostics for the project",
            ),
            ToolSpec(
                name="lsp:definition",
                description="Go to definition",
                properties={
                    "filepath": {"type": "string"},
                    "line": {"type": "integer"},
                    "character": {"type": "integer"},
                },
                required=["filepath", "line", "character"],
            ),
            ToolSpec(
                name="lsp:hover",
                description="Get hover information",
                properties={
                    "filepath": {"type": "string"},
                    "line": {"type": "integer"},
                    "character": {"type": "integer"},
                },
                required=["filepath", "line", "character"],
            ),
            ToolSpec(
                name="lsp:references",
                description="Find references",
                properties={
                    "filepath": {"type": "string"},
                    "line": {"type": "integer"},
                    "character": {"type": "integer"},
                },
                required=["filepath", "line", "character"],
            ),
        ]

        tools = {}
        for spec in specs:
            executor = ToolFactory._create_lsp_executor(spec.name, lsp_manager)
            tools[spec.name] = AI_SDK_Tool(
                name=spec.name,
                description=spec.description,
                input_schema={
                    "type": "object",
                    "properties": spec.properties,
                    "required": spec.required,
                },
                execute=executor,
            )

        return tools

    @staticmethod
    def _create_lsp_executor(tool_name: str, lsp_manager) -> Callable:
        """Create executor function for LSP tool."""
        action = tool_name.split(":")[-1]

        async def executor(**kwargs) -> str:
            if action == "diagnostics":
                return "LSP diagnostics executed"
            else:
                filepath = kwargs.get("filepath", "")
                line = kwargs.get("line", 0)
                character = kwargs.get("character", 0)
                return f"LSP {action}: {filepath}:{line}:{character}"

        return executor
