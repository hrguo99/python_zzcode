"""
Doom Loop 检测器

检测重复的工具调用，防止陷入无限循环。
"""

import json
import logging
from typing import Dict, Any, List, Callable, Awaitable

from session_management import Part, PartType, ToolPart

logger = logging.getLogger(__name__)


class DoomLoopDetector:
    """
    Doom Loop 检测器

    职责：
    - 检测重复的工具调用
    - 在检测到潜在循环时发出警告
    """

    def __init__(
        self,
        threshold: int = 3,
        on_parts_get: Callable[[], Awaitable[List[Part]]] = None,
    ):
        """
        初始化检测器

        Args:
            threshold: 检测阈值（连续多少次相同调用视为 doom loop）
            on_parts_get: 获取历史部分的回调
        """
        self.threshold = threshold
        self.on_parts_get = on_parts_get

    async def check(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        current_toolcalls: Dict[str, ToolPart],
    ) -> None:
        """
        检查是否陷入 doom loop

        Args:
            tool_name: 工具名称
            tool_input: 工具输入
            current_toolcalls: 当前工具调用状态
        """
        if not self.on_parts_get:
            return

        parts = await self.on_parts_get()

        # 合并当前正在进行的工具调用
        all_parts = parts + list(current_toolcalls.values())

        # 取最近的 N 个工具部分
        tool_parts = [
            p for p in all_parts
            if p.type == PartType.TOOL
        ]

        last_n = tool_parts[-self.threshold:]

        if len(last_n) < self.threshold:
            return

        # 检查是否所有都相同
        current_toolcalls_list = list(current_toolcalls.values()) if current_toolcalls else []
        all_same = all(
            p.tool == tool_name
            and not isinstance(p.state, type(current_toolcalls_list[0].state)) if current_toolcalls_list else True
            and json.dumps(p.state.input, sort_keys=True) == json.dumps(tool_input, sort_keys=True)
            for p in last_n
        )

        if all_same:
            logger.warning(
                "Doom loop detected",
                extra={
                    "tool": tool_name,
                    "input": tool_input,
                    "threshold": self.threshold,
                }
            )
            # TODO: 触发权限请求或其他处理


__all__ = ["DoomLoopDetector"]
