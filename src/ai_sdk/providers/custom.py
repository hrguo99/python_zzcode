"""
Custom/OpenAI-compatible provider for local models.

Supports local deployments like:
- Ollama (http://localhost:11434/v1)
- vLLM (http://localhost:8000/v1)
- LocalAI (http://localhost:8080/v1)
- LM Studio (http://localhost:1234/v1)
- Any OpenAI-compatible API
"""

from __future__ import annotations

from typing import Any, AsyncIterator
from .base import BaseProvider, Model, ModelCapabilities, ModelCost, ModelLimits, StreamChunk, StreamResponse


class CustomProvider(BaseProvider):
    """
    Custom provider for OpenAI-compatible local models.

    This provider can be used with any local model server that follows
    the OpenAI API format.

    Example:
        ```python
        # For Ollama
        provider = CustomProvider(
            base_url="http://localhost:11434/v1",
            models={
                "llama3.2": Model(
                    id="llama3.2",
                    provider_id="custom",
                    name="Llama 3.2",
                    capabilities=ModelCapabilities(
                        temperature=True,
                        streaming=True,
                        input_text=True,
                        output_text=True,
                    ),
                    cost=ModelCost(input_per_1m=0, output_per_1m=0),
                    limits=ModelLimits(max_context=8192, max_output=4096),
                )
            }
        )

        # Or use default models
        provider = CustomProvider(base_url="http://localhost:11434/v1")
        ```
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        models: dict[str, Model] | None = None,
        provider_name: str = "Custom",
    ):
        """
        Initialize custom provider.

        Args:
            api_key: Optional API key (not needed for most local models)
            base_url: Base URL of your local model server
            models: Optional dictionary of custom models
            provider_name: Name for this provider instance
        """
        # Set a dummy API key if none provided (local models often don't need it)
        if api_key is None:
            api_key = "not-needed"

        super().__init__(api_key, base_url)

        try:
            from openai import AsyncOpenAI
            self._client = None
            self._AsyncOpenAI = AsyncOpenAI
        except ImportError:
            raise ImportError(
                "OpenAI package is required. Install with: pip install openai"
            )

        # Store custom models
        self._custom_models = models
        self._provider_name = provider_name

    def _get_api_key_env(self) -> str:
        return "CUSTOM_API_KEY"

    @property
    def provider_id(self) -> str:
        return "custom"

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def available_models(self) -> dict[str, Model]:
        # If custom models provided, use those
        if self._custom_models:
            return self._custom_models

        # Otherwise, return some common local model defaults
        return {
            "default": Model(
                id="default",
                provider_id="custom",
                name="Default Local Model",
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
                    input_per_1m=0,  # Free for local models
                    output_per_1m=0,
                ),
                limits=ModelLimits(
                    max_context=8192,
                    max_output=4096,
                ),
            ),
        }

    def _get_client(self):
        """Get or create OpenAI client."""
        if self._client is None:
            self._client = self._AsyncOpenAI(
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
        """Stream text generation from custom provider."""
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
        """Generate text (non-streaming) from custom provider."""
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

    def validate_config(self) -> list[str]:
        """Validate provider configuration."""
        errors = []

        if not self.base_url:
            errors.append("base_url is required for custom provider")

        return errors
