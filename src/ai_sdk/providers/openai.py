"""
OpenAI provider implementation.
"""

from __future__ import annotations

from typing import Any, AsyncIterator
import json

from .base import BaseProvider, Model, ModelCapabilities, ModelCost, ModelLimits, StreamChunk, StreamResponse


class OpenAIProvider(BaseProvider):
    """OpenAI provider (GPT-3.5, GPT-4, etc.)."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        super().__init__(api_key, base_url)

        try:
            import openai
            self._client = None
            self._openai = openai
        except ImportError:
            raise ImportError(
                "OpenAI package is required. Install with: pip install openai"
            )

    def _get_api_key_env(self) -> str:
        return "OPENAI_API_KEY"

    @property
    def provider_id(self) -> str:
        return "openai"

    @property
    def provider_name(self) -> str:
        return "OpenAI"

    @property
    def available_models(self) -> dict[str, Model]:
        return {
            "gpt-4o": Model(
                id="gpt-4o",
                provider_id="openai",
                name="GPT-4 Omni",
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
                    input_per_1m=2.50,
                    output_per_1m=10.00,
                ),
                limits=ModelLimits(
                    max_context=128000,
                    max_output=4096,
                ),
            ),
            "gpt-4o-mini": Model(
                id="gpt-4o-mini",
                provider_id="openai",
                name="GPT-4 Omni Mini",
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
                    input_per_1m=0.15,
                    output_per_1m=0.60,
                ),
                limits=ModelLimits(
                    max_context=128000,
                    max_output=16384,
                ),
            ),
            "gpt-4-turbo": Model(
                id="gpt-4-turbo",
                provider_id="openai",
                name="GPT-4 Turbo",
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
                    input_per_1m=10.00,
                    output_per_1m=30.00,
                ),
                limits=ModelLimits(
                    max_context=128000,
                    max_output=4096,
                ),
            ),
            "gpt-3.5-turbo": Model(
                id="gpt-3.5-turbo",
                provider_id="openai",
                name="GPT-3.5 Turbo",
                capabilities=ModelCapabilities(
                    temperature=True,
                    reasoning=False,
                    attachment=True,
                    toolcall=True,
                    streaming=True,
                    input_text=True,
                    output_text=True,
                ),
                cost=ModelCost(
                    input_per_1m=0.50,
                    output_per_1m=1.50,
                ),
                limits=ModelLimits(
                    max_context=16385,
                    max_output=4096,
                ),
            ),
        }

    def _get_client(self):
        """Get or create OpenAI client."""
        if self._client is None:
            self._client = self._openai.AsyncOpenAI(
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
        """Stream text generation from OpenAI."""
        client = self._get_client()

        # Prepare request parameters
        params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        if tools:
            params["tools"] = tools

        if tool_choice:
            params["tool_choice"] = tool_choice

        # Add any additional parameters
        params.update(kwargs)

        # Make the streaming request
        stream = await client.chat.completions.create(**params)

        async for chunk in stream:
            # Extract delta
            delta = chunk.choices[0].delta

            # Extract text
            text = delta.content or None

            # Extract tool calls
            tool_calls = []
            if delta.tool_calls:
                for tool_call in delta.tool_calls:
                    tool_calls.append({
                        "index": tool_call.index,
                        "id": tool_call.id,
                        "type": tool_call.type,
                        "function": {
                            "name": tool_call.function.name if tool_call.function.name else None,
                            "arguments": tool_call.function.arguments if tool_call.function.arguments else "",
                        }
                    })

            # Extract finish reason
            finish_reason = chunk.choices[0].finish_reason

            # Extract usage (only in final chunk)
            usage = None
            if chunk.usage:
                usage = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens,
                }

            yield StreamChunk(
                delta=text,
                text=text,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                usage=usage,
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
        """Generate text (non-streaming) from OpenAI."""
        client = self._get_client()

        # Prepare request parameters
        params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            params["tools"] = tools

        if tool_choice:
            params["tool_choice"] = tool_choice

        params.update(kwargs)

        # Make the request
        response = await client.chat.completions.create(**params)

        # Extract the message
        message = response.choices[0].message

        # Extract tool calls
        tool_calls = []
        if message.tool_calls:
            for tool_call in message.tool_calls:
                tool_calls.append({
                    "id": tool_call.id,
                    "type": tool_call.type,
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    }
                })

        # Extract usage
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }

        return StreamResponse(
            text=message.content or "",
            tool_calls=tool_calls,
            finish_reason=response.choices[0].finish_reason or "stop",
            usage=usage,
            raw_response=response,
        )
