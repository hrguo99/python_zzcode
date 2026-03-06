"""
清理处理器

负责处理完成后的清理操作。
"""

import logging
import time
from typing import Dict, Any, List, Callable, Awaitable, Optional

from session_management import (
    Part,
    PatchPart,
    AssistantMessage,
    ToolPart,
    ToolStatus,
    PartType,
    ToolStateError,
)

logger = logging.getLogger(__name__)


class CleanupHandler:
    """
    清理处理器

    职责：
    - 处理未完成的工具调用
    - 处理快照和补丁
    - 更新消息完成时间
    - 保存交互追踪
    """

    def __init__(
        self,
        assistant_message: AssistantMessage,
        session_id: str,
        on_snapshot=None,
        on_patch=None,
        on_parts_get=None,
        on_part_update=None,
        on_message_update=None,
    ):
        self.assistant_message = assistant_message
        self.session_id = session_id
        self.on_snapshot = on_snapshot
        self.on_patch = on_patch
        self.on_parts_get = on_parts_get
        self.on_part_update = on_part_update
        self.on_message_update = on_message_update

    def _generate_id(self, prefix: str) -> str:
        """生成唯一 ID"""
        timestamp = int(time.time() * 1000)
        random = hash(id(self)) % 10000
        return f"{prefix}_{timestamp}_{random}"

    async def cleanup(
        self,
        toolcalls: Dict[str, ToolPart],
        snapshot: Optional[str] = None,
    ) -> None:
        """
        执行清理操作

        Args:
            toolcalls: 当前工具调用状态
            snapshot: 快照 ID
        """
        # 处理快照
        if snapshot and self.on_patch:
            patch_files = await self.on_patch(snapshot)
            if patch_files:
                patch_part = PatchPart(
                    id=self._generate_id("part"),
                    session_id=self.session_id,
                    message_id=self.assistant_message.id,
                    hash="",
                    files=patch_files,
                )
                if self.on_part_update:
                    await self.on_part_update(patch_part)

        # 清理未完成的工具调用
        if self.on_parts_get:
            parts = await self.on_parts_get()
            for part in parts:
                if part.type == PartType.TOOL:
                    tool_part = part
                    if tool_part.state.status not in [ToolStatus.COMPLETED, ToolStatus.ERROR]:
                        updated = ToolPart(
                            id=tool_part.id,
                            session_id=tool_part.session_id,
                            message_id=tool_part.message_id,
                            call_id=tool_part.call_id,
                            tool=tool_part.tool,
                            state=ToolStateError(
                                status=ToolStatus.ERROR,
                                input=tool_part.state.input,
                                error="Tool execution aborted",
                                time_start=int(time.time() * 1000),
                                time_end=int(time.time() * 1000),
                            ),
                        )
                        if self.on_part_update:
                            await self.on_part_update(updated)

        # 更新消息完成时间
        self.assistant_message.time.completed = int(time.time() * 1000)
        if self.on_message_update:
            await self.on_message_update(self.assistant_message)


__all__ = ["CleanupHandler"]
