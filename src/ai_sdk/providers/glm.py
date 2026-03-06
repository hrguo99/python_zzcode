"""
GLM (Zhipu AI) provider implementation.

GLM is a Chinese AI model provider with models like GLM-4, GLM-3-Turbo, etc.
API documentation: https://open.bigmodel.cn/dev/api
"""

from __future__ import annotations

from typing import Any, AsyncIterator
import json

from .base import BaseProvider, Model, ModelCapabilities, ModelCost, ModelLimits, StreamChunk, StreamResponse


class GLMProvider(BaseProvider):
    """GLM (Zhipu AI) provider."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        super().__init__(api_key, base_url)

        try:
            from openai import AsyncOpenAI
            self._client = None
            self._AsyncOpenAI = AsyncOpenAI
        except ImportError:
            raise ImportError(
                "OpenAI package is required for GLM provider. "
                "Install with: pip install openai"
            )

    def _get_api_key_env(self) -> str:
        return "GLM_API_KEY"

    @property
    def provider_id(self) -> str:
        return "glm"

    @property
    def provider_name(self) -> str:
        return "GLM"

    @property
    def available_models(self) -> dict[str, Model]:
        return {
            "glm-4-plus": Model(
                id="glm-4-plus",
                provider_id="glm",
                name="GLM-4 Plus",
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
                    input_per_1m=0.5,  # ¥0.5 per 1M tokens (approximately)
                    output_per_1m=0.5,
                ),
                limits=ModelLimits(
                    max_context=128000,
                    max_output=4096,
                ),
            ),
            "glm-4": Model(
                id="glm-4",
                provider_id="glm",
                name="GLM-4",
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
                    input_per_1m=0.1,  # ¥0.1 per 1M tokens
                    output_per_1m=0.1,
                ),
                limits=ModelLimits(
                    max_context=128000,
                    max_output=4096,
                ),
            ),
            "glm-4-flash": Model(
                id="glm-4-flash",
                provider_id="glm",
                name="GLM-4 Flash",
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
                    input_per_1m=0.01,  # ¥0.01 per 1M tokens
                    output_per_1m=0.01,
                ),
                limits=ModelLimits(
                    max_context=128000,
                    max_output=4096,
                ),
            ),
            "glm-4-flashx": Model(
                id="glm-4-flashx",
                provider_id="glm",
                name="GLM-4 FlashX",
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
                    input_per_1m=0.01,  # ¥0.01 per 1M tokens
                    output_per_1m=0.01,
                ),
                limits=ModelLimits(
                    max_context=128000,
                    max_output=4096,
                ),
            ),
            "glm-4-air": Model(
                id="glm-4-air",
                provider_id="glm",
                name="GLM-4 Air",
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
                    input_per_1m=0.001,  # ¥0.001 per 1M tokens
                    output_per_1m=0.001,
                ),
                limits=ModelLimits(
                    max_context=128000,
                    max_output=4096,
                ),
            ),
            "glm-4-long": Model(
                id="glm-4-long",
                provider_id="glm",
                name="GLM-4 Long",
                capabilities=ModelCapabilities(
                    temperature=True,
                    reasoning=True,
                    attachment=False,
                    toolcall=True,
                    streaming=True,
                    input_text=True,
                    output_text=True,
                ),
                cost=ModelCost(
                    input_per_1m=0.01,  # ¥0.01 per 1M tokens
                    output_per_1m=0.01,
                ),
                limits=ModelLimits(
                    max_context=1000000,  # 1M context!
                    max_output=4096,
                ),
            ),
            "glm-3-turbo": Model(
                id="glm-3-turbo",
                provider_id="glm",
                name="GLM-3 Turbo",
                capabilities=ModelCapabilities(
                    temperature=True,
                    reasoning=False,
                    attachment=False,
                    toolcall=True,
                    streaming=True,
                    input_text=True,
                    output_text=True,
                ),
                cost=ModelCost(
                    input_per_1m=0.005,  # ¥0.005 per 1M tokens
                    output_per_1m=0.005,
                ),
                limits=ModelLimits(
                    max_context=128000,
                    max_output=4096,
                ),
            ),
        }

    def _get_client(self):
        """Get or create GLM client."""
        if self._client is None:
            # GLM uses OpenAI-compatible API
            # Default base URL for Zhipu AI
            base_url = self.base_url or "https://open.bigmodel.cn/api/paas/v4/"

            self._client = self._AsyncOpenAI(
                api_key=self.api_key,
                base_url=base_url,
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
        """Stream text generation from GLM."""
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
            if hasattr(chunk, 'usage') and chunk.usage:
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
        """Generate text (non-streaming) from GLM."""
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
