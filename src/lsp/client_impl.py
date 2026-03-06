"""
Complete LSP Client implementation with real protocol support.

This module provides a full-featured LSP client that communicates
with language servers using JSON-RPC protocol.
"""

import asyncio
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from urllib.parse import urlparse
from urllib.request import url2pathname

from .jsonrpc import JSONRPCClient
from .models import (
    LSPRange,
    LSPPosition,
    LSPSymbol,
    LSPDocumentSymbol,
    LSPDiagnostic,
    LSPHover,
    LSPLocation,
    LSPInitializeError,
    LSPError,
)
from .language import get_language_id
from .project_root import find_nearest_root

logger = logging.getLogger(__name__)

# Default timeout for LSP requests
DEFAULT_TIMEOUT = 30.0

# Debounce time for diagnostics (ms)
DIAGNOSTICS_DEBOUNCE_MS = 150


@dataclass
class LSPClientInfo:
    """Information about an LSP client connection."""
    server_id: str
    root: str
    process: subprocess.Popen
    rpc_client: JSONRPCClient

    # Track open files and their versions
    _open_files: Dict[str, int] = field(default_factory=dict)

    # Diagnostics cache
    diagnostics: Dict[str, List[LSPDiagnostic]] = field(default_factory=dict)

    # Diagnostic event callbacks
    _diagnostic_callbacks: List[Callable] = field(default_factory=list)

    def on_diagnostic(self, callback: Callable[[str, List[LSPDiagnostic]], None]):
        """Register a callback for diagnostic updates."""
        self._diagnostic_callbacks.append(callback)

    def _notify_diagnostics(self, filepath: str, diagnostics: List[LSPDiagnostic]):
        """Notify listeners of diagnostic updates."""
        for callback in self._diagnostic_callbacks:
            try:
                callback(filepath, diagnostics)
            except Exception as e:
                logger.error(f"Error in diagnostic callback: {e}", exc_info=True)

    async def open_file(self, filepath: str, content: Optional[str] = None):
        """
        Open a file in the LSP server.

        Args:
            filepath: Path to the file
            content: Optional file content (will read if not provided)
        """
        # Resolve to absolute path
        if not os.path.isabs(filepath):
            filepath = os.path.abspath(filepath)

        # Read content if not provided
        if content is None:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

        # Get language ID
        ext = Path(filepath).suffix
        language_id = get_language_id(ext)

        # Convert to URI
        uri = Path(filepath).as_uri()

        # Check if file is already open
        if filepath in self._open_files:
            version = self._open_files[filepath] + 1
            self._open_files[filepath] = version

            # Send didChange notification
            await self.rpc_client.send_notification(
                "textDocument/didChange",
                {
                    "textDocument": {
                        "uri": uri,
                        "version": version,
                    },
                    "contentChanges": [{"text": content}],
                }
            )
        else:
            version = 0
            self._open_files[filepath] = version
            self.diagnostics.pop(filepath, None)  # Clear old diagnostics

            # Send didOpen notification
            await self.rpc_client.send_notification(
                "textDocument/didOpen",
                {
                    "textDocument": {
                        "uri": uri,
                        "languageId": language_id,
                        "version": version,
                        "text": content,
                    }
                }
            )

        # Notify that file changed
        await self.rpc_client.send_notification(
            "workspace/didChangeWatchedFiles",
            {
                "changes": [
                    {
                        "uri": uri,
                        "type": 1 if filepath not in self._open_files else 2,  # Created or Changed
                    }
                ]
            }
        )

        logger.debug(f"Opened file in LSP: {filepath} (version {version})")

    async def wait_for_diagnostics(self, filepath: str, timeout: float = 3.0):
        """
        Wait for diagnostics for a file.

        Args:
            filepath: Path to the file
            timeout: Timeout in seconds
        """
        filepath = os.path.abspath(filepath)

        # Create event for waiting
        event = asyncio.Event()
        received_diagnostics = []

        def on_diagnostic(path: str, diagnostics: List[LSPDiagnostic]):
            if path == filepath:
                received_diagnostics.extend(diagnostics)
                event.set()

        # Register temporary callback
        self.on_diagnostic(on_diagnostic)

        try:
            # Wait with timeout
            await asyncio.wait_for(event.wait(), timeout=timeout)
            # Small debounce to allow follow-up diagnostics
            await asyncio.sleep(DIAGNOSTICS_DEBOUNCE_MS / 1000.0)
        except asyncio.TimeoutError:
            pass
        finally:
            # Remove callback
            if on_diagnostic in self._diagnostic_callbacks:
                self._diagnostic_callbacks.remove(on_diagnostic)

    async def request_definition(self, filepath: str, position: LSPPosition) -> List[LSPLocation]:
        """
        Request go-to-definition for a position.

        Args:
            filepath: Path to the file
            position: Position in the file

        Returns:
            List of locations
        """
        uri = Path(filepath).as_uri()

        try:
            result = await self.rpc_client.send_request(
                "textDocument/definition",
                {
                    "textDocument": {"uri": uri},
                    "position": {
                        "line": position.line,
                        "character": position.character,
                    },
                },
                timeout=DEFAULT_TIMEOUT,
            )

            # Parse result
            if result is None:
                return []

            if isinstance(result, list):
                return [_parse_location(loc) for loc in result if loc]
            else:
                # Single location
                return [_parse_location(result)]

        except Exception as e:
            logger.error(f"Definition request failed: {e}", exc_info=True)
            return []

    async def request_hover(self, filepath: str, position: LSPPosition) -> Optional[LSPHover]:
        """
        Request hover information for a position.

        Args:
            filepath: Path to the file
            position: Position in the file

        Returns:
            Hover result if available
        """
        uri = Path(filepath).as_uri()

        try:
            result = await self.rpc_client.send_request(
                "textDocument/hover",
                {
                    "textDocument": {"uri": uri},
                    "position": {
                        "line": position.line,
                        "character": position.character,
                    },
                },
                timeout=DEFAULT_TIMEOUT,
            )

            if not result:
                return None

            # Parse hover result
            contents = result.get("contents", "")
            range_data = result.get("range")

            hover_range = None
            if range_data:
                hover_range = LSPRange(
                    start=LSPPosition(
                        line=range_data["start"]["line"],
                        character=range_data["start"]["character"],
                    ),
                    end=LSPPosition(
                        line=range_data["end"]["line"],
                        character=range_data["end"]["character"],
                    ),
                )

            # Handle different content formats
            if isinstance(contents, str):
                content_str = contents
            elif isinstance(contents, list):
                # Marked string
                if len(contents) > 0:
                    if isinstance(contents[0], str):
                        content_str = contents[0]
                    else:
                        content_str = str(contents[0])
                else:
                    content_str = ""
            elif isinstance(contents, dict):
                # Marked string with language
                content_str = contents.get("value", str(contents))
            else:
                content_str = str(contents)

            return LSPHover(contents=content_str, range=hover_range)

        except Exception as e:
            logger.error(f"Hover request failed: {e}", exc_info=True)
            return None

    async def request_references(self, filepath: str, position: LSPPosition) -> List[LSPLocation]:
        """
        Request find-references for a position.

        Args:
            filepath: Path to the file
            position: Position in the file

        Returns:
            List of locations
        """
        uri = Path(filepath).as_uri()

        try:
            result = await self.rpc_client.send_request(
                "textDocument/references",
                {
                    "textDocument": {"uri": uri},
                    "position": {
                        "line": position.line,
                        "character": position.character,
                    },
                    "context": {"includeDeclaration": True},
                },
                timeout=DEFAULT_TIMEOUT,
            )

            if not result:
                return []

            return [_parse_location(loc) for loc in result if loc]

        except Exception as e:
            logger.error(f"References request failed: {e}", exc_info=True)
            return []

    async def request_implementation(self, filepath: str, position: LSPPosition) -> List[LSPLocation]:
        """
        Request go-to-implementation for a position.

        Args:
            filepath: Path to the file
            position: Position in the file

        Returns:
            List of locations
        """
        uri = Path(filepath).as_uri()

        try:
            result = await self.rpc_client.send_request(
                "textDocument/implementation",
                {
                    "textDocument": {"uri": uri},
                    "position": {
                        "line": position.line,
                        "character": position.character,
                    },
                },
                timeout=DEFAULT_TIMEOUT,
            )

            if not result:
                return []

            if isinstance(result, list):
                return [_parse_location(loc) for loc in result if loc]
            else:
                return [_parse_location(result)]

        except Exception as e:
            logger.error(f"Implementation request failed: {e}", exc_info=True)
            return []

    async def request_document_symbols(self, filepath: str) -> List[LSPDocumentSymbol]:
        """
        Request document symbols for a file.

        Args:
            filepath: Path to the file

        Returns:
            List of document symbols
        """
        uri = Path(filepath).as_uri()

        try:
            result = await self.rpc_client.send_request(
                "textDocument/documentSymbol",
                {
                    "textDocument": {"uri": uri},
                },
                timeout=DEFAULT_TIMEOUT,
            )

            if not result:
                return []

            # Parse result (can be hierarchical or flat)
            symbols = []
            for item in result:
                if "range" in item and "selectionRange" in item:
                    # DocumentSymbol (hierarchical)
                    symbols.append(_parse_document_symbol(item))
                elif "location" in item:
                    # SymbolInformation (flat)
                    symbols.append(_parse_symbol_info(item))

            return symbols

        except Exception as e:
            logger.error(f"Document symbols request failed: {e}", exc_info=True)
            return []

    async def request_workspace_symbols(self, query: str) -> List[LSPSymbol]:
        """
        Request workspace symbols.

        Args:
            query: Search query

        Returns:
            List of matching symbols
        """
        try:
            result = await self.rpc_client.send_request(
                "workspace/symbol",
                {"query": query},
                timeout=DEFAULT_TIMEOUT,
            )

            if not result:
                return []

            # Filter and limit results
            kinds = [
                5,  # Class
                12,  # Function
                6,  # Method
                11,  # Interface
                13,  # Variable
                14,  # Constant
                23,  # Struct
                10,  # Enum
            ]

            filtered = [s for s in result if s.get("kind") in kinds]
            return [_parse_symbol_info(s) for s in filtered[:10]]

        except Exception as e:
            logger.error(f"Workspace symbols request failed: {e}", exc_info=True)
            return []

    async def prepare_call_hierarchy(self, filepath: str, position: LSPPosition) -> List[Dict[str, Any]]:
        """
        Prepare call hierarchy for a position.

        Args:
            filepath: Path to the file
            position: Position in the file

        Returns:
            List of call hierarchy items
        """
        uri = Path(filepath).as_uri()

        try:
            result = await self.rpc_client.send_request(
                "textDocument/prepareCallHierarchy",
                {
                    "textDocument": {"uri": uri},
                    "position": {
                        "line": position.line,
                        "character": position.character,
                    },
                },
                timeout=DEFAULT_TIMEOUT,
            )

            if not result:
                return []

            if isinstance(result, list):
                return result
            else:
                return [result]

        except Exception as e:
            logger.error(f"Prepare call hierarchy failed: {e}", exc_info=True)
            return []

    async def incoming_calls(self, filepath: str, position: LSPPosition) -> List[Dict[str, Any]]:
        """
        Get incoming calls for a position.

        Args:
            filepath: Path to the file
            position: Position in the file

        Returns:
            List of call hierarchy items
        """
        items = await self.prepare_call_hierarchy(filepath, position)
        if not items:
            return []

        try:
            result = await self.rpc_client.send_request(
                "callHierarchy/incomingCalls",
                {"item": items[0]},
                timeout=DEFAULT_TIMEOUT,
            )

            if not result:
                return []

            return result

        except Exception as e:
            logger.error(f"Incoming calls request failed: {e}", exc_info=True)
            return []

    async def outgoing_calls(self, filepath: str, position: LSPPosition) -> List[Dict[str, Any]]:
        """
        Get outgoing calls for a position.

        Args:
            filepath: Path to the file
            position: Position in the file

        Returns:
            List of call hierarchy items
        """
        items = await self.prepare_call_hierarchy(filepath, position)
        if not items:
            return []

        try:
            result = await self.rpc_client.send_request(
                "callHierarchy/outgoingCalls",
                {"item": items[0]},
                timeout=DEFAULT_TIMEOUT,
            )

            if not result:
                return []

            return result

        except Exception as e:
            logger.error(f"Outgoing calls request failed: {e}", exc_info=True)
            return []

    async def request_code_actions(
        self,
        filepath: str,
        range: "LSPRange",
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Request code actions for a range.

        This is used for auto-fix functionality to get available
        quick fixes and refactorings.

        Args:
            filepath: Path to the file
            range: Range to request actions for
            context: Additional context (diagnostics, etc.)

        Returns:
            List of code actions
        """
        uri = Path(filepath).as_uri()

        params = {
            "textDocument": {"uri": uri},
            "range": {
                "start": {
                    "line": range.start.line,
                    "character": range.start.character,
                },
                "end": {
                    "line": range.end.line,
                    "character": range.end.character,
                },
            },
        }

        if context:
            params["context"] = context

        try:
            result = await self.rpc_client.send_request(
                "textDocument/codeAction",
                params,
                timeout=DEFAULT_TIMEOUT,
            )

            if result is None:
                return []

            # Handle both array and Command[] | CodeAction[] formats
            if isinstance(result, list):
                return result

            return []

        except Exception as e:
            logger.error(f"Code action request failed: {e}")
            return []

    async def apply_edit(self, edit: Dict[str, Any]) -> bool:
        """
        Apply a workspace edit.

        This is used for auto-fix functionality to apply code actions.

        Args:
            edit: Workspace edit to apply

        Returns:
            True if successful
        """
        try:
            result = await self.rpc_client.send_request(
                "workspace/applyEdit",
                {"edit": edit},
                timeout=DEFAULT_TIMEOUT,
            )

            return result.get("applied", False) if result else False

        except Exception as e:
            logger.error(f"Apply edit failed: {e}")
            return False

    async def shutdown(self):
        """Shutdown the LSP client and server process."""
        logger.info(f"Shutting down LSP client: {self.server_id}")

        try:
            # Send shutdown request
            await self.rpc_client.send_request("shutdown", {}, timeout=5.0)

            # Send exit notification
            await self.rpc_client.send_notification("exit")
        except:
            pass

        # Close RPC connection
        await self.rpc_client.close()

        # Terminate process
        try:
            self.process.terminate()
            self.process.wait(timeout=5)
        except:
            try:
                self.process.kill()
            except:
                pass


def _parse_location(loc: Dict[str, Any]) -> LSPLocation:
    """Parse a location from LSP response."""
    uri = loc["uri"]
    range_data = loc["range"]

    return LSPLocation(
        uri=uri,
        range=LSPRange(
            start=LSPPosition(
                line=range_data["start"]["line"],
                character=range_data["start"]["character"],
            ),
            end=LSPPosition(
                line=range_data["end"]["line"],
                character=range_data["end"]["character"],
            ),
        ),
    )


def _parse_document_symbol(item: Dict[str, Any]) -> LSPDocumentSymbol:
    """Parse a document symbol from LSP response."""
    range_data = item["range"]
    selection_range_data = item["selectionRange"]

    children = []
    if "children" in item:
        children = [_parse_document_symbol(child) for child in item["children"]]

    return LSPDocumentSymbol(
        name=item["name"],
        kind=item["kind"],
        range=LSPRange(
            start=LSPPosition(
                line=range_data["start"]["line"],
                character=range_data["start"]["character"],
            ),
            end=LSPPosition(
                line=range_data["end"]["line"],
                character=range_data["end"]["character"],
            ),
        ),
        selection_range=LSPRange(
            start=LSPPosition(
                line=selection_range_data["start"]["line"],
                character=selection_range_data["start"]["character"],
            ),
            end=LSPPosition(
                line=selection_range_data["end"]["line"],
                character=selection_range_data["end"]["character"],
            ),
        ),
        detail=item.get("detail"),
        children=children,
    )


def _parse_symbol_info(item: Dict[str, Any]) -> LSPDocumentSymbol:
    """Parse symbol information to document symbol."""
    loc = _parse_location(item["location"])

    return LSPDocumentSymbol(
        name=item["name"],
        kind=item["kind"],
        range=loc.range,
        selection_range=loc.range,
        detail=item.get("containerName"),
    )


class LSPClient:
    """
    LSP Client for communicating with language servers.

    This is a full-featured implementation using JSON-RPC protocol.
    """

    def __init__(
        self,
        server_id: str,
        root: str,
        command: List[str],
        env: Optional[Dict[str, str]] = None,
        initialization_options: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize an LSP client.

        Args:
            server_id: Server identifier
            root: Root directory for the workspace
            command: Command to start the server
            env: Optional environment variables
            initialization_options: Optional initialization options
        """
        self.server_id = server_id
        self.root = root
        self.command = command
        self.env = env or {}
        self.initialization_options = initialization_options or {}
        self._info: Optional[LSPClientInfo] = None

    async def start(self) -> LSPClientInfo:
        """
        Start the LSP server and initialize the client.

        Returns:
            Client information

        Raises:
            LSPInitializeError: If initialization fails
        """
        logger.info(f"Starting LSP server: {self.server_id}")

        try:
            # Start the server process
            full_env = {**os.environ.copy(), **self.env}
            process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.root,
                env=full_env,
            )

            # Create JSON-RPC client
            reader = asyncio.StreamReader()
            reader_protocol = asyncio.StreamReaderProtocol(reader)
            transport, _ = await asyncio.get_event_loop().connect_read_pipe(
                lambda: reader_protocol,
                process.stdout,
            )

            writer_transport, writer_protocol = await asyncio.get_event_loop().connect_write_pipe(
                asyncio.Protocol,
                process.stdin,
            )
            writer = asyncio.StreamWriter(
                writer_transport,
                writer_protocol,
                None,
                asyncio.get_event_loop(),
            )

            rpc_client = JSONRPCClient(reader, writer)

            # Set up notification handler for diagnostics
            def on_publish_diagnostics(params):
                uri = params["uri"]
                diagnostics_data = params.get("diagnostics", [])

                # Convert URI to filepath
                parsed = urlparse(uri)
                if parsed.scheme == "file":
                    filepath = url2pathname(parsed.path)
                else:
                    filepath = uri

                # Parse diagnostics
                diagnostics = []
                for diag in diagnostics_data:
                    range_data = diag["range"]
                    lsp_range = LSPRange(
                        start=LSPPosition(
                            line=range_data["start"]["line"],
                            character=range_data["start"]["character"],
                        ),
                        end=LSPPosition(
                            line=range_data["end"]["line"],
                            character=range_data["end"]["character"],
                        ),
                    )

                    diagnostics.append(
                        LSPDiagnostic(
                            range=lsp_range,
                            severity=diag.get("severity"),
                            code=diag.get("code"),
                            source=diag.get("source"),
                            message=diag.get("message", ""),
                        )
                    )

                # Cache diagnostics
                self._info.diagnostics[filepath] = diagnostics

                # Notify listeners
                self._info._notify_diagnostics(filepath, diagnostics)

                logger.debug(f"Received {len(diagnostics)} diagnostics for {filepath}")

            rpc_client.on_notification("textDocument/publishDiagnostics", on_publish_diagnostics)

            # Set up request handlers
            async def handle_workspace_configuration(params):
                # Return initialization options
                return [self.initialization_options]

            rpc_client.on_request("workspace/configuration", handle_workspace_configuration)

            async def handle_workspace_folders():
                return [
                    {
                        "name": "workspace",
                        "uri": Path(self.root).as_uri(),
                    }
                ]

            rpc_client.on_request("workspace/workspaceFolders", handle_workspace_folders)

            async def handle_register_capability(_params):
                return None

            rpc_client.on_request("client/registerCapability", handle_register_capability)

            async def handle_unregister_capability(_params):
                return None

            rpc_client.on_request("client/unregisterCapability", handle_unregister_capability)

            async def handle_work_done_progress(_params):
                return None

            rpc_client.on_request("window/workDoneProgress/create", handle_work_done_progress)

            # Start RPC client
            await rpc_client.start()

            # Send initialize request
            root_uri = Path(self.root).as_uri()

            await rpc_client.send_request(
                "initialize",
                {
                    "rootUri": root_uri,
                    "processId": process.pid,
                    "workspaceFolders": [
                        {
                            "name": "workspace",
                            "uri": root_uri,
                        }
                    ],
                    "initializationOptions": self.initialization_options,
                    "capabilities": {
                        "window": {
                            "workDoneProgress": True,
                        },
                        "workspace": {
                            "configuration": True,
                            "didChangeWatchedFiles": {
                                "dynamicRegistration": True,
                            },
                        },
                        "textDocument": {
                            "synchronization": {
                                "didOpen": True,
                                "didChange": True,
                            },
                            "publishDiagnostics": {
                                "versionSupport": True,
                            },
                        },
                    },
                },
                timeout=45.0,
            )

            # Send initialized notification
            await rpc_client.send_notification("initialized", {})

            # Send didChangeConfiguration notification if needed
            if self.initialization_options:
                await rpc_client.send_notification(
                    "workspace/didChangeConfiguration",
                    {
                        "settings": self.initialization_options,
                    }
                )

            # Create client info
            self._info = LSPClientInfo(
                server_id=self.server_id,
                root=self.root,
                process=process,
                rpc_client=rpc_client,
            )

            logger.info(f"LSP server started: {self.server_id} (PID: {process.pid})")

            return self._info

        except Exception as e:
            logger.error(f"Failed to start LSP server: {e}", exc_info=True)
            raise LSPInitializeError(
                f"Failed to initialize LSP server {self.server_id}: {e}",
                server_id=self.server_id,
            )

    async def open_file(self, filepath: str):
        """
        Open a file in the LSP server.

        Args:
            filepath: Path to the file
        """
        if not self._info:
            raise RuntimeError("LSP client not started")

        await self._info.open_file(filepath)

    def get_info(self) -> Optional[LSPClientInfo]:
        """
        Get the client information.

        Returns:
            Client info if started, None otherwise
        """
        return self._info

    async def shutdown(self):
        """Shutdown the LSP client."""
        if self._info:
            await self._info.shutdown()
            self._info = None


def create_client(
    server_id: str,
    root: str,
    command: List[str],
    env: Optional[Dict[str, str]] = None,
    initialization_options: Optional[Dict[str, Any]] = None,
) -> LSPClient:
    """
    Create an LSP client.

    Convenience function for creating an LSP client.

    Args:
        server_id: Server identifier
        root: Root directory
        command: Command to start server
        env: Optional environment variables
        initialization_options: Optional initialization options

    Returns:
        LSPClient instance
    """
    return LSPClient(server_id, root, command, env, initialization_options)
