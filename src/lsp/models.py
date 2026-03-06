"""
Data models for the LSP system.

This module defines the core data structures used throughout the LSP system.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum


class LSPSymbolKind(int, Enum):
    """LSP symbol kinds."""
    FILE = 1
    MODULE = 2
    NAMESPACE = 3
    PACKAGE = 4
    CLASS = 5
    METHOD = 6
    PROPERTY = 7
    FIELD = 8
    CONSTRUCTOR = 9
    ENUM = 10
    INTERFACE = 11
    FUNCTION = 12
    VARIABLE = 13
    CONSTANT = 14
    STRING = 15
    NUMBER = 16
    BOOLEAN = 17
    ARRAY = 18
    OBJECT = 19
    KEY = 20
    NULL = 21
    ENUM_MEMBER = 22
    STRUCTURE = 23
    EVENT = 24
    OPERATOR = 25
    TYPE_PARAMETER = 26


@dataclass
class LSPPosition:
    """Position in a text document."""
    line: int  # 0-based
    character: int  # 0-based (UTF-16 code unit)

    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary representation."""
        return {
            "line": self.line,
            "character": self.character,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> "LSPPosition":
        """Create from dictionary representation."""
        return cls(line=data["line"], character=data["character"])

    def to_lsp(self) -> Dict[str, int]:
        """Convert to LSP format (1-based)."""
        return {
            "line": self.line + 1,
            "character": self.character + 1,
        }


@dataclass
class LSPRange:
    """A range in a text document."""
    start: LSPPosition
    end: LSPPosition

    def to_dict(self) -> Dict[str, Dict[str, int]]:
        """Convert to dictionary representation."""
        return {
            "start": self.start.to_dict(),
            "end": self.end.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LSPRange":
        """Create from dictionary representation."""
        return cls(
            start=LSPPosition.from_dict(data["start"]),
            end=LSPPosition.from_dict(data["end"]),
        )


@dataclass
class LSPLocation:
    """A location in a text document."""
    uri: str  # File URI
    range: LSPRange

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "uri": self.uri,
            "range": self.range.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LSPLocation":
        """Create from dictionary representation."""
        return cls(
            uri=data["uri"],
            range=LSPRange.from_dict(data["range"]),
        )


@dataclass
class LSPSymbol:
    """A symbol in code."""
    name: str
    kind: LSPSymbolKind
    location: LSPLocation

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "kind": self.kind.value,
            "location": self.location.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LSPSymbol":
        """Create from dictionary representation."""
        return cls(
            name=data["name"],
            kind=LSPSymbolKind(data["kind"]),
            location=LSPLocation.from_dict(data["location"]),
        )


@dataclass
class LSPDocumentSymbol:
    """A symbol in a document (with range instead of location)."""
    name: str
    kind: LSPSymbolKind
    range: LSPRange
    selection_range: LSPRange
    detail: Optional[str] = None
    children: List["LSPDocumentSymbol"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "kind": self.kind.value,
            "range": self.range.to_dict(),
            "selectionRange": self.selection_range.to_dict(),
            "detail": self.detail,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class LSPDiagnostic:
    """A diagnostic from a language server."""
    range: LSPRange
    severity: Optional[int] = None  # 1: Error, 2: Warning, 3: Info, 4: Hint
    code: Optional[str] = None
    source: Optional[str] = None
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "range": self.range.to_dict(),
            "severity": self.severity,
            "code": self.code,
            "source": self.source,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LSPDiagnostic":
        """Create from dictionary representation."""
        return cls(
            range=LSPRange.from_dict(data["range"]),
            severity=data.get("severity"),
            code=data.get("code"),
            source=data.get("source"),
            message=data.get("message", ""),
        )


@dataclass
class LSPHover:
    """Hover result."""
    contents: str
    range: Optional[LSPRange] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "contents": self.contents,
        }
        if self.range:
            result["range"] = self.range.to_dict()
        return result


class LSPError(Exception):
    """Base exception for LSP-related errors."""

    def __init__(self, message: str, server_id: Optional[str] = None):
        """
        Initialize an LSP error.

        Args:
            message: Error message
            server_id: Optional server identifier
        """
        self.message = message
        self.server_id = server_id
        super().__init__(message)


class LSPInitializeError(LSPError):
    """Raised when LSP client initialization fails."""

    pass


class LSPServerError(LSPError):
    """Raised when LSP server operation fails."""

    pass
