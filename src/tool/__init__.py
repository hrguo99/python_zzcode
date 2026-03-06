"""
OpenCode Tool Module - Python Implementation

This module provides the core tool functionality for OpenCode, including:
- Tool definition and execution framework
- Built-in tools (bash, read, edit, write, glob, grep, etc.)
- Tool registration and management
- Permission integration
"""

from .base import Tool, ToolContext, ToolResult, ToolDefinition, define_tool
from .models import ToolMetadata, ToolParameters
from .registry import ToolRegistry

# Import built-in tools
from .tools import (
    BashTool,
    ReadTool,
    EditTool,
    WriteTool,
    GlobTool,
    GrepTool,
)

__all__ = [
    # Core framework
    "Tool",
    "ToolContext",
    "ToolResult",
    "ToolDefinition",
    "ToolMetadata",
    "ToolParameters",
    "define_tool",

    # Registry
    "ToolRegistry",

    # Built-in tools
    "BashTool",
    "ReadTool",
    "EditTool",
    "WriteTool",
    "GlobTool",
    "GrepTool",
]

__version__ = "0.1.0"
