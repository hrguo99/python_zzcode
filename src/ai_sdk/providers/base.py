"""
Base provider interface for AI SDK.

This module defines the abstract interface that all providers must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Optional
from dataclasses import dataclass, field
from enum import Enum
import os


class ProviderType(Enum):
    """Provider types."""
    BUNDLED = "bundled"  # Built-in providers (OpenAI, Anthropic, etc.)
    DYNAMIC = "dynamic"  # Dynamically loaded via plugin
    CUSTOM = "custom"    # Custom user-defined provider


@dataclass
class ModelCapabilities:
    """Model capability flags."""
    temperature: bool = True
    reasoning: bool = False
    attachment: bool = False
    toolcall: bool = True
    streaming: bool = True
    supports_images: bool = False
    supports_audio: bool = False
    supports_video: bool = False
    supports_pdf: bool = False

    # Input/output capabilities
    input_text: bool = True
    input_image: bool = False
    input_audio: bool = False
    input_video: bool = False
    input_pdf: bool = False

    output_text: bool = True
    output_image: bool = False
    output_audio: bool = False
    output_video: bool = False


@dataclass
class ModelCost:
    """Token costs for the model."""
    input_per_1m: float
    output_per_1m: float
    cache_read_per_1m: Optional[float] = None
    cache_write_per_1m: Optional[float] = None


@dataclass
class ModelLimits:
    """Model usage limits."""
    max_context: int
    max_output: int


@dataclass
class Model:
    """Model definition."""
    id: str
    provider_id: str
    name: str
    capabilities: ModelCapabilities
    cost: ModelCost
    limits: ModelLimits
    base_url: Optional[str] = None
    api_key: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "provider_id": self.provider_id,
            "name": self.name,
            "capabilities": {
                "temperature": self.capabilities.temperature,
                "reasoning": self.capabilities.reasoning,
                "toolcall": self.capabilities.toolcall,
                "streaming": self.capabilities.streaming,
                "supports_images": self.capabilities.supports_images,
                "input_text": self.capabilities.input_text,
                "input_image": self.capabilities.input_image,
            },
            "cost": {
                "input_per_1m": self.cost.input_per_1m,
                "output_per_1m": self.cost.output_per_1m,
            },
            "limits": {
                "max_context": self.limits.max_context,
                "max_output": self.limits.max_output,
            }
        }


@dataclass
class StreamChunk:
    """A chunk of streamed response."""
    delta: str | None = None
    text: str | None = None
    tool_calls: list[dict] = field(default_factory=list)
    finish_reason: str | None = None
    usage: dict[str, int] | None = None
    reasoning: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        return self.finish_reason is not None


@dataclass
class StreamResponse:
    """Complete streaming response."""
    text: str
    tool_calls: list[dict] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    reasoning: str | None = None
    raw_response: Any = None


class BaseProvider(ABC):
    """
    Abstract base class for all AI providers.

    All providers must implement this interface to be compatible with the LLM abstraction layer.
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or os.getenv(self._get_api_key_env())
        self.base_url = base_url or os.getenv(f"{self._get_prefix()}_BASE_URL")

    @abstractmethod
    def _get_api_key_env(self) -> str:
        """Return the environment variable name for the API key."""
        pass

    def _get_prefix(self) -> str:
        """Return the environment variable prefix for this provider."""
        return self.provider_id.upper()

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique provider identifier."""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""
        pass

    @property
    @abstractmethod
    def available_models(self) -> dict[str, Model]:
        """Dictionary of available models."""
        pass

    @abstractmethod
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
        """
        Stream text generation from the model.

        Args:
            model: Model ID to use
            messages: Conversation messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            tools: Available tools for function calling
            tool_choice: Tool choice strategy ("auto", "required", "none")
            **kwargs: Additional provider-specific parameters

        Yields:
            StreamChunk objects with partial results
        """
        pass

    @abstractmethod
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
        """
        Generate text (non-streaming).

        Args:
            model: Model ID to use
            messages: Conversation messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            tools: Available tools for function calling
            tool_choice: Tool choice strategy
            **kwargs: Additional provider-specific parameters

        Returns:
            StreamResponse with complete result
        """
        pass

    def get_model(self, model_id: str) -> Model | None:
        """Get model configuration by ID."""
        return self.available_models.get(model_id)

    def supports_tool_calling(self, model_id: str) -> bool:
        """Check if model supports tool calling."""
        model = self.get_model(model_id)
        return model.capabilities.toolcall if model else False

    def supports_streaming(self, model_id: str) -> bool:
        """Check if model supports streaming."""
        model = self.get_model(model_id)
        return model.capabilities.streaming if model else False

    def get_max_tokens(self, model_id: str) -> int:
        """Get maximum output tokens for model."""
        model = self.get_model(model_id)
        return model.limits.max_output if model else 4096

    def estimate_cost(
        self,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0
    ) -> float:
        """
        Estimate cost in USD for a request.

        Args:
            model_id: Model ID
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cache_read_tokens: Number of cached tokens read
            cache_write_tokens: Number of cached tokens written

        Returns:
            Estimated cost in USD
        """
        model = self.get_model(model_id)
        if not model:
            return 0.0

        cost = 0.0
        cost += (input_tokens / 1_000_000) * model.cost.input_per_1m
        cost += (output_tokens / 1_000_000) * model.cost.output_per_1m

        if model.cost.cache_read_per_1m and cache_read_tokens > 0:
            cost += (cache_read_tokens / 1_000_000) * model.cost.cache_read_per_1m

        if model.cost.cache_write_per_1m and cache_write_tokens > 0:
            cost += (cache_write_tokens / 1_000_000) * model.cost.cache_write_per_1m

        return cost

    def validate_config(self) -> list[str]:
        """
        Validate provider configuration.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        if not self.api_key:
            errors.append(f"API key not found (set {self._get_api_key_env()} environment variable)")

        return errors
