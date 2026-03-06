"""
OpenCode Skill Module - Python Implementation

This module provides the skill functionality for OpenCode, including:
- Skill discovery and loading
- Skill content management
- Skill execution through tools
- Permission integration
"""

from .models import SkillInfo, SkillMetadata, SkillConfig
from .skill import SkillManager, SkillManagerConfig
from .discovery import SkillDiscovery
from .tools import SkillTool

__all__ = [
    "SkillInfo",
    "SkillMetadata",
    "SkillConfig",
    "SkillManager",
    "SkillManagerConfig",
    "SkillDiscovery",
    "SkillTool",
]

__version__ = "0.1.0"
