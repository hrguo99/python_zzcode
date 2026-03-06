"""
Core Tool framework.

This module provides the base classes and interfaces for defining and executing tools.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Callable, TypeVar, Generic
from dataclasses import dataclass
import inspect

from .models import ToolResult, ToolMetadata, PermissionRequest


@dataclass
class ToolContext:
    """
    Execution context for a tool.

    This provides the tool with access to session information,
    ability to request permissions, and update metadata.

    Corresponds to Tool.Context in the TypeScript implementation.
    """

    session_id: str
    message_id: str
    agent: str
    abort_signal: Optional[asyncio.Event] = None
    call_id: Optional[str] = None
    extra: Dict[str, Any] = None
    messages: List[Dict[str, Any]] = None

    # Callbacks
    metadata_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    permission_callback: Optional[Callable[[PermissionRequest], None]] = None

    def __post_init__(self):
        if self.extra is None:
            self.extra = {}
        if self.messages is None:
            self.messages = []

    def update_metadata(self, title: Optional[str] = None, metadata: Dict[str, Any] = None):
        """
        Update execution metadata.

        Args:
            title: Optional title for the execution
            metadata: Additional metadata key-value pairs
        """
        data = {}
        if title is not None:
            data["title"] = title
        if metadata:
            data["metadata"] = metadata

        if self.metadata_callback:
            self.metadata_callback(data)

    async def ask_permission(
        self,
        permission: str,
        patterns: List[str],
        always: List[str],
        metadata: Dict[str, Any] = None,
    ):
        """
        Request permission for an operation.

        Args:
            permission: Permission type (e.g., "bash", "edit")
            patterns: File patterns affected
            always: Patterns to always allow
            metadata: Additional metadata

        Raises:
            PermissionDenied: If permission is denied
        """
        request = PermissionRequest(
            permission=permission,
            patterns=patterns,
            always=always,
            metadata=metadata or {},
        )

        if self.permission_callback:
            await self.permission_callback(request)

    def is_aborted(self) -> bool:
        """Check if execution has been aborted."""
        if self.abort_signal is None:
            return False
        # Check for AbortSignal.aborted property
        if hasattr(self.abort_signal, 'aborted'):
            return self.abort_signal.aborted
        # Check for asyncio.Event.is_set() method
        if hasattr(self.abort_signal, 'is_set'):
            return self.abort_signal.is_set()
        return False


T = TypeVar('T')


class ToolDefinition(ABC, Generic[T]):
    """
    Base class for tool definitions.

    Each tool should inherit from this class and implement the required methods.
    """

    def __init__(self, tool_id: str, allowed: bool = True):
        """
        Initialize the tool definition.

        Args:
            tool_id: Unique identifier for this tool
            allowed: Whether this tool is allowed to be used (default: True)
        """
        self.tool_id = tool_id
        self.allowed = allowed
        self._description: Optional[str] = None
        self._parameters_schema: Optional[Dict[str, Any]] = None
        self._initialized: bool = False

    @property
    def id(self) -> str:
        """Get the tool ID."""
        return self.tool_id

    async def _ensure_initialized(self) -> None:
        """
        Ensure the tool is initialized.

        This is called automatically when accessing description or parameters_schema.
        """
        if not self._initialized:
            await self.initialize()
            self._initialized = True

    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the tool.

        This is called once when the tool is registered.
        Use this to set up description and parameters.
        """

    @abstractmethod
    async def execute(self, args: T, ctx: ToolContext) -> ToolResult:
        """
        Execute the tool with given arguments.

        Args:
            args: Tool-specific arguments
            ctx: Execution context

        Returns:
            ToolResult containing output and metadata

        Raises:
            ValueError: If arguments are invalid
            PermissionError: If permission is denied
            RuntimeError: If execution fails
        """

    @property
    def description(self) -> str:
        """Get tool description."""
        if self._description is None:
            raise NotImplementedError(f"Tool {self.id} has not been initialized. Call await initialize() first.")
        return self._description

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        """Get JSON schema for parameters."""
        if self._parameters_schema is None:
            raise NotImplementedError(f"Tool {self.id} has not been initialized. Call await initialize() first.")
        return self._parameters_schema

    def validate_args(self, args: Dict[str, Any]) -> T:
        """
        Validate and convert arguments.

        Default implementation does basic validation.
        Subclasses can override for custom validation.

        Args:
            args: Raw arguments dictionary

        Returns:
            Validated and converted arguments

        Raises:
            ValueError: If arguments are invalid
        """
        # Basic validation - subclasses should override
        return args

    def format_validation_error(self, error: Exception) -> str:
        """
        Format a validation error for display.

        Args:
            error: The validation error

        Returns:
            Formatted error message
        """
        return (
            f"The {self.id} tool was called with invalid arguments: {error}.\n"
            "Please rewrite the input so it satisfies the expected schema."
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert tool to dictionary format (for API calls).

        Returns:
            Tool definition in OpenAI function call format
        """
        return {
            "type": "function",
            "function": {
                "name": self.id,
                "description": self.description,
                "parameters": self.parameters_schema
            }
        }

    async def to_dict_async(self) -> Dict[str, Any]:
        """
        Convert tool to dictionary format (async version, ensures initialization).

        Returns:
            Tool definition in OpenAI function call format
        """
        await self._ensure_initialized()
        return {
            "type": "function",
            "function": {
                "name": self.id,
                "description": self._description,
                "parameters": self._parameters_schema
            }
        }


class SimpleTool(ToolDefinition[Dict[str, Any]]):
    """
    Simplified tool base class.

    This provides a more straightforward way to define tools
    without dealing with generic types.
    """

    def __init__(
        self,
        tool_id: str,
        description: str,
        parameter_schema: Dict[str, Any],
        execute_func: Callable[[Dict[str, Any], ToolContext], ToolResult],
        allowed: bool = True,
    ):
        """
        Initialize a simple tool.

        Args:
            tool_id: Unique identifier
            description: Tool description
            parameter_schema: JSON schema for parameters
            execute_func: Function to execute the tool
            allowed: Whether this tool is allowed to be used (default: True)
        """
        super().__init__(tool_id, allowed=allowed)
        self._description = description
        self._parameters_schema = parameter_schema
        self._execute_func = execute_func

    async def initialize(self) -> None:
        """Initialize the tool (already done in constructor)."""
        pass

    async def execute(self, args: Dict[str, Any], ctx: ToolContext) -> ToolResult:
        """
        Execute the tool.

        Args:
            args: Tool arguments
            ctx: Execution context

        Returns:
            Tool execution result
        """
        # Check for abort
        if ctx.is_aborted():
            raise RuntimeError("Tool execution aborted")

        # Call the execute function
        result = self._execute_func(args, ctx)

        # If it's a coroutine, await it
        if asyncio.iscoroutine(result):
            result = await result

        return result


def define_tool(
    tool_id: str,
    description: str,
    parameters: Dict[str, Any],
    execute: Callable,
) -> ToolDefinition:
    """
    Define a new tool.

    This is a convenience function that creates a SimpleTool.

    Args:
        tool_id: Unique identifier for the tool
        description: Human-readable description
        parameters: JSON schema for parameters
        execute: Function that executes the tool

    Returns:
        ToolDefinition instance

    Example:
        ```python
        tool = define_tool(
            "my_tool",
            "Does something useful",
            {
                "type": "object",
                "properties": {
                    "input": {"type": "string"},
                },
                "required": ["input"],
            },
            lambda args, ctx: ToolResult(
                title="Result",
                output=f"Processed: {args['input']}",
            ),
        )
        ```
    """
    return SimpleTool(tool_id, description, parameters, execute)


# Export commonly used types
Tool = ToolDefinition
