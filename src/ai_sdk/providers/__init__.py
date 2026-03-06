"""
Provider package for AI SDK.
"""

from .base import (
    BaseProvider,
    ProviderType,
    Model,
    ModelCapabilities,
    ModelCost,
    ModelLimits,
    StreamChunk,
    StreamResponse,
)

from .openai import OpenAIProvider
from .anthropic import AnthropicProvider
from .glm import GLMProvider
from .custom import CustomProvider

__all__ = [
    "BaseProvider",
    "ProviderType",
    "Model",
    "ModelCapabilities",
    "ModelCost",
    "ModelLimits",
    "StreamChunk",
    "StreamResponse",
    "OpenAIProvider",
    "AnthropicProvider",
    "GLMProvider",
    "CustomProvider",
    "ProviderRegistry",
]


class ProviderRegistry:
    """
    Registry for managing multiple providers.

    Example:
        ```python
        registry = ProviderRegistry()

        # Register a provider
        registry.register("openai", OpenAIProvider())

        # Get provider
        provider = registry.get("openai")

        # Get model from provider
        model = registry.get_model("openai", "gpt-4")
        ```
    """

    def __init__(self):
        self._providers: dict[str, BaseProvider] = {}

    def register(self, provider_id: str, provider: BaseProvider) -> None:
        """Register a provider."""
        self._providers[provider_id] = provider

    def unregister(self, provider_id: str) -> None:
        """Unregister a provider."""
        if provider_id in self._providers:
            del self._providers[provider_id]

    def get(self, provider_id: str) -> BaseProvider | None:
        """Get a provider by ID."""
        return self._providers.get(provider_id)

    def get_all(self) -> dict[str, BaseProvider]:
        """Get all registered providers."""
        return self._providers.copy()

    def get_model(self, provider_id: str, model_id: str) -> Model | None:
        """Get a model from a specific provider."""
        provider = self.get(provider_id)
        if provider:
            return provider.get_model(model_id)
        return None

    def list_models(self) -> dict[str, list[Model]]:
        """List all models from all providers."""
        result = {}
        for provider_id, provider in self._providers.items():
            result[provider_id] = list(provider.available_models.values())
        return result
