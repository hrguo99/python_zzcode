"""
主循环处理器

实现完整的主循环逻辑，处理 LLM 流式响应。
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, List, AsyncGenerator

from session_management import (
    Part,
    TextPart,
    ReasoningPart,
    ToolPart,
    StepStartPart,
    StepFinishPart,
    PatchPart,
    AssistantMessage,
    TokenUsage,
    TimeInfo,
    ModelInfo,
    ToolStatePending,
    ToolStateRunning,
    ToolStateCompleted,
    ToolStateError,
    ToolStatus,
    PartType,
    MessageRole,
    AbortSignal,
    SessionRetry,
    InteractionTracker,
    get_tracker,
)

logger = logging.getLogger(__name__)


class ProcessorResult:
    """处理器结果"""
    CONTINUE = "continue"
    STOP = "stop"
    COMPACT = "compact"


class SessionProcessor:
    """
    会话处理器（主循环）

    职责：
    - 管理主循环的生命周期
    - 协调事件处理、清理和重试
    - 维护处理状态
    """

    DOOM_LOOP_THRESHOLD = 3

    def __init__(
        self,
        assistant_message: AssistantMessage,
        session_id: str,
        model: ModelInfo,
        abort: AbortSignal,
        interaction_tracker: Optional[InteractionTracker] = None,
        on_part_update=None,
        on_part_delta=None,
        on_message_update=None,
        on_snapshot=None,
        on_patch=None,
        on_parts_get=None,
    ):
        from .event_handler import EventHandler
        from .doom_loop import DoomLoopDetector
        from .cleanup import CleanupHandler

        self.assistant_message = assistant_message
        self.session_id = session_id
        self.model = model
        self.abort = abort
        self.interaction_tracker = interaction_tracker or get_tracker()

        # 创建子组件
        self.event_handler = EventHandler(
            assistant_message=assistant_message,
            session_id=session_id,
            abort=abort,
            interaction_tracker=interaction_tracker,
            on_part_update=on_part_update,
            on_part_delta=on_part_delta,
        )

        self.doom_loop_detector = DoomLoopDetector(
            threshold=self.DOOM_LOOP_THRESHOLD,
            on_parts_get=on_parts_get,
        )

        self.cleanup_handler = CleanupHandler(
            assistant_message=assistant_message,
            session_id=session_id,
            on_snapshot=on_snapshot,
            on_patch=on_patch,
            on_parts_get=on_parts_get,
            on_part_update=on_part_update,
            on_message_update=on_message_update,
        )

        # 内部状态
        self.blocked = False
        self.attempt = 0
        self.needs_compaction = False
        self.continue_loop_on_deny = False

    async def process_stream(
        self,
        stream: AsyncGenerator[Dict[str, Any], None],
    ) -> str:
        """
        处理完整的流式响应

        Args:
            stream: 流式事件生成器（字典格式）

        Returns:
            处理结果 (continue/stop/compact)
        """
        logger.info("Processing stream", extra={"session_id": self.session_id})

        self.needs_compaction = False

        while True:
            try:
                async for event_dict in stream:
                    self.abort.throw_if_aborted()

                    result = await self.event_handler.handle(event_dict)

                    # 检查 doom loop
                    if result and result.get("type") == "tool-call":
                        await self.doom_loop_detector.check(
                            result["tool_name"],
                            result["input"],
                            self.event_handler.toolcalls
                        )

                    if result and result.get("break_loop"):
                        return result.get("result", ProcessorResult.CONTINUE)

                    # 检查是否需要压缩并中断
                    if self.needs_compaction:
                        break

            except Exception as e:
                logger.error(
                    "Process error",
                    extra={"error": str(e), "session_id": self.session_id},
                    exc_info=True
                )

                # 处理错误
                error_result = await self._handle_error(e)
                if error_result:
                    return error_result

                # 继续重试
                continue

            # 清理工作
            await self.cleanup_handler.cleanup(self.event_handler.toolcalls)

            # 检查结果
            if self.needs_compaction:
                return ProcessorResult.COMPACT
            if self.blocked or self.assistant_message.error:
                return ProcessorResult.STOP
            return ProcessorResult.CONTINUE

    async def _handle_error(self, error: Exception) -> Optional[str]:
        """处理错误"""
        logger.error(
            "Handling error",
            extra={"error": str(error), "session_id": self.session_id},
            exc_info=True
        )

        # 记录错误到消息
        self.assistant_message.error = {
            "name": type(error).__name__,
            "message": str(error),
        }
        if self.event_handler.on_message_update:
            await self.event_handler.on_message_update(self.assistant_message)

        # 检查是否可重试
        retry_info = SessionRetry.is_retryable(error)
        if retry_info is not None:
            self.attempt += 1
            delay = SessionRetry.calculate_delay(self.attempt, error)

            logger.info(
                "Retryable error, will retry",
                extra={
                    "attempt": self.attempt,
                    "delay": delay,
                    "error": str(error),
                }
            )

            await SessionRetry.sleep(delay, self.abort)
            return None  # 返回 None 以继续循环

        # 记录交互追踪
        if not self.event_handler.interaction_has_tracked:
            self.event_handler.interaction_tracker.record_error(str(error))
            self.event_handler.interaction_has_tracked = True

        # 保存交互追踪
        await self.event_handler.interaction_tracker.save()

        return ProcessorResult.STOP

    def part_from_tool_call(self, tool_call_id: str):
        """根据工具调用 ID 获取部分"""
        return self.event_handler.toolcalls.get(tool_call_id)


__all__ = ["SessionProcessor", "ProcessorResult"]
