"""
LSP Manager and main interface.

This module provides the main LSP interface for managing LSP clients and
providing language intelligence features.
"""

import asyncio
import os
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any

from .models import (
    LSPRange,
    LSPPosition,
    LSPSymbol,
    LSPDocumentSymbol,
    LSPHover,
    LSPLocation,
)
from .client_impl import LSPClient, create_client, LSPClientInfo
from .servers import LSPServerInfo, get_global_registry

logger = logging.getLogger(__name__)


class LSPManager:
    """
    Main LSP management class.

    This class handles LSP client lifecycle and provides language intelligence features.
    """

    def __init__(self, project_dir: str = "."):
        """
        Initialize the LSP manager.

        Args:
            project_dir: Project root directory
        """
        self.project_dir = os.path.abspath(project_dir)
        self._clients: Dict[str, LSPClient] = {}
        self._client_infos: Dict[str, LSPClientInfo] = {}
        self._registry = get_global_registry(project_dir)
        self._broken: set = set()
        self._spawning: Dict[str, asyncio.Task] = {}

    async def get_client_for_file(self, filepath: str) -> Optional[LSPClient]:
        """
        Get or create an LSP client for a file.

        Args:
            filepath: Path to the file

        Returns:
            LSPClient if available and started, None otherwise
        """
        # Find servers that support this file type
        servers = self._registry.get_for_file(filepath)

        if not servers:
            logger.debug(f"No LSP server for file: {filepath}")
            return None

        # Try each server
        for server_info in servers:
            # Find root for this server
            root = self.project_dir
            if server_info.root_function:
                root = server_info.root_function(filepath)
                if not root:
                    continue

            # Check if broken
            key = f"{root}_{server_info.id}"
            if key in self._broken:
                continue

            # Check if already spawned
            if key in self._spawning:
                try:
                    client = await self._spawning[key]
                    if client:
                        return client
                except Exception as e:
                    logger.error(f"Failed to get spawning client: {e}")
                    self._spawning.pop(key, None)
                    self._broken.add(key)
                    continue

            # Check if client already exists
            if server_info.id in self._clients:
                return self._clients[server_info.id]

            # Spawn new client
            async def spawn_client():
                if not server_info.spawn_command:
                    return None

                handle = await server_info.spawn_command(root)
                if not handle:
                    self._broken.add(key)
                    return None

                # Create client
                client = create_client(
                    server_id=server_info.id,
                    root=root,
                    command=handle.command,
                    env=handle.env,
                    initialization_options=handle.initialization_options,
                )

                try:
                    info = await client.start()
                    self._clients[server_info.id] = client
                    self._client_infos[server_info.id] = info
                    logger.info(f"Spawned LSP server: {server_info.id}")
                    return client

                except Exception as e:
                    logger.error(f"Failed to start LSP client {server_info.id}: {e}")
                    self._broken.add(key)
                    return None

            # Create spawn task
            task = asyncio.create_task(spawn_client())
            self._spawning[key] = task

            try:
                client = await task
                if client:
                    return client
            except Exception as e:
                logger.error(f"Failed to spawn LSP client: {e}")
                self._broken.add(key)
            finally:
                self._spawning.pop(key, None)

        return None

    async def has_clients(self, filepath: str) -> bool:
        """
        Check if any LSP clients are available for a file.

        Args:
            filepath: Path to the file

        Returns:
            True if LSP is available
        """
        servers = self._registry.get_for_file(filepath)
        if not servers:
            return False

        for server_info in servers:
            key = f"{self.project_dir}_{server_info.id}"
            if key in self._broken:
                continue
            return True

        return False

    async def touch_file(self, filepath: str, wait_for_diagnostics: bool = False):
        """
        Touch a file to trigger LSP analysis.

        Args:
            filepath: Path to the file
            wait_for_diagnostics: Whether to wait for diagnostics
        """
        client = await self.get_client_for_file(filepath)

        if client:
            await client.open_file(filepath)

            if wait_for_diagnostics:
                info = client.get_info()
                if info:
                    await info.wait_for_diagnostics(filepath)

    async def get_diagnostics(self) -> Dict[str, List[Any]]:
        """
        Get diagnostics from all active clients.

        Returns:
            Dictionary mapping file paths to diagnostic lists
        """
        diagnostics = {}

        for info in self._client_infos.values():
            for filepath, diags in info.diagnostics.items():
                if filepath not in diagnostics:
                    diagnostics[filepath] = []
                diagnostics[filepath].extend(diags)

        return diagnostics

    async def shutdown_all(self):
        """Shutdown all LSP clients."""
        logger.info(f"Shutting down {len(self._clients)} LSP client(s)")

        for client in self._clients.values():
            try:
                await client.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down LSP client: {e}")

        self._clients.clear()
        self._client_infos.clear()

    def get_status(self) -> List[Dict[str, Any]]:
        """
        Get status of all LSP clients.

        Returns:
            List of status dictionaries
        """
        status_list = []

        for server_id, info in self._client_infos.items():
            server_info = self._registry.get(server_id)
            status_list.append({
                "id": server_id,
                "name": server_info.name if server_info else server_id,
                "root": os.path.relpath(info.root, self.project_dir),
                "status": "connected",
            })

        return status_list


class LSP:
    """
    Main LSP interface class.

    This provides static methods for LSP operations, similar to the TypeScript implementation.
    """

    _manager: Optional[LSPManager] = None

    @classmethod
    def get_manager(cls, project_dir: str = ".") -> LSPManager:
        """
        Get or create the LSP manager.

        Args:
            project_dir: Project directory

        Returns:
            LSPManager instance
        """
        if cls._manager is None:
            cls._manager = LSPManager(project_dir)
        return cls._manager

    @classmethod
    async def init(cls):
        """Initialize the LSP system."""
        logger.info("Initializing LSP system")
        return cls.get_manager()

    @classmethod
    async def touchFile(cls, filepath: str, wait: bool = False):
        """
        Touch a file to trigger LSP analysis.

        Args:
            filepath: Path to the file
            wait: Whether to wait for diagnostics
        """
        manager = cls.get_manager()
        await manager.touch_file(filepath, wait_for_diagnostics=wait)

    @classmethod
    async def diagnostics(cls) -> Dict[str, List[Any]]:
        """
        Get diagnostics from all active clients.

        Returns:
            Dictionary mapping file paths to diagnostic lists
        """
        manager = cls.get_manager()
        return await manager.get_diagnostics()

    @classmethod
    async def definition(cls, position: Dict[str, Any]) -> List[LSPLocation]:
        """
        Request go-to-definition for a position.

        Args:
            position: Position information (file, line, character)

        Returns:
            List of locations
        """
        manager = cls.get_manager()
        client = await manager.get_client_for_file(position["file"])

        if client:
            lsp_pos = LSPPosition(
                line=position.get("line", 0),
                character=position.get("character", 0),
            )
            return await client.request_definition(position["file"], lsp_pos)

        return []

    @classmethod
    async def hover(cls, position: Dict[str, Any]) -> Optional[LSPHover]:
        """
        Request hover information for a position.

        Args:
            position: Position information (file, line, character)

        Returns:
            Hover result if available
        """
        manager = cls.get_manager()
        client = await manager.get_client_for_file(position["file"])

        if client:
            lsp_pos = LSPPosition(
                line=position.get("line", 0),
                character=position.get("character", 0),
            )
            return await client.request_hover(position["file"], lsp_pos)

        return None

    @classmethod
    async def references(cls, position: Dict[str, Any]) -> List[LSPLocation]:
        """
        Request find-references for a position.

        Args:
            position: Position information (file, line, character)

        Returns:
            List of locations
        """
        manager = cls.get_manager()
        client = await manager.get_client_for_file(position["file"])

        if client:
            lsp_pos = LSPPosition(
                line=position.get("line", 0),
                character=position.get("character", 0),
            )
            return await client.request_references(position["file"], lsp_pos)

        return []

    @classmethod
    async def documentSymbol(cls, uri: str) -> List[LSPDocumentSymbol]:
        """
        Request document symbols for a file.

        Args:
            uri: File URI

        Returns:
            List of document symbols
        """
        # Convert URI to file path
        from urllib.parse import urlparse
        from urllib.request import url2pathname

        parsed = urlparse(uri)
        if parsed.scheme == "file":
            filepath = url2pathname(parsed.path)
        else:
            filepath = uri

        manager = cls.get_manager()
        client = await manager.get_client_for_file(filepath)

        if client:
            return await client.request_document_symbols(filepath)

        return []

    @classmethod
    async def workspaceSymbol(cls, query: str) -> List[LSPSymbol]:
        """
        Request workspace symbols.

        Args:
            query: Search query

        Returns:
            List of matching symbols
        """
        manager = cls.get_manager()
        results = []

        for client in manager._clients.values():
            info = client.get_info()
            if info:
                symbols = await info.request_workspace_symbols(query)
                results.extend(symbols)

        return results

    @classmethod
    async def implementation(cls, position: Dict[str, Any]) -> List[LSPLocation]:
        """
        Request go-to-implementation for a position.

        Args:
            position: Position information (file, line, character)

        Returns:
            List of locations
        """
        manager = cls.get_manager()
        client = await manager.get_client_for_file(position["file"])

        if client:
            info = client.get_info()
            if info:
                lsp_pos = LSPPosition(
                    line=position.get("line", 0),
                    character=position.get("character", 0),
                )
                return await info.request_implementation(position["file"], lsp_pos)

        return []

    @classmethod
    async def prepareCallHierarchy(cls, position: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Prepare call hierarchy for a position.

        Args:
            position: Position information (file, line, character)

        Returns:
            List of call hierarchy items
        """
        manager = cls.get_manager()
        client = await manager.get_client_for_file(position["file"])

        if client:
            info = client.get_info()
            if info:
                lsp_pos = LSPPosition(
                    line=position.get("line", 0),
                    character=position.get("character", 0),
                )
                return await info.prepare_call_hierarchy(position["file"], lsp_pos)

        return []

    @classmethod
    async def incomingCalls(cls, position: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get incoming calls for a position.

        Args:
            position: Position information (file, line, character)

        Returns:
            List of call hierarchy items
        """
        manager = cls.get_manager()
        client = await manager.get_client_for_file(position["file"])

        if client:
            info = client.get_info()
            if info:
                lsp_pos = LSPPosition(
                    line=position.get("line", 0),
                    character=position.get("character", 0),
                )
                return await info.incoming_calls(position["file"], lsp_pos)

        return []

    @classmethod
    async def outgoingCalls(cls, position: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get outgoing calls for a position.

        Args:
            position: Position information (file, line, character)

        Returns:
            List of call hierarchy items
        """
        manager = cls.get_manager()
        client = await manager.get_client_for_file(position["file"])

        if client:
            info = client.get_info()
            if info:
                lsp_pos = LSPPosition(
                    line=position.get("line", 0),
                    character=position.get("character", 0),
                )
                return await info.outgoing_calls(position["file"], lsp_pos)

        return []

    @classmethod
    async def hasClients(cls, filepath: str) -> bool:
        """
        Check if LSP clients are available for a file.

        Args:
            filepath: Path to the file

        Returns:
            True if LSP is available
        """
        manager = cls.get_manager()
        return await manager.has_clients(filepath)

    @classmethod
    async def status(cls) -> List[Dict[str, Any]]:
        """
        Get status of all LSP clients.

        Returns:
            List of status dictionaries
        """
        manager = cls.get_manager()
        return manager.get_status()
