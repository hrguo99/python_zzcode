"""
Processor 模块

主循环处理模块，负责处理 LLM 流式响应的核心逻辑。
基于 TypeScript 实现: packages/opencode/src/session/processor.ts

职责：
- 处理流式事件
- 管理工具调用状态
- 检测 doom loop
- 执行清理操作
依赖：session_management（类型定义）、ai_sdk（LLM 调用）
"""

from .processor import SessionProcessor
from .event_handler import EventHandler
from .doom_loop import DoomLoopDetector
from .cleanup import CleanupHandler

__all__ = [
    "SessionProcessor",
    "EventHandler",
    "DoomLoopDetector",
    "CleanupHandler",
]
