"""
事件处理器

处理所有流式事件，更新消息和部分。
"""

import logging
import time
from typing import Dict, Any, Optional, List, Callable, Awaitable

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
    ToolStatePending,
    ToolStateRunning,
    ToolStateCompleted,
    ToolStateError,
    ToolStatus,
    InteractionTracker,
)
from session_management.interaction_tracker import ToolCallRecord, TokenUsageRecord

logger = logging.getLogger(__name__)


class EventHandler:
    """
    事件处理器

    职责：
    - 处理所有流式事件
    - 更新消息和部分
    - 收集交互追踪数据
    """

    def __init__(
        self,
        assistant_message: AssistantMessage,
        session_id: str,
        abort,
        interaction_tracker: InteractionTracker,
        on_part_update=None,
        on_part_delta=None,
        on_message_update=None,
    ):
        self.assistant_message = assistant_message
        self.session_id = session_id
        self.abort = abort
        self.interaction_tracker = interaction_tracker
        self.on_part_update = on_part_update
        self.on_part_delta = on_part_delta
        self.on_message_update = on_message_update

        # 内部状态
        self.toolcalls: Dict[str, ToolPart] = {}
        self.reasoning_map: Dict[str, ReasoningPart] = {}
        self.current_text: Optional[TextPart] = None
        self.snapshot: Optional[str] = None

        # 交互追踪状态
        self.interaction_output_text = ""
        self.interaction_tool_calls: Dict[str, ToolCallRecord] = {}
        self.interaction_has_tracked = False

    async def handle(self, event_dict: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理事件字典

        Args:
            event_dict: 事件字典

        Returns:
            处理结果（可选）
        """
        event_type = event_dict.get("type")

        handlers = {
            "start": self._handle_start,
            "reasoning-start": self._handle_reasoning_start,
            "reasoning-delta": self._handle_reasoning_delta,
            "reasoning-end": self._handle_reasoning_end,
            "tool-input-start": self._handle_tool_input_start,
            "tool-input-delta": lambda e: None,
            "tool-input-end": lambda e: None,
            "tool-call": self._handle_tool_call,
            "tool-result": self._handle_tool_result,
            "tool-error": self._handle_tool_error,
            "text-start": self._handle_text_start,
            "text-delta": self._handle_text_delta,
            "text-end": self._handle_text_end,
            "start-step": self._handle_start_step,
            "finish-step": self._handle_finish_step,
            "finish": self._handle_finish,
            "error": self._handle_error_event,
        }

        handler = handlers.get(event_type)
        if handler:
            return await handler(event_dict)

        logger.warning("Unhandled event", extra={"event_type": event_type})
        return None

    def _generate_id(self, prefix: str) -> str:
        """生成唯一 ID"""
        timestamp = int(time.time() * 1000)
        random = hash(id(self)) % 10000
        return f"{prefix}_{timestamp}_{random}"

    async def _update_part(self, part: Part) -> Part:
        """更新部分到存储"""
        if self.on_part_update:
            await self.on_part_update(part)
        return part

    # 事件处理方法
    async def _handle_start(self, event: Dict[str, Any]) -> None:
        logger.debug("Stream started", extra={"session_id": self.session_id})
        if self.interaction_tracker:
            self.interaction_tracker.add_event("start")

    async def _handle_reasoning_start(self, event: Dict[str, Any]) -> None:
        if event["id"] in self.reasoning_map:
            return

        if self.interaction_tracker:
            self.interaction_tracker.add_event("reasoning-start", {"id": event["id"]})

        part = ReasoningPart(
            id=self._generate_id("part"),
            session_id=self.session_id,
            message_id=self.assistant_message.id,
            text="",
            time=TimeInfo(start=int(time.time() * 1000)),
            metadata=event.get("provider_metadata"),
        )
        self.reasoning_map[event["id"]] = part
        await self._update_part(part)

    async def _handle_reasoning_delta(self, event: Dict[str, Any]) -> None:
        if event["id"] in self.reasoning_map:
            part = self.reasoning_map[event["id"]]
            part.text += event["text"]
            if event.get("provider_metadata"):
                part.metadata = event["provider_metadata"]

            if self.on_part_delta:
                await self.on_part_delta(
                    part.session_id,
                    part.message_id,
                    part.id,
                    "text",
                    event["text"],
                )

    async def _handle_reasoning_end(self, event: Dict[str, Any]) -> None:
        if event["id"] in self.reasoning_map:
            if self.interaction_tracker:
                self.interaction_tracker.add_event("reasoning-end", {"id": event["id"]})

            part = self.reasoning_map[event["id"]]
            part.text = part.text.rstrip()
            part.time.end = int(time.time() * 1000)
            if event.get("provider_metadata"):
                part.metadata = event["provider_metadata"]

            await self._update_part(part)
            del self.reasoning_map[event["id"]]

    async def _handle_tool_input_start(self, event: Dict[str, Any]) -> None:
        existing = self.toolcalls.get(event["id"])
        part_id = existing.id if existing else self._generate_id("part")

        part = ToolPart(
            id=part_id,
            session_id=self.session_id,
            message_id=self.assistant_message.id,
            call_id=event["id"],
            tool=event["tool_name"],
            state=ToolStatePending(
                status=ToolStatus.PENDING,
                input={},
                raw="",
            ),
        )
        self.toolcalls[event["id"]] = await self._update_part(part)

    async def _handle_tool_call(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        existing = self.toolcalls.get(event["tool_call_id"])
        if existing:
            if self.interaction_tracker:
                self.interaction_tracker.add_event("tool-call", {
                    "toolCallId": event["tool_call_id"],
                    "toolName": event["tool_name"],
                    "input": event["input"]
                })

            part = ToolPart(
                id=existing.id,
                session_id=existing.session_id,
                message_id=existing.message_id,
                call_id=event["tool_call_id"],
                tool=event["tool_name"],
                state=ToolStateRunning(
                    status=ToolStatus.RUNNING,
                    input=event["input"],
                    time_start=int(time.time() * 1000),
                    metadata=event.get("provider_metadata"),
                ),
                metadata=event.get("provider_metadata"),
            )
            self.toolcalls[event["tool_call_id"]] = await self._update_part(part)

            # 创建工具调用记录
            self.interaction_tool_calls[event["tool_call_id"]] = ToolCallRecord(
                id=event["tool_call_id"],
                tool_name=event["tool_name"],
                input=event["input"],
            )

            return event  # 返回事件供 doom loop 检测

    async def _handle_tool_result(self, event: Dict[str, Any]) -> None:
        existing = self.toolcalls.get(event["tool_call_id"])
        if existing and isinstance(existing.state, ToolStateRunning):
            time_end = int(time.time() * 1000)

            if self.interaction_tracker:
                self.interaction_tracker.add_event("tool-result", {
                    "toolCallId": event["tool_call_id"],
                    "output": event.get("output")
                })

            part = ToolPart(
                id=existing.id,
                session_id=existing.session_id,
                message_id=existing.message_id,
                call_id=event["tool_call_id"],
                tool=existing.tool,
                state=ToolStateCompleted(
                    status=ToolStatus.COMPLETED,
                    input=event.get("input") or existing.state.input,
                    output=str(event["output"]) if event.get("output") else "",
                    title=event.get("metadata", {}).get("title", "") if event.get("metadata") else "",
                    time_start=existing.state.time_start,
                    time_end=time_end,
                    metadata=event.get("metadata"),
                ),
            )
            await self._update_part(part)

            # 更新工具调用记录
            if event["tool_call_id"] in self.interaction_tool_calls:
                record = self.interaction_tool_calls[event["tool_call_id"]]
                record.output = event.get("output")
                record.duration = time_end - existing.state.time_start

            del self.toolcalls[event["tool_call_id"]]

            # Trigger LSP auto-diagnostics for Write/Edit tools
            if existing.tool in ("write", "edit"):
                try:
                    from lsp.auto_diagnostic import get_auto_diagnostic
                except ImportError:
                    # LSP module not available, skip auto-diagnostics
                    pass
                else:
                    # Extract filepath from metadata or input
                    filepath = None
                    if event.get("metadata"):
                        filepath = event["metadata"].get("filepath")
                    elif event.get("input"):
                        filepath = event["input"].get("filePath")

                    if filepath:
                        auto_diag = get_auto_diagnostic()
                        # Run in background, don't await
                        asyncio.create_task(
                            auto_diag.trigger_diagnostic(
                                filepath=filepath,
                                tool_name=existing.tool,
                                session_id=self.session_id,
                            )
                        )

    async def _handle_tool_error(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        existing = self.toolcalls.get(event["tool_call_id"])
        if existing and isinstance(existing.state, (ToolStateRunning, ToolStatePending)):
            time_start = (
                existing.state.time_start
                if isinstance(existing.state, ToolStateRunning)
                else int(time.time() * 1000)
            )
            time_end = int(time.time() * 1000)

            if self.interaction_tracker:
                self.interaction_tracker.add_event("tool-error", {
                    "toolCallId": event["tool_call_id"],
                    "error": str(event["error"])
                })

            part = ToolPart(
                id=existing.id,
                session_id=existing.session_id,
                message_id=existing.message_id,
                call_id=event["tool_call_id"],
                tool=existing.tool,
                state=ToolStateError(
                    status=ToolStatus.ERROR,
                    input=event.get("input") or existing.state.input,
                    error=str(event["error"]),
                    time_start=time_start,
                    time_end=time_end,
                ),
            )
            await self._update_part(part)

            # 更新工具调用记录
            if event["tool_call_id"] in self.interaction_tool_calls:
                record = self.interaction_tool_calls[event["tool_call_id"]]
                record.error = str(event["error"])
                record.duration = time_end - time_start

            # 检查是否为权限错误
            error_type = type(event["error"]).__name__
            blocked = "Permission" in error_type or "Rejected" in error_type

            del self.toolcalls[event["tool_call_id"]]

            return {"blocked": blocked}

    async def _handle_text_start(self, event: Dict[str, Any]) -> None:
        if self.interaction_tracker:
            self.interaction_tracker.add_event("text-start")

        self.current_text = TextPart(
            id=self._generate_id("part"),
            session_id=self.session_id,
            message_id=self.assistant_message.id,
            text="",
            time=TimeInfo(start=int(time.time() * 1000)),
            metadata=event.get("provider_metadata"),
        )
        await self._update_part(self.current_text)

    async def _handle_text_delta(self, event: Dict[str, Any]) -> None:
        if self.current_text:
            self.current_text.text += event["text"]
            if event.get("provider_metadata"):
                self.current_text.metadata = event["provider_metadata"]

            if self.on_part_delta:
                await self.on_part_delta(
                    self.current_text.session_id,
                    self.current_text.message_id,
                    self.current_text.id,
                    "text",
                    event["text"],
                )

            # 收集追踪文本
            self.interaction_output_text += event["text"]

    async def _handle_text_end(self, event: Dict[str, Any]) -> None:
        if self.current_text:
            if self.interaction_tracker:
                self.interaction_tracker.add_event("text-end")

            self.current_text.text = self.current_text.text.rstrip()
            self.current_text.time.end = int(time.time() * 1000)
            if event.get("provider_metadata"):
                self.current_text.metadata = event["provider_metadata"]

            await self._update_part(self.current_text)
            self.current_text = None

    async def _handle_start_step(self, event: Dict[str, Any]) -> None:
        self.snapshot = event.get("snapshot")  # 从外部获取
        if self.interaction_tracker:
            self.interaction_tracker.add_event("start-step")

        part = StepStartPart(
            id=self._generate_id("part"),
            session_id=self.session_id,
            message_id=self.assistant_message.id,
            snapshot=self.snapshot,
        )
        await self._update_part(part)

    async def _handle_finish_step(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        usage = self._calculate_usage(event.get("usage"), event.get("provider_metadata"))

        if self.interaction_tracker:
            self.interaction_tracker.add_event("finish-step", {
                "finishReason": event["finish_reason"],
                "usage": event.get("usage")
            })

        # 更新消息
        self.assistant_message.finish = event["finish_reason"]
        self.assistant_message.tokens = usage
        if self.on_message_update:
            await self.on_message_update(self.assistant_message)

        # 创建完成部分
        part = StepFinishPart(
            id=self._generate_id("part"),
            session_id=self.session_id,
            message_id=self.assistant_message.id,
            reason=event["finish_reason"],
            snapshot=self.snapshot,
            tokens=usage,
        )
        await self._update_part(part)

        # 记录交互追踪
        if not self.interaction_has_tracked:
            usage_record = None
            if event.get("usage"):
                usage_record = TokenUsageRecord(
                    prompt_tokens=event["usage"].get("promptTokens", 0),
                    completion_tokens=event["usage"].get("completionTokens", 0),
                    total_tokens=event["usage"].get("totalTokens", 0),
                )

            if self.interaction_tracker:
                self.interaction_tracker.record_output(
                    text=self.interaction_output_text,
                    tool_calls=list(self.interaction_tool_calls.values()),
                    finish_reason=event["finish_reason"],
                    usage=usage_record,
                )
            self.interaction_has_tracked = True

        return {"snapshot": self.snapshot}

    async def _handle_finish(self, event: Dict[str, Any]) -> None:
        logger.debug("Stream finished", extra={"session_id": self.session_id})
        if self.interaction_tracker:
            self.interaction_tracker.add_event("finish")

    async def _handle_error_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        return {"error": event["error"]}

    def _calculate_usage(self, usage, provider_metadata) -> TokenUsage:
        """计算 token 使用"""
        if usage:
            total = usage.get("totalTokens")
            if total is None:
                total = usage.get("promptTokens", 0) + usage.get("completionTokens", 0)

            from session_management.types import TokenUsage
            return TokenUsage(
                input=usage.get("promptTokens", 0),
                output=usage.get("completionTokens", 0),
                reasoning=usage.get("reasoningTokens", 0),
                total=total,
                cache_read=usage.get("cacheReadTokens", 0),
                cache_write=usage.get("cacheWriteTokens", 0),
            )
        from session_management.types import TokenUsage
        return TokenUsage(input=0, output=0)


__all__ = ["EventHandler"]
