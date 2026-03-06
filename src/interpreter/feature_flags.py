"""
Feature Flags Configuration System.

This module provides a centralized way to manage experimental features
and feature flags across the OpenCode system.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import os
from enum import Enum


class FlagState(Enum):
    """Feature flag states."""
    DISABLED = "disabled"
    EXPERIMENTAL = "experimental"  # Requires explicit opt-in
    ENABLED = "enabled"


@dataclass
class FeatureFlags:
    """
    Feature flags configuration.

    These flags control experimental and opt-in features across the system.
    Flags can be overridden via environment variables.

    Environment Variable Override Pattern:
        OPENCODE_FLAG_<FLAG_NAME>=true|false
    """

    # LSP Features
    lsp_implicit_integration: FlagState = FlagState.EXPERIMENTAL
    """Enable automatic LSP diagnostics after Write/Edit operations."""

    lsp_auto_fix: FlagState = FlagState.EXPERIMENTAL
    """Enable automatic code fixing via LSP Code Actions."""

    lsp_explicit_tool: FlagState = FlagState.ENABLED
    """Enable explicit LSP tool (existing lsp tool)."""

    def __post_init__(self):
        """Apply environment variable overrides."""
        for flag_name in self.__dataclass_fields__:
            env_var = f"OPENCODE_FLAG_{flag_name.upper()}"
            env_value = os.getenv(env_var)

            if env_value:
                env_value = env_value.lower()
                if env_value in ("true", "1", "enabled"):
                    setattr(self, flag_name, FlagState.ENABLED)
                elif env_value in ("false", "0", "disabled"):
                    setattr(self, flag_name, FlagState.DISABLED)
                elif env_value in ("experimental", "exp"):
                    setattr(self, flag_name, FlagState.EXPERIMENTAL)

    def is_enabled(self, flag_name: str) -> bool:
        """
        Check if a flag is enabled.

        Args:
            flag_name: Name of the flag

        Returns:
            True if flag is in ENABLED state
        """
        state = getattr(self, flag_name, FlagState.DISABLED)
        return state == FlagState.ENABLED

    def is_experimental(self, flag_name: str) -> bool:
        """
        Check if a flag is in experimental state.

        Args:
            flag_name: Name of the flag

        Returns:
            True if flag is in EXPERIMENTAL state
        """
        state = getattr(self, flag_name, FlagState.DISABLED)
        return state == FlagState.EXPERIMENTAL

    def is_disabled(self, flag_name: str) -> bool:
        """
        Check if a flag is disabled.

        Args:
            flag_name: Name of the flag

        Returns:
            True if flag is in DISABLED state
        """
        state = getattr(self, flag_name, FlagState.DISABLED)
        return state == FlagState.DISABLED

    def enable(self, flag_name: str) -> None:
        """
        Enable a flag.

        Args:
            flag_name: Name of the flag to enable
        """
        if hasattr(self, flag_name):
            setattr(self, flag_name, FlagState.ENABLED)

    def disable(self, flag_name: str) -> None:
        """
        Disable a flag.

        Args:
            flag_name: Name of the flag to disable
        """
        if hasattr(self, flag_name):
            setattr(self, flag_name, FlagState.DISABLED)

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "FeatureFlags":
        """
        Create FeatureFlags from configuration dictionary.

        Args:
            config: Configuration dictionary with flag settings

        Returns:
            FeatureFlags instance
        """
        flags = cls()

        for flag_name, flag_value in config.items():
            if hasattr(flags, flag_name):
                if isinstance(flag_value, str):
                    flags.__setattr__(
                        flag_name,
                        FlagState(flag_value.lower())
                    )
                elif isinstance(flag_value, bool):
                    flags.__setattr__(
                        flag_name,
                        FlagState.ENABLED if flag_value else FlagState.DISABLED
                    )

        return flags

    def to_dict(self) -> Dict[str, str]:
        """
        Convert to dictionary representation.

        Returns:
            Dictionary mapping flag names to their states
        """
        return {
            name: getattr(self, name).value
            for name in self.__dataclass_fields__
        }


# Global singleton instance
_global_flags: Optional[FeatureFlags] = None


def get_flags() -> FeatureFlags:
    """
    Get the global feature flags instance.

    Returns:
        FeatureFlags instance
    """
    global _global_flags
    if _global_flags is None:
        _global_flags = FeatureFlags()
    return _global_flags


def set_flags(flags: FeatureFlags) -> None:
    """
    Set the global feature flags instance.

    Args:
        flags: FeatureFlags instance to set as global
    """
    global _global_flags
    _global_flags = flags


__all__ = [
    "FeatureFlags",
    "FlagState",
    "get_flags",
    "set_flags",
]
