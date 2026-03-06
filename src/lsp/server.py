"""
LSP Server definitions and management.

This module provides LSP server definitions for various programming languages.
"""

import asyncio
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class LanguageServerID(str, Enum):
    """Language server identifiers."""
    # JavaScript/TypeScript
    TYPESCRIPT = "typescript"
    OXLINT = "oxlint"
    BIOME = "biome"

    # Python
    PYRIGHT = "pyright"
    TY = "ty"  # Experimental

    # Go
    GOPLS = "gopls"

    # Rust
    RUST_ANALYZER = "rust-analyzer"

    # Java
    JDTLS = "jdtls"

    # C#
    CSHARP = "csharp"

    # PHP
    INTEPHENSE = "intelephense"

    # Ruby
    RUBY_LSP = "ruby-lsp"

    # Vue
    VUE = "vue"

    # Svelte
    SVELTE = "svelte"


@dataclass
class LSPServerHandle:
    """Handle to a running LSP server process."""
    process: Any  # subprocess.Popen
    initialization: Optional[Dict[str, Any]] = None


@dataclass
class LSPServerInfo:
    """Information about an LSP server."""
    id: str
    name: str
    extensions: List[str]
    global_server: bool = False
    root_function: Optional[Callable[[str], str]] = None
    spawn_function: Optional[Callable[[str], LSPServerHandle]] = None
    command: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None


class LSPServerRegistry:
    """
    Registry for LSP server definitions.

    This class manages the definitions of all available language servers.
    """

    def __init__(self):
        """Initialize the registry with default servers."""
        self._servers: Dict[str, LSPServerInfo] = {}
        self._register_default_servers()

    def _register_default_servers(self):
        """Register default language server definitions."""

        # TypeScript/JavaScript
        self._servers[LanguageServerID.TYPESCRIPT.value] = LSPServerInfo(
            id="typescript",
            name="TypeScript Server",
            extensions=["ts", "tsx", "js", "jsx", "mjs", "cjs"],
            global_server=True,
            command=["tsserver", "--stdio"],
        )

        self._servers[LanguageServerID.BIOME.value] = LSPServerInfo(
            id="biome",
            name="Biome (JavaScript/TypeScript)",
            extensions=["js", "jsx", "ts", "tsx", "json", "jsonc"],
            command=["biome", "lsp-proxy", "stdio"],
        )

        # Python
        self._servers[LanguageServerID.PYRIGHT.value] = LSPServerInfo(
            id="pyright",
            name="Pyright (Python)",
            extensions=["py"],
            command=["pyright-langserver", "--stdio"],
        )

        # Go
        self._servers[LanguageServerID.GOPLS.value] = LSPServerInfo(
            id="gopls",
            name="Go Language Server",
            extensions=["go"],
            command=["gopls"],
        )

        # Rust
        self._servers[LanguageServerID.RUST_ANALYZER.value] = LSPServerInfo(
            id="rust-analyzer",
            name="Rust Analyzer",
            extensions=["rs"],
            command=["rust-analyzer"],
        )

    def register(self, server: LSPServerInfo):
        """
        Register a language server.

        Args:
            server: Server information
        """
        self._servers[server.id] = server

    def get(self, server_id: str) -> Optional[LSPServerInfo]:
        """
        Get a server by ID.

        Args:
            server_id: Server identifier

        Returns:
            Server info if found, None otherwise
        """
        return self._servers.get(server_id)

    def list(self) -> List[LSPServerInfo]:
        """
        List all registered servers.

        Returns:
            List of server information
        """
        return list(self._servers.values())

    def get_for_extension(self, extension: str) -> List[LSPServerInfo]:
        """
        Get servers that support a file extension.

        Args:
            extension: File extension (e.g., "py", "ts")

        Returns:
            List of matching servers
        """
        return [
            server for server in self._servers.values()
            if extension in server.extensions
        ]

    def get_for_file(self, filepath: str) -> List[LSPServerInfo]:
        """
        Get servers that support a file.

        Args:
            filepath: Path to file

        Returns:
            List of matching servers
        """
        ext = Path(filepath).suffix.lstrip('.')
        return self.get_for_extension(ext)

    def remove(self, server_id: str) -> bool:
        """
        Remove a server from the registry.

        Args:
            server_id: Server identifier

        Returns:
            True if removed, False if not found
        """
        if server_id in self._servers:
            del self._servers[server_id]
            return True
        return False


# Global registry instance
_global_registry = LSPServerRegistry()


def get_global_registry() -> LSPServerRegistry:
    """
    Get the global LSP server registry.

    Returns:
        Global LSPServerRegistry instance
    """
    return _global_registry


def register_server(server: LSPServerInfo):
    """
    Register a server in the global registry.

    Args:
        server: Server information
    """
    _global_registry.register(server)


def get_server(server_id: str) -> Optional[LSPServerInfo]:
    """
    Get a server from the global registry.

    Args:
        server_id: Server identifier

    Returns:
        Server info if found
    """
    return _global_registry.get(server_id)


def list_servers() -> List[LSPServerInfo]:
    """
    List all servers in the global registry.

    Returns:
        List of server information
    """
    return _global_registry.list()
