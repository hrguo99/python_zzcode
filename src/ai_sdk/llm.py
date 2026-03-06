"""
LLM abstraction layer for AI SDK.

This module provides a unified interface for text generation across multiple providers.
Inspired by OpenCode's LLM abstraction.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Optional, TYPE_CHECKING
from dataclasses import dataclass, field
import asyncio

from .message import Message, Role, to_model_messages, ModelMessage
from .tool import Tool, ToolRegistry, ToolCall, create_tool_call
from .provider import ProviderManager
from .providers import BaseProvider, StreamChunk

if TYPE_CHECKING:
    from .tracker import InteractionTracker


@dataclass
class StreamOptions:
    """Options for streaming generation."""
    temperature: float = 0.7
    max_tokens: int = 1024
    tool_choice: Optional[str] = None
    include_usage: bool = True


@dataclass
class StreamInput:
    """Input for stream generation."""
    messages: list[Message]
    model: str
    provider: str
    system: list[str] = field(default_factory=list)
    tools: dict[str, Tool] = field(default_factory=dict)
    temperature: float = 0.7
    max_tokens: int = 1024
    tool_choice: Optional[str] = None
    session_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamResult:
    """Result of streaming generation."""
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    reasoning: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class LLM:
    """
    High-level LLM interface for unified text generation.

    This class provides a simple, unified API for interacting with multiple AI providers.
    It handles message formatting, tool calling, streaming, and interaction tracking.

    Example:
        ```python
        llm = LLM(provider="openai", model="gpt-4")

        # Simple text generation
        response = await llm.stream(
            messages=[Message.user("Hello, how are you?")]
        )

        async for chunk in response:
            if chunk.text:
                print(chunk.text, end="")

        # With tool calling
        tools = {
            "get_weather": Tool(...)
        }
        response = await llm.stream(
            messages=[Message.user("What's the weather?")],
            tools=tools
        )
        ```
    """

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        provider_manager: ProviderManager | None = None,
        tracker: InteractionTracker | None = None,
        _provider: BaseProvider | None = None,
    ):
        """
        Initialize LLM instance.

        Args:
            provider: Provider ID (e.g., "openai", "anthropic", "custom")
            model: Model ID (e.g., "gpt-4", "claude-3-5-sonnet-20241022")
            provider_manager: Optional custom provider manager
            tracker: Optional interaction tracker
            _provider: Internal use only - pre-configured provider instance
        """
        self.provider_manager = provider_manager or ProviderManager()
        self.tracker = tracker

        # If a custom provider instance is provided, use it directly
        if _provider:
            self.provider = _provider
            self.provider_id = _provider.provider_id
            self.model_id = model or "default"
        else:
            # Set provider
            if provider is None:
                provider = self.provider_manager.get_default_provider()
            self.provider_id = provider

            # Set model
            if model is None:
                model = self.provider_manager.get_default_model(provider)
            self.model_id = model

            # Get provider
            self.provider = self.provider_manager.get_provider(provider)
            if not self.provider:
                raise ValueError(f"Provider '{provider}' not found or not configured")

        # Validate configuration
        errors = self.provider.validate_config()
        if errors:
            raise ValueError(f"Provider configuration error: {', '.join(errors)}")

    async def stream(
        self,
        messages: list[Message],
        tools: dict[str, Tool] | None = None,
        system: list[str] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tool_choice: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream text generation.

        Args:
            messages: Conversation messages
            tools: Optional tool registry for function calling
            system: Optional system prompts
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            tool_choice: Tool choice strategy ("auto", "required", "none")
            session_id: Optional session ID for tracking
            metadata: Optional additional metadata

        Yields:
            StreamChunk objects with partial results
        """
        # Prepare system messages
        system_messages = []
        if system:
            for sys_prompt in system:
                system_messages.append(Message.system(sys_prompt))

        # Combine all messages
        all_messages = system_messages + messages

        # Convert to provider format
        model_messages = to_model_messages(
            all_messages,
            provider_capabilities=self._get_capabilities()
        )

        # Prepare tools
        tools_list = None
        if tools:
            # Initialize all tools first
            for tool in tools.values():
                if hasattr(tool, '_ensure_initialized'):
                    await tool._ensure_initialized()

            tools_list = [
                tool.to_dict()
                for tool in tools.values()
                if tool.allowed
            ]

        # Set max_tokens from model limits if not specified
        if max_tokens is None:
            max_tokens = self.provider.get_max_tokens(self.model_id)

        # Track interaction if tracker is enabled
        if self.tracker:
            await self.tracker.track_start(
                session_id=session_id,
                provider_id=self.provider_id,
                model_id=self.model_id,
                messages=[msg.to_dict() for msg in all_messages],
                tools=list(tools.keys()) if tools else [],
                temperature=temperature,
            )

        try:
            # Stream from provider
            full_text = ""
            accumulated_tool_calls = {}
            finish_reason = None
            usage = None

            async for chunk in self.provider.stream_generate(
                model=self.model_id,
                messages=[msg.to_dict() for msg in model_messages],
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools_list,
                tool_choice=tool_choice,
            ):
                # Accumulate text
                if chunk.text:
                    full_text += chunk.text

                # Accumulate tool calls
                if chunk.tool_calls:
                    for tool_call_data in chunk.tool_calls:
                        index = tool_call_data.get("index", 0)
                        if index not in accumulated_tool_calls:
                            accumulated_tool_calls[index] = {
                                "id": tool_call_data.get("id", ""),
                                "name": tool_call_data.get("function", {}).get("name", ""),
                                "arguments": tool_call_data.get("function", {}).get("arguments", ""),
                            }
                        else:
                            # Append arguments
                            accumulated_tool_calls[index]["arguments"] += tool_call_data.get(
                                "function", {}
                            ).get("arguments", "")

                # Capture finish reason and usage
                if chunk.finish_reason:
                    finish_reason = chunk.finish_reason
                if chunk.usage:
                    usage = chunk.usage

                yield chunk

            # Track completion if tracker is enabled
            if self.tracker:
                # Parse tool calls
                tool_calls_list = []
                for tool_call_data in accumulated_tool_calls.values():
                    import json
                    args = tool_call_data["arguments"]
                    if args:
                        try:
                            arguments = json.loads(args)
                        except json.JSONDecodeError:
                            arguments = {}

                        tool_calls_list.append({
                            "id": tool_call_data["id"],
                            "name": tool_call_data["name"],
                            "arguments": arguments,
                        })

                await self.tracker.track_complete(
                    text=full_text,
                    tool_calls=tool_calls_list,
                    finish_reason=finish_reason or "stop",
                    usage=usage,
                )

        except Exception as e:
            if self.tracker:
                await self.tracker.track_error(error=str(e))
            raise

    async def generate(
        self,
        messages: list[Message],
        tools: dict[str, Tool] | None = None,
        system: list[str] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        tool_choice: str | None = None,
        session_id: str | None = None,
    ) -> StreamResult:
        """
        Generate text (non-streaming).

        Args:
            messages: Conversation messages
            tools: Optional tool registry for function calling
            system: Optional system prompts
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            tool_choice: Tool choice strategy
            session_id: Optional session ID for tracking

        Returns:
            StreamResult with complete response
        """
        # Prepare system messages
        system_messages = []
        if system:
            for sys_prompt in system:
                system_messages.append(Message.system(sys_prompt))

        # Combine all messages
        all_messages = system_messages + messages

        # Convert to provider format
        model_messages = to_model_messages(
            all_messages,
            provider_capabilities=self._get_capabilities()
        )

        # Prepare tools
        tools_list = None
        if tools:
            # Initialize all tools first
            for tool in tools.values():
                if hasattr(tool, '_ensure_initialized'):
                    await tool._ensure_initialized()

            tools_list = [
                tool.to_dict()
                for tool in tools.values()
                if tool.allowed
            ]

        # Set max_tokens from model limits if not specified
        if max_tokens is None:
            max_tokens = self.provider.get_max_tokens(self.model_id)

        # Track interaction if tracker is enabled
        if self.tracker:
            await self.tracker.track_start(
                session_id=session_id,
                provider_id=self.provider_id,
                model_id=self.model_id,
                messages=[msg.to_dict() for msg in all_messages],
                tools=list(tools.keys()) if tools else [],
                temperature=temperature,
            )

        try:
            # Generate from provider
            response = await self.provider.generate(
                model=self.model_id,
                messages=[msg.to_dict() for msg in model_messages],
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools_list,
                tool_choice=tool_choice,
            )

            # Create tool call objects
            tool_calls = []
            if response.tool_calls:
                tool_registry = ToolRegistry()
                tool_registry._tools = tools or {}

                for tool_call_data in response.tool_calls:
                    tool_call = create_tool_call(tool_call_data, tool_registry)
                    tool_calls.append(tool_call)

            result = StreamResult(
                text=response.text,
                tool_calls=tool_calls,
                finish_reason=response.finish_reason,
                usage=response.usage,
            )

            # Track completion
            if self.tracker:
                await self.tracker.track_complete(
                    text=response.text,
                    tool_calls=[
                        {
                            "id": tc.id,
                            "name": tc.name,
                            "arguments": tc.input,
                        }
                        for tc in tool_calls
                    ],
                    finish_reason=response.finish_reason,
                    usage=response.usage,
                )

            return result

        except Exception as e:
            if self.tracker:
                await self.tracker.track_error(error=str(e))
            raise

    def _get_capabilities(self) -> dict:
        """Get provider capabilities for message conversion."""
        model = self.provider.get_model(self.model_id)
        if not model:
            return {}

        return {
            "supports_files": model.capabilities.supports_images,
            "supports_images": model.capabilities.supports_images,
            "supports_audio": model.capabilities.supports_audio,
        }

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
    ) -> float:
        """
        Estimate cost for a request.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cache_read_tokens: Number of cached tokens read
            cache_write_tokens: Number of cached tokens written

        Returns:
            Estimated cost in USD
        """
        return self.provider.estimate_cost(
            self.model_id,
            input_tokens,
            output_tokens,
            cache_read_tokens,
            cache_write_tokens,
        )
