"""
Data models for the Tool system.

This module defines the core data structures used throughout the tool system.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum
import asyncio


class ToolStatus(str, Enum):
    """Tool execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ToolMetadata:
    """
    Metadata returned by tool execution.

    Attributes:
        truncated: Whether output was truncated
        exit_code: Process exit code (for bash tool)
        output_path: Path to truncated output file
        error: Error message if execution failed
        duration: Execution time in seconds
        [custom]: Additional tool-specific metadata
    """
    truncated: bool = False
    exit_code: Optional[int] = None
    output_path: Optional[str] = None
    error: Optional[str] = None
    duration: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "truncated": self.truncated,
            "exit_code": self.exit_code,
            "output_path": self.output_path,
            "error": self.error,
            "duration": self.duration,
            **self.extra,
        }


@dataclass
class ToolResult:
    """
    Result from tool execution.

    Attributes:
        title: Short title describing the result
        output: Main output text
        metadata: Additional metadata
        attachments: Optional file attachments
    """
    title: str
    output: str
    metadata: ToolMetadata = field(default_factory=ToolMetadata)
    attachments: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "title": self.title,
            "output": self.output,
            "metadata": self.metadata.to_dict(),
            "attachments": self.attachments,
        }


@dataclass
class ToolParameters:
    """
    Base class for tool parameters.

    Each tool should define its own parameters as a dataclass
    that inherits from this or uses Pydantic for validation.
    """
    pass


class PermissionRequest:
    """
    Permission request for tool execution.

    This corresponds to PermissionNext.Request in the TypeScript implementation.
    """

    def __init__(
        self,
        permission: str,
        patterns: List[str],
        always: List[str],
        metadata: Dict[str, Any],
    ):
        """
        Initialize a permission request.

        Args:
            permission: Permission type (e.g., "bash", "edit", "read")
            patterns: File patterns affected
            always: Patterns to always allow
            metadata: Additional metadata about the request
        """
        self.permission = permission
        self.patterns = patterns
        self.always = always
        self.metadata = metadata

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "permission": self.permission,
            "patterns": self.patterns,
            "always": self.always,
            "metadata": self.metadata,
        }
