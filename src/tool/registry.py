"""
Tool registry for managing available tools.

This module provides the ToolRegistry class for registering and retrieving tools.
"""

from typing import Dict, List, Optional
from .base import ToolDefinition


class ToolRegistry:
    """
    Registry for managing available tools.

    This class provides a central place to register and retrieve tool definitions.
    """

    def __init__(self):
        """Initialize an empty registry."""
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """
        Register a tool.

        Args:
            tool: Tool definition to register

        Raises:
            ValueError: If a tool with the same ID is already registered
        """
        if tool.id in self._tools:
            raise ValueError(f"Tool '{tool.id}' is already registered")
        self._tools[tool.id] = tool

    def get(self, tool_id: str) -> Optional[ToolDefinition]:
        """
        Get a tool by ID.

        Args:
            tool_id: Tool identifier

        Returns:
            Tool definition if found, None otherwise
        """
        return self._tools.get(tool_id)

    def list(self) -> List[ToolDefinition]:
        """
        List all registered tools.

        Returns:
            List of all tool definitions
        """
        return list(self._tools.values())

    def has(self, tool_id: str) -> bool:
        """
        Check if a tool is registered.

        Args:
            tool_id: Tool identifier

        Returns:
            True if tool is registered
        """
        return tool_id in self._tools

    def remove(self, tool_id: str) -> bool:
        """
        Remove a tool from the registry.

        Args:
            tool_id: Tool identifier

        Returns:
            True if tool was removed, False if not found
        """
        if tool_id in self._tools:
            del self._tools[tool_id]
            return True
        return False

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()

    @property
    def count(self) -> int:
        """Get the number of registered tools."""
        return len(self._tools)


# Global registry instance
_global_registry = ToolRegistry()


def get_global_registry() -> ToolRegistry:
    """
    Get the global tool registry.

    Returns:
        Global ToolRegistry instance
    """
    return _global_registry


def register_tool(tool: ToolDefinition) -> None:
    """
    Register a tool in the global registry.

    Args:
        tool: Tool definition to register
    """
    _global_registry.register(tool)


def get_tool(tool_id: str) -> Optional[ToolDefinition]:
    """
    Get a tool from the global registry.

    Args:
        tool_id: Tool identifier

    Returns:
        Tool definition if found
    """
    return _global_registry.get(tool_id)


def list_tools() -> List[ToolDefinition]:
    """
    List all tools in the global registry.

    Returns:
        List of all tool definitions
    """
    return _global_registry.list()
