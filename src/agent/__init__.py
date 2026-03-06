"""
OpenCode Agent Module - Python Implementation

This module provides the core agent functionality for OpenCode, including:
- Agent information and configuration
- Built-in agents (build, plan, general, explore, etc.)
- Permission management
- Agent lifecycle management
"""

from .models import AgentInfo, AgentMode, ModelInfo
from .agent import Agent, AgentConfig
from .permissions import PermissionRule, PermissionAction, PermissionRuleset, PermissionNext
from .builtin_agents import BuiltinAgents
from .acp_agent import ACPAgent, ToolKind, ToolStatus

__all__ = [
    "AgentInfo",
    "AgentMode",
    "ModelInfo",
    "Agent",
    "AgentConfig",
    "PermissionRule",
    "PermissionAction",
    "PermissionRuleset",
    "PermissionNext",
    "BuiltinAgents",
    "ACPAgent",
    "ToolKind",
    "ToolStatus",
]

__version__ = "0.1.0"
