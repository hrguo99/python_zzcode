"""
Tool calling interface for AI SDK.

This module provides tool/function calling capabilities similar to OpenCode's tool system.
"""

from __future__ import annotations

from typing import Any, Callable, Awaitable, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
import json
import inspect

if TYPE_CHECKING:
    from ai_sdk.message import Message


class ToolError(Exception):
    """Base exception for tool-related errors."""
    pass


class ToolExecutionError(ToolError):
    """Exception raised when tool execution fails."""
    pass


class ToolValidationError(ToolError):
    """Exception raised when tool input validation fails."""
    pass


class ToolPermissionError(ToolError):
    """Exception raised when tool permission is denied."""
    pass


@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    output: str | dict[str, Any]
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata
        }


@dataclass
class ToolCall:
    """Represents a single tool call from the AI."""
    id: str
    name: str
    input: dict[str, Any]
    tool: Tool | None = None

    async def execute(self) -> ToolResult:
        """
        Execute the tool call.

        Returns:
            ToolResult containing the execution result

        Raises:
            ToolExecutionError: If tool is not found or execution fails
        """
        if self.tool is None:
            raise ToolExecutionError(f"Tool '{self.name}' not found")

        try:
            # Validate input
            validation_error = self.tool.validate_input(self.input)
            if validation_error:
                raise ToolValidationError(validation_error)

            # Execute tool
            result = await self.tool.execute(self.input)

            if isinstance(result, ToolResult):
                return result
            else:
                # Convert simple return values to ToolResult
                return ToolResult(
                    success=True,
                    output=str(result) if not isinstance(result, (str, dict)) else result
                )

        except ToolPermissionError as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Permission denied: {str(e)}"
            )
        except ToolValidationError as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Validation error: {str(e)}"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Execution error: {str(e)}"
            )


class Tool:
    """
    Represents a callable tool/function that the AI can invoke.

    Example:
        ```python
        async def get_weather(location: str) -> str:
            return f"Weather in {location}: Sunny, 72°F"

        tool = Tool(
            name="get_weather",
            description="Get the current weather for a location",
            input_schema={
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city name"
                    }
                },
                "required": ["location"]
            },
            execute=get_weather
        )
        ```
    """

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        execute: Callable[..., Any] | Callable[..., Awaitable[Any]],
        metadata: dict[str, Any] | None = None,
        allowed: bool = True
    ):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.execute_fn = execute
        self.metadata = metadata or {}
        self.allowed = allowed

        # Detect if function is async
        self.is_async = inspect.iscoroutinefunction(execute)

    def validate_input(self, input_data: dict[str, Any]) -> str | None:
        """
        Validate tool input against schema.

        Args:
            input_data: Input data to validate

        Returns:
            Error message if validation fails, None otherwise
        """
        # Check required fields
        required = self.input_schema.get("required", [])
        for field in required:
            if field not in input_data:
                return f"Missing required field: {field}"

        # Check for extra fields (if additionalProperties is False)
        if not self.input_schema.get("additionalProperties", True):
            properties = self.input_schema.get("properties", {}).keys()
            extra = set(input_data.keys()) - set(properties)
            if extra:
                return f"Unexpected fields: {', '.join(extra)}"

        # Type validation (basic)
        properties = self.input_schema.get("properties", {})
        for field, value in input_data.items():
            if field in properties:
                expected_type = properties[field].get("type")
                if expected_type:
                    type_error = self._validate_type(field, value, expected_type)
                    if type_error:
                        return type_error

        return None

    def _validate_type(self, field: str, value: Any, expected_type: str) -> str | None:
        """Validate a field's type."""
        type_map = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict
        }

        expected_python_type = type_map.get(expected_type)
        if expected_python_type and not isinstance(value, expected_python_type):
            return f"Field '{field}' must be {expected_type}, got {type(value).__name__}"

        return None

    async def execute(self, input_data: dict[str, Any]) -> ToolResult | Any:
        """
        Execute the tool with the given input.

        Args:
            input_data: Validated input data

        Returns:
            ToolResult or raw result
        """
        if not self.allowed:
            raise ToolPermissionError(f"Tool '{self.name}' is not allowed")

        # Call the execute function
        if self.is_async:
            result = await self.execute_fn(**input_data)
        else:
            result = self.execute_fn(**input_data)

        return result

    def to_dict(self) -> dict:
        """Convert tool to dictionary format (for API calls)."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema
            }
        }


class ToolRegistry:
    """
    Registry for managing multiple tools.

    Example:
        ```python
        registry = ToolRegistry()

        @registry.tool
        async def get_weather(location: str) -> str:
            return f"Weather in {location}: Sunny"

        # Or manually register
        registry.register(Tool(...))

        # Get tool by name
        tool = registry.get("get_weather")
        ```
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """Unregister a tool by name."""
        if name in self._tools:
            del self._tools[name]

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all(self) -> dict[str, Tool]:
        """Get all registered tools."""
        return self._tools.copy()

    def get_allowed(self) -> dict[str, Tool]:
        """Get only allowed tools."""
        return {
            name: tool
            for name, tool in self._tools.items()
            if tool.allowed
        }

    def allow(self, name: str) -> None:
        """Allow a tool."""
        if name in self._tools:
            self._tools[name].allowed = True

    def deny(self, name: str) -> None:
        """Deny a tool."""
        if name in self._tools:
            self._tools[name].allowed = False

    def tool(self, name: str, description: str | None = None, schema: dict | None = None):
        """
        Decorator for registering tools.

        Example:
            ```python
            @registry.tool
            async def my_function(param: str) -> str:
                return "result"
            ```
        """
        def decorator(func: Callable[..., Any]):
            # Generate schema from function signature if not provided
            if schema is None:
                generated_schema = self._generate_schema_from_function(func)
            else:
                generated_schema = schema

            # Use provided description or generate from docstring
            tool_description = description or func.__doc__ or f"Tool {name}"

            tool = Tool(
                name=name,
                description=tool_description,
                input_schema=generated_schema,
                execute=func
            )
            self.register(tool)
            return func

        return decorator

    def _generate_schema_from_function(self, func: Callable) -> dict:
        """Generate JSON schema from function signature."""
        sig = inspect.signature(func)
        parameters = {}

        for param_name, param in sig.parameters.items():
            param_type = param.annotation

            # Map Python types to JSON schema types
            type_mapping = {
                str: "string",
                int: "integer",
                float: "number",
                bool: "boolean",
                list: "array",
                dict: "object"
            }

            json_type = type_mapping.get(param_type, "string")

            param_info = {"type": json_type}

            # Check if parameter is required
            if param.default == inspect.Parameter.empty:
                param_info["required"] = True

            parameters[param_name] = param_info

        return {
            "type": "object",
            "properties": parameters,
            "required": [
                name for name, info in parameters.items()
                if info.get("required", False)
            ]
        }

    def to_list(self) -> list[dict]:
        """Convert all allowed tools to list format (for API)."""
        return [
            tool.to_dict()
            for tool in self.get_allowed().values()
        ]


def create_tool_call(tool_data: dict[str, Any], registry: ToolRegistry) -> ToolCall:
    """
    Create a ToolCall from provider data and tool registry.

    Args:
        tool_data: Tool call data from provider (id, name, arguments)
        registry: Tool registry to look up the tool

    Returns:
        ToolCall instance
    """
    # Handle different provider formats
    # OpenAI format: {id, type, function: {name, arguments}}
    # Direct format: {id, name, arguments}

    if "function" in tool_data:
        # OpenAI/GLM format
        function_data = tool_data["function"]
        tool_name = function_data.get("name", "")
        arguments = function_data.get("arguments", {})
    else:
        # Direct format
        tool_name = tool_data.get("name", "")
        arguments = tool_data.get("arguments", {})

    # Parse arguments if they're a JSON string
    if isinstance(arguments, str):
        arguments = json.loads(arguments)

    tool = registry.get(tool_name)

    return ToolCall(
        id=tool_data.get("id", ""),
        name=tool_name,
        input=arguments,
        tool=tool
    )
