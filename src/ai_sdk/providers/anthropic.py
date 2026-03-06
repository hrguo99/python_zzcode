"""
Anthropic provider implementation.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from .base import BaseProvider, Model, ModelCapabilities, ModelCost, ModelLimits, StreamChunk, StreamResponse


class AnthropicProvider(BaseProvider):
    """Anthropic provider (Claude 3 family)."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        super().__init__(api_key, base_url)

        try:
            import anthropic
            self._client = None
            self._anthropic = anthropic
        except ImportError:
            raise ImportError(
                "Anthropic package is required. Install with: pip install anthropic"
            )

    def _get_api_key_env(self) -> str:
        return "ANTHROPIC_API_KEY"

    @property
    def provider_id(self) -> str:
        return "anthropic"

    @property
    def provider_name(self) -> str:
        return "Anthropic"

    @property
    def available_models(self) -> dict[str, Model]:
        return {
            "claude-3-5-sonnet-20241022": Model(
                id="claude-3-5-sonnet-20241022",
                provider_id="anthropic",
                name="Claude 3.5 Sonnet",
                capabilities=ModelCapabilities(
                    temperature=True,
                    reasoning=True,
                    attachment=True,
                    toolcall=True,
                    streaming=True,
                    supports_images=True,
                    input_text=True,
                    input_image=True,
                    output_text=True,
                ),
                cost=ModelCost(
                    input_per_1m=3.00,
                    output_per_1m=15.00,
                    cache_read_per_1m=0.30,
                    cache_write_per_1m=3.75,
                ),
                limits=ModelLimits(
                    max_context=200000,
                    max_output=8192,
                ),
            ),
            "claude-3-5-haiku-20241022": Model(
                id="claude-3-5-haiku-20241022",
                provider_id="anthropic",
                name="Claude 3.5 Haiku",
                capabilities=ModelCapabilities(
                    temperature=True,
                    reasoning=False,
                    attachment=True,
                    toolcall=True,
                    streaming=True,
                    supports_images=True,
                    input_text=True,
                    input_image=True,
                    output_text=True,
                ),
                cost=ModelCost(
                    input_per_1m=0.80,
                    output_per_1m=4.00,
                    cache_read_per_1m=0.08,
                    cache_write_per_1m=1.00,
                ),
                limits=ModelLimits(
                    max_context=200000,
                    max_output=8192,
                ),
            ),
            "claude-3-opus-20240229": Model(
                id="claude-3-opus-20240229",
                provider_id="anthropic",
                name="Claude 3 Opus",
                capabilities=ModelCapabilities(
                    temperature=True,
                    reasoning=True,
                    attachment=True,
                    toolcall=True,
                    streaming=True,
                    supports_images=True,
                    input_text=True,
                    input_image=True,
                    output_text=True,
                ),
                cost=ModelCost(
                    input_per_1m=15.00,
                    output_per_1m=75.00,
                ),
                limits=ModelLimits(
                    max_context=200000,
                    max_output=4096,
                ),
            ),
        }

    def _get_client(self):
        """Get or create Anthropic client."""
        if self._client is None:
            self._client = self._anthropic.AsyncAnthropic(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._client

    async def stream_generate(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """Stream text generation from Anthropic."""
        client = self._get_client()

        # Convert messages to Anthropic format
        anthropic_messages = self._convert_messages(messages)

        # Prepare system message
        system_message = None
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg.get("content", "")
                break

        # Prepare request parameters
        params = {
            "model": model,
            "messages": anthropic_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if system_message:
            params["system"] = system_message

        if tools:
            params["tools"] = self._convert_tools(tools)

        if tool_choice:
            params["tool_choice"] = self._convert_tool_choice(tool_choice)

        params.update(kwargs)

        # Make the streaming request
        async with client.messages.stream(**params) as stream:
            async for text in stream.text_stream:
                yield StreamChunk(
                    delta=text,
                    text=text,
                )

            # Get final response for tool calls and finish reason
            response = await stream.get_final_message()

            # Extract tool calls
            tool_calls = []
            if hasattr(response, 'content'):
                for block in response.content:
                    if hasattr(block, 'type') and block.type == 'tool_use':
                        tool_calls.append({
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })

            yield StreamChunk(
                tool_calls=tool_calls,
                finish_reason=response.stop_reason,
            )

    async def generate(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs
    ) -> StreamResponse:
        """Generate text (non-streaming) from Anthropic."""
        client = self._get_client()

        # Convert messages to Anthropic format
        anthropic_messages = self._convert_messages(messages)

        # Prepare system message
        system_message = None
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg.get("content", "")
                break

        # Prepare request parameters
        params = {
            "model": model,
            "messages": anthropic_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if system_message:
            params["system"] = system_message

        if tools:
            params["tools"] = self._convert_tools(tools)

        if tool_choice:
            params["tool_choice"] = self._convert_tool_choice(tool_choice)

        params.update(kwargs)

        # Make the request
        response = await client.messages.create(**params)

        # Extract text content
        text = ""
        for block in response.content:
            if hasattr(block, 'type') and block.type == 'text':
                text += block.text

        # Extract tool calls
        tool_calls = []
        for block in response.content:
            if hasattr(block, 'type') and block.type == 'tool_use':
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        # Extract usage
        usage = {
            "prompt_tokens": response.usage.input_tokens,
            "completion_tokens": response.usage.output_tokens,
            "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
        }

        return StreamResponse(
            text=text,
            tool_calls=tool_calls,
            finish_reason=response.stop_reason,
            usage=usage,
            raw_response=response,
        )

    def _convert_messages(self, messages: list[dict]) -> list[dict]:
        """Convert standard message format to Anthropic format."""
        anthropic_messages = []

        for msg in messages:
            if msg["role"] == "system":
                continue  # System messages handled separately

            anthropic_msg = {
                "role": msg["role"],
                "content": []
            }

            # Handle content
            content = msg.get("content")
            if isinstance(content, str):
                anthropic_msg["content"] = [{"type": "text", "text": content}]
            elif isinstance(content, list):
                anthropic_msg["content"] = content

            # Handle tool results
            if msg.get("role") == "tool":
                anthropic_msg["role"] = "user"
                anthropic_msg["content"] = [{
                    "type": "tool_result",
                    "tool_use_id": msg.get("tool_call_id"),
                    "content": content
                }]

            anthropic_messages.append(anthropic_msg)

        return anthropic_messages

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        """Convert tools to Anthropic format."""
        anthropic_tools = []

        for tool in tools:
            if "function" in tool:
                func = tool["function"]
                anthropic_tools.append({
                    "name": func["name"],
                    "description": func["description"],
                    "input_schema": func["parameters"],
                })

        return anthropic_tools

    def _convert_tool_choice(self, tool_choice: str) -> Any:
        """Convert tool choice to Anthropic format."""
        if tool_choice == "required":
            return {"type": "any"}
        elif tool_choice == "auto":
            return {"type": "auto"}
        elif tool_choice == "none":
            return None
        return {"type": "auto"}
