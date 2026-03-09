"""
解释器会话

管理单个会话的生命周期和状态。
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, AsyncGenerator, Optional, Callable, Awaitable
import json

from session_management import (
    AssistantMessage,
    UserMessage,
    ModelMessage,
    ModelInfo,
    AgentInfo,
    Part,
    MessageRole,
    TimeInfo,
)
from session_management import AbortSignal
from processor import SessionProcessor

from .config import InterpreterConfig

logger = logging.getLogger(__name__)


class InterpreterSession:
    """
    解释器会话

    职责：
    - 管理单个会话的状态
    - 协调 LLM 调用和处理器
    - 提供上下文管理
    """

    def __init__(
        self,
        interpreter: "OpenCodeInterpreter",
        session_id: str,
        agent: AgentInfo,
        model: ModelInfo,
    ):
        self.interpreter = interpreter
        self.session_id = session_id
        self.agent = agent
        self.model = model

        # 会话状态
        self.messages: List[ModelMessage] = []
        self.tools: Dict[str, Any] = {}
        self.parts: List[Part] = []

        # 内部组件
        self.abort_signal = AbortSignal()
        self._current_message: Optional[AssistantMessage] = None

        # 回调
        self.on_part_update: Optional[Callable[[Part], Awaitable[None]]] = None
        self.on_part_delta: Optional[Callable[[str, str, str, str], Awaitable[None]]] = None
        self.on_message_update: Optional[Callable[[AssistantMessage], Awaitable[None]]] = None
        self.on_snapshot: Optional[Callable[[], Awaitable[Optional[str]]]] = None
        self.on_patch: Optional[Callable[[str], Awaitable[Optional[List[str]]]]] = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def process(
        self,
        messages: List[ModelMessage],
        tools: Dict[str, Any],
        system: List[str],
        user_message: Optional[UserMessage] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        处理用户输入并生成响应
        """
        if not self.interpreter._llm:
            raise RuntimeError("Interpreter not initialized")

        # 更新状态
        self.messages = messages
        self.tools = tools

        # 创建助手消息
        self._current_message = AssistantMessage(
            id=self._generate_id("message"),
            session_id=self.session_id,
            role=MessageRole.ASSISTANT,
            time=TimeInfo(created=int(time.time() * 1000)),
            parent_id="",
            model_id=self.model.model_id,
            provider_id=self.model.provider_id,
            mode=self.agent.mode,
            agent=self.agent.name,
        )

        # 创建处理器
        processor = SessionProcessor(
            assistant_message=self._current_message,
            session_id=self.session_id,
            model=self.model,
            abort=self.abort_signal,
            on_part_update=self._on_part_update,
            on_part_delta=self._on_part_delta,
            on_message_update=self._on_message_update,
            on_snapshot=self._on_snapshot,
            on_patch=self._on_patch,
            on_parts_get=self._on_parts_get,
        )

        # 执行 LLM 调用循环
        from ai_sdk.message import Message

        max_iterations = 10
        iteration = 0
        all_collected_text = []

        while iteration < max_iterations:
            iteration += 1

            # 转换 ModelMessage 到 ai_sdk.Message 格式
            converted_messages = []
            for msg in messages:
                if msg.role == "user":
                    converted_messages.append(Message.user(msg.content))
                elif msg.role == "assistant":
                    converted_messages.append(Message.assistant(msg.content))
                elif msg.role == "system":
                    converted_messages.append(Message.system(msg.content))
                elif msg.role == "tool":
                    # 将 tool 消息转换为 user 消息（包含工具结果）
                    converted_messages.append(Message.user(f"Tool result: {msg.content}"))

            # 调试：打印工具信息
            print(f"\n[工具调试] 传递给 LLM 的工具数量: {len(tools) if tools else 0}")
            if tools:
                print(f"[工具调试] 工具列表: {list(tools.keys())}")
            else:
                print(f"[工具调试] 警告：没有工具被传递给 LLM！")

            stream = self.interpreter._llm.stream(
                messages=converted_messages,
                tools=tools,
                system=system,
                temperature=self.agent.temperature or self.interpreter.config.temperature,
                tool_choice=self.interpreter.config.tool_choice,
            )

            # 收集本轮的工具结果和 finishReason
            tool_results = []  # 存储 (tool_call_id, tool_name, result)
            finish_reason = None

            # 转换并转发 StreamChunk
            async def convert_and_forward_stream():
                """将 StreamChunk 转换为事件字典并转发"""
                nonlocal finish_reason, tool_results
                async for chunk in stream:
                    event = None

                    # 文本增量
                    if chunk.delta:
                        event = {"type": "text-delta", "delta": chunk.delta}
                        yield event

                    # 工具调用
                    if chunk.tool_calls:
                        import json
                        for tool_call in chunk.tool_calls:
                            # 解析工具调用格式
                            func_data = tool_call.get("function", {})
                            tool_name = func_data.get("name", "")
                            arguments_str = func_data.get("arguments", "{}")

                            # 解析参数
                            tool_input = {}
                            if arguments_str:
                                try:
                                    tool_input = json.loads(arguments_str)
                                except json.JSONDecodeError:
                                    tool_input = {"arguments": arguments_str}

                            # 生成工具调用 ID
                            tool_call_id = tool_call.get("id", f"call_{int(time.time() * 1000)}")

                            # 发送 tool-input-start 事件（创建 tool part）
                            yield {
                                "type": "tool-input-start",
                                "id": tool_call_id,
                                "tool_name": tool_name,
                            }

                            # 发送 tool-call 事件（更新为 running 状态）
                            event = {
                                "type": "tool-call",
                                "tool_call_id": tool_call_id,
                                "tool_name": tool_name,
                                "input": tool_input,
                                "provider_metadata": tool_call,
                            }
                            yield event

                            # 执行工具
                            tool = self.tools.get(tool_name)
                            if tool and hasattr(tool, 'execute'):
                                try:
                                    # Create ToolContext for ToolDefinition tools
                                    from tool.base import ToolContext
                                    tool_ctx = ToolContext(
                                        session_id=self.session_id,
                                        message_id=self._current_message.id,
                                        agent=self.agent.name,
                                        abort_signal=self.abort_signal,
                                    )

                                    result = await tool.execute(tool_input, tool_ctx)

                                    # 收集工具结果（tool_call_id, tool_name, result）
                                    tool_result_str = str(result.output) if hasattr(result, 'output') else str(result)
                                    tool_results.append((tool_call_id, tool_name, tool_result_str))

                                    # 发送 tool-result 事件
                                    yield {
                                        "type": "tool-result",
                                        "tool_call_id": tool_call_id,
                                        "output": tool_result_str,
                                        "metadata": {"title": f"Tool {tool_name} executed"},
                                    }
                                except Exception as e:
                                    # 发送 tool-error 事件
                                    yield {
                                        "type": "tool-error",
                                        "tool_call_id": tool_call_id,
                                        "error": str(e),
                                    }

                    # 完成
                    if chunk.finish_reason:
                        finish_reason = chunk.finish_reason
                        event = {
                            "type": "finish",
                            "finish_reason": chunk.finish_reason,
                            "usage": chunk.usage or {},
                        }
                        yield event


            # 收集事件和文本
            events = []
            collected_text = []
            async for event in convert_and_forward_stream():
                events.append(event)

                # Forward all events to the user, not just text-delta
                event_type = event.get("type")
                if event_type == "text-delta":
                    delta = event.get("delta")
                    collected_text.append(delta)
                    all_collected_text.append(delta)
                    yield {"type": "text", "text": delta}
                elif event_type in ("tool-input-start", "tool-call", "tool-result", "tool-error", "error", "finish"):
                    # Forward tool-related and error events
                    yield event
                elif event_type == "processing":
                    # Forward processing events
                    yield event

            # 根据 finishReason 决定是否继续循环
            if finish_reason == "tool_calls":
                # 为每个工具结果创建一个 tool 消息，包含工具名称
                for tool_call_id, tool_name, result in tool_results:
                    tool_msg = ModelMessage(
                        role="tool",
                        content=f"[Tool: {tool_name}]\n{result}",
                        tool_call_id=tool_call_id
                    )
                    messages.append(tool_msg)
                    # 调试：打印工具结果
                    logger.debug(f"Added tool result: tool={tool_name}, result={result[:100]}...")
                # 继续循环
                logger.debug(f"Continuing loop, iteration={iteration}, finish_reason={finish_reason}")
                continue
            elif finish_reason in ("stop", "length"):
                # 退出循环
                break
            elif finish_reason == "unknown":
                # 重试：继续循环
                continue
            else:
                # 未知情况，退出循环
                break

        # 处理收集的事件
        async def replay_events():
            for event in events:
                yield event

        result = await processor.process_stream(replay_events())

        # 创建助手消息用于历史记录
        assistant_model_message = ModelMessage(
            role="assistant",
            content="".join(all_collected_text),
        )

        # 返回最终结果
        yield {
            "type": "result",
            "result": result,
            "message": assistant_model_message,
        }

    def _generate_id(self, prefix: str) -> str:
        timestamp = int(time.time() * 1000)
        random = hash(id(self)) % 10000
        return f"{prefix}_{timestamp}_{random}"

    async def _on_part_update(self, part: Part) -> None:
        self.parts.append(part)
        if self.on_part_update:
            await self.on_part_update(part)

    async def _on_part_delta(self, session_id: str, message_id: str, part_id: str, field: str, delta: str) -> None:
        if self.on_part_delta:
            await self.on_part_delta(session_id, message_id, part_id, field, delta)

    async def _on_message_update(self, message: AssistantMessage) -> None:
        if self.on_message_update:
            await self.on_message_update(message)

    async def _on_snapshot(self) -> Optional[str]:
        if self.on_snapshot:
            return await self.on_snapshot()
        return None

    async def _on_patch(self, patch: str) -> Optional[List[str]]:
        if self.on_patch:
            return await self.on_patch(patch)
        return None

    async def _on_parts_get(self) -> List[Part]:
        return self.parts

    def abort(self) -> None:
        self.abort_signal.abort()


__all__ = ["InterpreterSession"]
