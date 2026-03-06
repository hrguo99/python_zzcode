"""
Provider management and factory for AI SDK.

This module provides high-level provider management and configuration loading.
"""

from __future__ import annotations

from typing import Any, Optional
import os
import json
from pathlib import Path

from .providers import BaseProvider, ProviderRegistry, OpenAIProvider, AnthropicProvider, GLMProvider


class ProviderManager:
    """
    Manages provider initialization and configuration.

    This is the main entry point for working with providers in the AI SDK.
    """

    def __init__(self, config_path: str | None = None):
        """
        Initialize provider manager.

        Args:
            config_path: Optional path to models configuration JSON file
        """
        self.registry = ProviderRegistry()
        self.config_path = config_path or self._find_config_path()
        self._load_providers()

    def _find_config_path(self) -> str | None:
        """Find the models configuration file."""
        # Check common locations
        possible_paths = [
            "config/models.json",
            "../config/models.json",
            "../../config/models.json",
        ]

        for path in possible_paths:
            full_path = Path(__file__).parent.parent.parent / path
            if full_path.exists():
                return str(full_path)

        return None

    def _load_providers(self):
        """Load and initialize providers."""
        # Register built-in providers
        try:
            openai_provider = OpenAIProvider()
            self.registry.register("openai", openai_provider)
        except Exception as e:
            # API key might not be set
            pass

        try:
            anthropic_provider = AnthropicProvider()
            self.registry.register("anthropic", anthropic_provider)
        except Exception as e:
            # API key might not be set
            pass

        try:
            glm_provider = GLMProvider()
            self.registry.register("glm", glm_provider)
        except Exception as e:
            # API key might not be set
            pass

        # Load custom providers from config if available
        if self.config_path:
            self._load_config_providers()

    def _load_config_providers(self):
        """Load providers from configuration file."""
        if not self.config_path:
            return

        try:
            with open(self.config_path) as f:
                config = json.load(f)

            # Load custom providers from config
            for provider_id, provider_config in config.get("providers", {}).items():
                # Custom provider loading logic would go here
                pass

        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def get_provider(self, provider_id: str) -> BaseProvider | None:
        """Get a provider by ID."""
        return self.registry.get(provider_id)

    def get_providers(self) -> dict[str, BaseProvider]:
        """Get all registered providers."""
        return self.registry.get_all()

    def get_model(self, provider_id: str, model_id: str):
        """Get a model from a provider."""
        return self.registry.get_model(provider_id, model_id)

    def list_models(self) -> dict[str, list]:
        """List all available models."""
        models = self.registry.list_models()
        return {
            provider_id: [
                {
                    "id": model.id,
                    "name": model.name,
                    "capabilities": {
                        "toolcall": model.capabilities.toolcall,
                        "streaming": model.capabilities.streaming,
                        "supports_images": model.capabilities.supports_images,
                    },
                    "limits": {
                        "max_context": model.limits.max_context,
                        "max_output": model.limits.max_output,
                    },
                }
                for model in provider_models
            ]
            for provider_id, provider_models in models.items()
        }

    def validate_provider(self, provider_id: str) -> list[str]:
        """Validate provider configuration."""
        provider = self.get_provider(provider_id)
        if not provider:
            return [f"Provider '{provider_id}' not found"]
        return provider.validate_config()

    def get_default_provider(self) -> str:
        """Get the default provider from environment or 'openai'."""
        return os.getenv("DEFAULT_PROVIDER", "openai")

    def get_default_model(self, provider_id: str) -> str:
        """Get the default model for a provider."""
        defaults = {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-3-5-sonnet-20241022",
        }
        return os.getenv(f"{provider_id.upper()}_DEFAULT_MODEL", defaults.get(provider_id, ""))
