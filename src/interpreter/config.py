"""
解释器配置
"""

from dataclasses import dataclass, field
from typing import Optional

from .feature_flags import FeatureFlags


@dataclass
class InterpreterConfig:
    """解释器配置"""
    provider: str = "anthropic"
    model: str = "claude-3-5-sonnet-20241022"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: int = 120
    max_retries: int = 0
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    tool_choice: str = "auto"

    # Feature flags configuration
    feature_flags: FeatureFlags = field(default_factory=FeatureFlags)


__all__ = ["InterpreterConfig", "FeatureFlags"]
