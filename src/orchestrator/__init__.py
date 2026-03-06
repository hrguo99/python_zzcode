"""
编排器模块

整合所有模块，实现完整的对话系统工作流程。

职责：
- 输入解析与分流
- 命令处理
- 智能体切换
- 主循环编排
"""

from .orchestrator import Orchestrator
from .parser import InputParser, InputType
from .command_handler import CommandHandler
from .agent_switcher import AgentSwitcher

__all__ = [
    "Orchestrator",
    "InputParser",
    "InputType",
    "CommandHandler",
    "AgentSwitcher",
]
