"""
OpenCode LSP Module - Python Implementation

This module provides Language Server Protocol support for OpenCode, including:
- LSP client management
- LSP server definitions and spawning
- Language intelligence features
- Tool integration for agent usage
"""

from .models import LSPRange, LSPSymbol, LSPDiagnostic, LSPPosition
from .client import LSPClient, LSPClientInfo
from .server import LSPServerInfo, LSPServerRegistry, LanguageServerID
from .lsp import LSPManager, LSP
from .tools import LSPTool

__all__ = [
    # Data models
    "LSPRange",
    "LSPSymbol",
    "LSPDiagnostic",
    "LSPPosition",

    # Client
    "LSPClient",
    "LSPClientInfo",

    # Server
    "LSPServerInfo",
    "LSPServerRegistry",
    "LanguageServerID",

    # Main LSP interface
    "LSPManager",
    "LSP",

    # Tools
    "LSPTool",
]

__version__ = "0.1.0"
