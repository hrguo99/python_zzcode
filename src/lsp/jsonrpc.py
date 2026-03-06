"""
JSON-RPC 2.0 implementation for LSP communication.

This module provides JSON-RPC 2.0 protocol support for communicating
with Language Server Protocol servers.
"""

import asyncio
import json
import logging
import uuid
from typing import Any, Callable, Dict, Optional, Union
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class JSONRPCErrorCode(int, Enum):
    """JSON-RPC error codes."""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_ERROR_START = -32099
    SERVER_ERROR_END = -32000
    SERVER_NOT_INITIALIZED = -32002
    UNKNOWN_ERROR_CODE = -32001


@dataclass
class JSONRPCError:
    """JSON-RPC error object."""
    code: int
    message: str
    data: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "code": self.code,
            "message": self.message,
        }
        if self.data is not None:
            result["data"] = self.data
        return result


@dataclass
class JSONRPCRequest:
    """JSON-RPC request object."""
    method: str
    params: Optional[Any] = None
    id: Union[str, int, None] = None
    jsonrpc: str = "2.0"

    def __post_init__(self):
        """Generate ID if not provided."""
        if self.id is None:
            self.id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
            "id": self.id,
        }
        if self.params is not None:
            result["params"] = self.params
        return result


@dataclass
class JSONRPCNotification:
    """JSON-RPC notification object (no response expected)."""
    method: str
    params: Optional[Any] = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
        }
        if self.params is not None:
            result["params"] = self.params
        return result


@dataclass
class JSONRPCResponse:
    """JSON-RPC response object."""
    id: Union[str, int]
    result: Optional[Any] = None
    error: Optional[JSONRPCError] = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "jsonrpc": self.jsonrpc,
            "id": self.id,
        }
        if self.error is not None:
            result["error"] = self.error.to_dict()
        else:
            result["result"] = self.result
        return result


class JSONRPCMessage:
    """Factory for creating JSON-RPC messages."""

    @staticmethod
    def parse(data: str) -> Union[JSONRPCRequest, JSONRPCNotification, JSONRPCResponse]:
        """
        Parse a JSON-RPC message from a string.

        Args:
            data: JSON string

        Returns:
            Parsed message object

        Raises:
            ValueError: If the message is invalid
        """
        try:
            obj = json.loads(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

        if not isinstance(obj, dict):
            raise ValueError("JSON-RPC message must be an object")

        # Check jsonrpc version
        if obj.get("jsonrpc", "2.0") != "2.0":
            raise ValueError("Unsupported JSON-RPC version")

        # Response or Request
        if "id" in obj:
            if "method" in obj:
                # Request
                return JSONRPCRequest(
                    method=obj["method"],
                    params=obj.get("params"),
                    id=obj["id"],
                    jsonrpc=obj.get("jsonrpc", "2.0"),
                )
            else:
                # Response
                error_obj = obj.get("error")
                error = JSONRPCError(
                    code=error_obj["code"],
                    message=error_obj["message"],
                    data=error_obj.get("data"),
                ) if error_obj else None

                return JSONRPCResponse(
                    id=obj["id"],
                    result=obj.get("result"),
                    error=error,
                    jsonrpc=obj.get("jsonrpc", "2.0"),
                )
        else:
            # Notification
            if "method" not in obj:
                raise ValueError("Notification must have a method")

            return JSONRPCNotification(
                method=obj["method"],
                params=obj.get("params"),
                jsonrpc=obj.get("jsonrpc", "2.0"),
            )


class JSONRPCProtocol:
    """
    JSON-RPC 2.0 protocol handler.

    This class handles encoding and decoding of JSON-RPC messages
    using Content-Length headers for message framing.
    """

    CONTENT_LENGTH_HEADER = "Content-Length"
    CRLF = "\r\n"

    @staticmethod
    def encode_message(message: Union[JSONRPCRequest, JSONRPCNotification, JSONRPCResponse]) -> bytes:
        """
        Encode a JSON-RPC message with Content-Length header.

        Args:
            message: Message to encode

        Returns:
            Encoded message bytes
        """
        content = json.dumps(message.to_dict(), ensure_ascii=False)
        content_bytes = content.encode("utf-8")
        header = f"Content-Length: {len(content_bytes)}{JSONRPCProtocol.CRLF}{JSONRPCProtocol.CRLF}"
        return header.encode("utf-8") + content_bytes

    @staticmethod
    async def read_message(reader: asyncio.StreamReader) -> Optional[str]:
        """
        Read a JSON-RPC message from a stream.

        Args:
            reader: Stream reader

        Returns:
            Message content as string, or None if stream is closed

        Raises:
            ValueError: If message format is invalid
        """
        # Read headers
        headers = {}
        while True:
            line = await reader.readline()
            if not line:
                return None  # EOF

            line_str = line.decode("utf-8").strip()
            if not line_str:
                break  # Empty line indicates end of headers

            if ":" in line_str:
                key, value = line_str.split(":", 1)
                headers[key.strip()] = value.strip()

        # Check Content-Length
        content_length_str = headers.get(JSONRPCProtocol.CONTENT_LENGTH_HEADER)
        if not content_length_str:
            raise ValueError("Missing Content-Length header")

        try:
            content_length = int(content_length_str)
        except ValueError:
            raise ValueError(f"Invalid Content-Length: {content_length_str}")

        # Read content
        if content_length == 0:
            return ""

        content = await reader.readexactly(content_length)
        return content.decode("utf-8")


class JSONRPCClient:
    """
    JSON-RPC 2.0 client for communicating with LSP servers.

    This class manages the JSON-RPC connection and handles
    requests, responses, and notifications.
    """

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        Initialize the JSON-RPC client.

        Args:
            reader: Stream reader
            writer: Stream writer
        """
        self.reader = reader
        self.writer = writer
        self._pending_requests: Dict[Union[str, int], asyncio.Future] = {}
        self._notification_handlers: Dict[str, Callable] = {}
        self._request_handlers: Dict[str, Callable] = {}
        self._running = False
        self._response_task: Optional[asyncio.Task] = None

    def on_notification(self, method: str, handler: Callable):
        """
        Register a notification handler.

        Args:
            method: Notification method
            handler: Handler function
        """
        self._notification_handlers[method] = handler

    def on_request(self, method: str, handler: Callable):
        """
        Register a request handler (for server->client requests).

        Args:
            method: Request method
            handler: Handler function
        """
        self._request_handlers[method] = handler

    async def send_request(self, method: str, params: Optional[Any] = None, timeout: float = 30.0) -> Any:
        """
        Send a JSON-RPC request and wait for response.

        Args:
            method: Request method
            params: Request parameters
            timeout: Request timeout in seconds

        Returns:
            Response result

        Raises:
            asyncio.TimeoutError: If request times out
            ValueError: If response contains an error
        """
        request = JSONRPCRequest(method=method, params=params)
        message = JSONRPCProtocol.encode_message(request)

        # Create future for response
        future: asyncio.Future = asyncio.Future()
        self._pending_requests[request.id] = future

        try:
            # Send request
            self.writer.write(message)
            await self.writer.drain()

            # Wait for response
            return await asyncio.wait_for(future, timeout=timeout)

        except asyncio.TimeoutError:
            # Clean up on timeout
            self._pending_requests.pop(request.id, None)
            raise
        except Exception as e:
            # Clean up on error
            self._pending_requests.pop(request.id, None)
            raise

    async def send_notification(self, method: str, params: Optional[Any] = None):
        """
        Send a JSON-RPC notification (no response expected).

        Args:
            method: Notification method
            params: Notification parameters
        """
        notification = JSONRPCNotification(method=method, params=params)
        message = JSONRPCProtocol.encode_message(notification)

        self.writer.write(message)
        await self.writer.drain()

    async def start(self):
        """Start listening for messages."""
        if self._running:
            return

        self._running = True
        self._response_task = asyncio.create_task(self._message_loop())

        logger.debug("JSON-RPC client started")

    async def stop(self):
        """Stop listening for messages."""
        if not self._running:
            return

        self._running = False

        if self._response_task:
            self._response_task.cancel()
            try:
                await self._response_task
            except asyncio.CancelledError:
                pass

        # Cancel all pending requests
        for future in self._pending_requests.values():
            if not future.done():
                future.set_exception(ValueError("Connection closed"))

        self._pending_requests.clear()

        logger.debug("JSON-RPC client stopped")

    async def _message_loop(self):
        """Main message loop."""
        try:
            while self._running:
                try:
                    # Read message
                    data = await JSONRPCProtocol.read_message(self.reader)
                    if data is None:
                        logger.debug("Connection closed by server")
                        break

                    # Parse message
                    try:
                        message = JSONRPCMessage.parse(data)
                    except ValueError as e:
                        logger.error(f"Failed to parse message: {e}")
                        continue

                    # Handle message based on type
                    if isinstance(message, JSONRPCResponse):
                        await self._handle_response(message)
                    elif isinstance(message, JSONRPCNotification):
                        await self._handle_notification(message)
                    elif isinstance(message, JSONRPCRequest):
                        await self._handle_server_request(message)

                except Exception as e:
                    logger.error(f"Error in message loop: {e}", exc_info=True)
                    break

        finally:
            self._running = False

    async def _handle_response(self, response: JSONRPCResponse):
        """Handle a response message."""
        future = self._pending_requests.pop(response.id, None)
        if not future:
            logger.warning(f"Received response for unknown request ID: {response.id}")
            return

        if future.done():
            return

        if response.error:
            future.set_exception(ValueError(response.error.message))
        else:
            future.set_result(response.result)

    async def _handle_notification(self, notification: JSONRPCNotification):
        """Handle a notification message."""
        handler = self._notification_handlers.get(notification.method)
        if handler:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(notification.params)
                else:
                    handler(notification.params)
            except Exception as e:
                logger.error(f"Error in notification handler for {notification.method}: {e}", exc_info=True)
        else:
            logger.debug(f"No handler for notification: {notification.method}")

    async def _handle_server_request(self, request: JSONRPCRequest):
        """Handle a server-to-client request."""
        handler = self._request_handlers.get(request.method)
        result = None
        error = None

        if handler:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(request.params)
                else:
                    result = handler(request.params)
            except Exception as e:
                logger.error(f"Error in request handler for {request.method}: {e}", exc_info=True)
                error = JSONRPCError(
                    code=JSONRPCErrorCode.INTERNAL_ERROR,
                    message=str(e),
                )
        else:
            logger.warning(f"No handler for server request: {request.method}")
            error = JSONRPCError(
                code=JSONRPCErrorCode.METHOD_NOT_FOUND,
                message=f"Method not found: {request.method}",
            )

        # Send response
        response = JSONRPCResponse(id=request.id, result=result, error=error)
        message = JSONRPCProtocol.encode_message(response)
        self.writer.write(message)
        await self.writer.drain()

    async def close(self):
        """Close the connection."""
        await self.stop()

        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception as e:
            logger.error(f"Error closing connection: {e}")
