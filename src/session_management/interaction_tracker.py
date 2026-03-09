"""
交互追踪器模块

跟踪和记录模型交互的详细信息，包括输入、输出和错误。
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class InteractionModel:
    """模型信息"""
    provider_id: str
    model_id: str


@dataclass
class InteractionAgent:
    """代理信息"""
    name: str
    mode: str


@dataclass
class InteractionInput:
    """交互输入"""
    session_id: str
    timestamp: int
    model: InteractionModel
    agent: InteractionAgent
    system: List[str]
    messages: List[Dict[str, Any]]
    tools: List[Dict[str, Any]]  # 完整工具信息：name, description, inputSchema
    tool_choice: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[float] = None


@dataclass
class ToolCallRecord:
    """工具调用记录"""
    id: str
    tool_name: str
    input: Dict[str, Any]
    output: Optional[Any] = None
    error: Optional[str] = None
    duration: Optional[int] = None


@dataclass
class TokenUsageRecord:
    """Token使用记录"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class EventRecord:
    """事件记录"""
    type: str
    timestamp: int
    data: Optional[Dict[str, Any]] = None


@dataclass
class InteractionOutput:
    """交互输出"""
    timestamp: int
    duration: int
    text: str
    tool_calls: List[ToolCallRecord]
    finish_reason: str
    usage: Optional[TokenUsageRecord] = None
    events: Optional[List[EventRecord]] = None


@dataclass
class Interaction:
    """交互记录"""
    id: str
    input: InteractionInput
    output: Optional[InteractionOutput] = None
    error: Optional[str] = None


class InteractionTracker:
    """
    交互追踪器

    记录模型交互的完整生命周期，包括：
    - 输入参数（系统提示、消息、工具等）
    - 输出结果（文本、工具调用、Token使用）
    - 错误信息
    - 时间统计
    - 事件流

    示例：
        ```python
        tracker = InteractionTracker(log_dir="./logs/interactions")

        # 开始追踪
        interaction_id = tracker.start(
            session_id="session_123",
            model=InteractionModel(provider_id="anthropic", model_id="claude-3-5-sonnet-20241022"),
            agent=InteractionAgent(name="planner", mode="plan"),
            system=["You are a helpful assistant"],
            messages=[{"role": "user", "content": "Hello"}],
            tools=[
                {
                    "name": "Read",
                    "description": "Reads a file from the local filesystem",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"file_path": {"type": "string"}},
                        "required": ["file_path"]
                    }
                }
            ],
        )

        # 记录事件
        tracker.add_event("text-start")
        tracker.add_event("text-delta", {"text": "Hello"})

        # 记录输出
        tracker.record_output(
            text="Hello! How can I help you?",
            tool_calls=[],
            finish_reason="stop",
            usage=TokenUsageRecord(
                prompt_tokens=10,
                completion_tokens=9,
                total_tokens=19
            )
        )

        # 保存记录
        await tracker.save()
        ```
    """

    def __init__(self, log_dir: Optional[str] = None):
        """
        初始化交互追踪器

        Args:
            log_dir: 日志目录路径，默认为 ./logs/interactions
        """
        if log_dir is None:
            log_dir = os.path.join(os.getcwd(), "logs", "interactions")

        self.log_dir = Path(log_dir)
        self._current_interaction: Optional[Interaction] = None
        self._interaction_start_time: int = 0

        # 确保目录存在
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def start(
        self,
        session_id: str,
        model: InteractionModel,
        agent: InteractionAgent,
        system: List[str],
        messages: List[Dict[str, Any]],
        tools: List[str],
        tool_choice: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[float] = None,
    ) -> str:
        """
        开始追踪新的交互

        Args:
            session_id: 会话ID
            model: 模型信息
            agent: 代理信息
            system: 系统提示列表
            messages: 消息列表
            tools: 可用工具列表
            tool_choice: 工具选择策略
            temperature: 温度参数
            top_p: Top-P参数
            top_k: Top-K参数

        Returns:
            交互ID
        """
        import time
        interaction_id = f"interaction_{int(time.time() * 1000)}_{id(session_id)}"
        self._interaction_start_time = int(time.time() * 1000)

        self._current_interaction = Interaction(
            id=interaction_id,
            input=InteractionInput(
                session_id=session_id,
                timestamp=self._interaction_start_time,
                model=model,
                agent=agent,
                system=system,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
            )
        )

        logger.debug(
            f"Started interaction tracking",
            extra={
                "interaction_id": interaction_id,
                "session_id": session_id,
                "model": model.model_id,
            }
        )

        return interaction_id

    def record_output(
        self,
        text: str,
        tool_calls: List[ToolCallRecord],
        finish_reason: str,
        usage: Optional[TokenUsageRecord] = None,
        events: Optional[List[EventRecord]] = None,
    ) -> None:
        """
        记录交互输出

        Args:
            text: 输出文本
            tool_calls: 工具调用列表
            finish_reason: 完成原因
            usage: Token使用统计
            events: 事件流记录
        """
        if self._current_interaction is None:
            logger.warning("No active interaction to record output")
            return

        import time
        now = int(time.time() * 1000)

        self._current_interaction.output = InteractionOutput(
            timestamp=now,
            duration=now - self._interaction_start_time,
            text=text,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
            events=events,
        )

        logger.debug(
            f"Recorded interaction output",
            extra={
                "interaction_id": self._current_interaction.id,
                "duration": self._current_interaction.output.duration,
                "finish_reason": finish_reason,
            }
        )

    def record_error(self, error: str) -> None:
        """
        记录交互错误

        Args:
            error: 错误信息
        """
        if self._current_interaction is None:
            logger.warning("No active interaction to record error")
            return

        self._current_interaction.error = error

        logger.debug(
            f"Recorded interaction error",
            extra={
                "interaction_id": self._current_interaction.id,
                "error": error,
            }
        )

    def add_event(self, event_type: str, data: Optional[Dict[str, Any]] = None) -> None:
        """
        添加事件记录

        Args:
            event_type: 事件类型（如 "text-delta", "tool-call", "tool-result"）
            data: 事件数据
        """
        if self._current_interaction is None:
            logger.warning("No active interaction to add event")
            return

        import time
        event = EventRecord(
            type=event_type,
            timestamp=int(time.time() * 1000),
            data=data,
        )

        # 初始化 output 和 events 列表（如果需要）
        if self._current_interaction.output is None:
            self._current_interaction.output = InteractionOutput(
                timestamp=0,
                duration=0,
                text="",
                tool_calls=[],
                finish_reason="",
                events=[],
            )

        if self._current_interaction.output.events is None:
            self._current_interaction.output.events = []

        self._current_interaction.output.events.append(event)

    async def save(self) -> None:
        """
        保存交互记录到文件

        交互记录保存为JSON文件，文件名为 `{interaction_id}.json`
        """
        if self._current_interaction is None:
            logger.warning("No active interaction to save")
            return

        try:
            filename = f"{self._current_interaction.id}.json"
            filepath = self.log_dir / filename

            # 转换为可序列化的字典
            data = self._serialize_interaction(self._current_interaction)

            # 写入文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(
                f"Saved interaction",
                extra={
                    "interaction_id": self._current_interaction.id,
                    "filepath": str(filepath),
                    "duration": self._current_interaction.output.duration if self._current_interaction.output else None,
                }
            )
        except Exception as e:
            logger.error(
                f"Failed to save interaction",
                extra={
                    "error": str(e),
                    "interaction_id": self._current_interaction.id if self._current_interaction else None,
                },
                exc_info=True
            )
        finally:
            self._current_interaction = None

    def _serialize_interaction(self, interaction: Interaction) -> Dict[str, Any]:
        """序列化交互对象为字典（使用camelCase）"""
        return {
            "id": interaction.id,
            "input": {
                "sessionID": interaction.input.session_id,
                "timestamp": interaction.input.timestamp,
                "model": {
                    "providerID": interaction.input.model.provider_id,
                    "modelID": interaction.input.model.model_id,
                },
                "agent": {
                    "name": interaction.input.agent.name,
                    "mode": interaction.input.agent.mode,
                },
                "system": interaction.input.system,
                "messages": interaction.input.messages,
                "tools": interaction.input.tools,
                "toolChoice": interaction.input.tool_choice,
                "temperature": interaction.input.temperature,
                "topP": interaction.input.top_p,
                "topK": interaction.input.top_k,
            },
            "output": {
                "timestamp": interaction.output.timestamp,
                "duration": interaction.output.duration,
                "text": interaction.output.text,
                "toolCalls": [
                    {
                        "id": tc.id,
                        "toolName": tc.tool_name,
                        "input": tc.input,
                        "output": tc.output,
                        "error": tc.error,
                        "duration": tc.duration,
                    }
                    for tc in interaction.output.tool_calls
                ],
                "finishReason": interaction.output.finish_reason,
                "usage": {
                    "promptTokens": interaction.output.usage.prompt_tokens,
                    "completionTokens": interaction.output.usage.completion_tokens,
                    "totalTokens": interaction.output.usage.total_tokens,
                } if interaction.output.usage else None,
                "events": [
                    {
                        "type": e.type,
                        "timestamp": e.timestamp,
                        "data": e.data,
                    }
                    for e in interaction.output.events
                ] if interaction.output.events else None,
            } if interaction.output else None,
            "error": interaction.error,
        }

    async def list_interactions(self) -> List[Interaction]:
        """
        获取所有交互记录

        Returns:
            交互记录列表，按时间戳排序
        """
        try:
            interactions = []

            for filepath in self.log_dir.glob("*.json"):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        interaction = self._deserialize_interaction(data)
                        interactions.append(interaction)
                except Exception as e:
                    logger.warning(
                        f"Failed to parse interaction file",
                        extra={"filepath": str(filepath), "error": str(e)}
                    )

            # 按时间戳排序
            interactions.sort(key=lambda x: x.input.timestamp)
            return interactions

        except Exception as e:
            logger.error(f"Failed to list interactions", extra={"error": str(e)}, exc_info=True)
            return []

    def _deserialize_interaction(self, data: Dict[str, Any]) -> Interaction:
        """从字典反序列化交互对象（支持camelCase和snake_case）"""
        input_data = data["input"]
        output_data = data.get("output")

        # 支持两种命名格式
        def get_field(obj: Dict, camel: str, snake: str):
            return obj.get(camel) or obj.get(snake)

        return Interaction(
            id=data["id"],
            input=InteractionInput(
                session_id=get_field(input_data, "sessionID", "session_id"),
                timestamp=input_data["timestamp"],
                model=InteractionModel(
                    provider_id=get_field(input_data["model"], "providerID", "provider_id"),
                    model_id=get_field(input_data["model"], "modelID", "model_id"),
                ),
                agent=InteractionAgent(
                    name=input_data["agent"]["name"],
                    mode=input_data["agent"]["mode"],
                ),
                system=input_data["system"],
                messages=input_data["messages"],
                tools=input_data["tools"],
                tool_choice=get_field(input_data, "toolChoice", "tool_choice"),
                temperature=input_data.get("temperature"),
                top_p=get_field(input_data, "topP", "top_p"),
                top_k=get_field(input_data, "topK", "top_k"),
            ),
            output=InteractionOutput(
                timestamp=output_data["timestamp"],
                duration=output_data["duration"],
                text=output_data["text"],
                tool_calls=[
                    ToolCallRecord(
                        id=tc["id"],
                        tool_name=get_field(tc, "toolName", "tool_name"),
                        input=tc["input"],
                        output=tc.get("output"),
                        error=tc.get("error"),
                        duration=tc.get("duration"),
                    )
                    for tc in get_field(output_data, "toolCalls", "tool_calls") or []
                ],
                finish_reason=get_field(output_data, "finishReason", "finish_reason"),
                usage=TokenUsageRecord(
                    prompt_tokens=get_field(output_data["usage"], "promptTokens", "prompt_tokens"),
                    completion_tokens=get_field(output_data["usage"], "completionTokens", "completion_tokens"),
                    total_tokens=get_field(output_data["usage"], "totalTokens", "total_tokens"),
                ) if output_data.get("usage") else None,
                events=[
                    EventRecord(
                        type=e["type"],
                        timestamp=e["timestamp"],
                        data=e.get("data"),
                    )
                    for e in output_data.get("events") or []
                ] if output_data.get("events") else None,
            ) if output_data else None,
            error=data.get("error"),
        )

    async def get_interactions_by_session(self, session_id: str) -> List[Interaction]:
        """
        根据会话ID获取交互记录

        Args:
            session_id: 会话ID

        Returns:
            该会话的所有交互记录
        """
        all_interactions = await self.list_interactions()
        return [i for i in all_interactions if i.input.session_id == session_id]

    async def export_to_markdown(self, session_id: Optional[str] = None) -> str:
        """
        导出交互记录为Markdown格式

        Args:
            session_id: 可选的会话ID，如果提供则只导出该会话的记录

        Returns:
            Markdown格式的交互记录
        """
        interactions = (
            await self.get_interactions_by_session(session_id)
            if session_id
            else await self.list_interactions()
        )

        md = "# OpenCode Interaction Log\n\n"
        md += f"Generated: {datetime.now().isoformat()}\n"
        md += f"Total Interactions: {len(interactions)}\n\n"

        for interaction in interactions:
            md += "---\n\n"
            md += f"## Interaction {interaction.id}\n\n"
            md += f"**Session ID:** `{interaction.input.session_id}`\n\n"
            md += f"**Time:** {datetime.fromtimestamp(interaction.input.timestamp / 1000).isoformat()}\n\n"
            md += f"**Model:** {interaction.input.model.provider_id}/{interaction.input.model.model_id}\n\n"
            md += f"**Agent:** {interaction.input.agent.name} ({interaction.input.agent.mode})\n\n"

            if interaction.output and interaction.output.duration:
                md += f"**Duration:** {interaction.output.duration}ms\n\n"

            # Input section
            md += "### Input\n\n"
            md += f"**System Prompts:** {len(interaction.input.system)} prompts\n\n"
            md += f"**Messages:** {len(interaction.input.messages)} messages\n\n"
            md += f"**Tools:** {', '.join(interaction.input.tools) or 'none'}\n\n"

            # Messages detail
            md += "#### Messages Detail\n\n"
            for msg in interaction.input.messages:
                md += f"**[{msg['role']}]**\n\n"
                content = msg.get('content')
                if isinstance(content, str):
                    preview = content[:200] + "..." if len(content) > 200 else content
                    md += f'"{preview}"\n\n'
                elif isinstance(content, list):
                    for part in content:
                        if part.get('type') == 'text':
                            text = part.get('text', '')
                            preview = text[:200] + "..." if len(text) > 200 else text
                            md += f"- Text: \"{preview}\"\n\n"
                        elif part.get('type') == 'tool-call':
                            md += f"- Tool Call: {part.get('toolName', 'unknown')}\n\n"
                        elif part.get('type') == 'tool-result':
                            md += f"- Tool Result: {part.get('toolName', 'unknown')}\n\n"

            # Output section
            if interaction.output:
                md += "### Output\n\n"
                md += f"**Finish Reason:** {interaction.output.finish_reason}\n\n"

                if interaction.output.text:
                    md += "#### Response Text\n\n"
                    md += f"```\n{interaction.output.text}\n```\n\n"

                if interaction.output.tool_calls:
                    md += "#### Tool Calls\n\n"
                    for tc in interaction.output.tool_calls:
                        md += f"- **{tc.tool_name}** (ID: {tc.id})\n"
                        md += f"  ```json\n{json.dumps(tc.input, indent=2)}\n```\n\n"

                if interaction.output.usage:
                    md += "#### Token Usage\n\n"
                    md += f"- Prompt Tokens: {interaction.output.usage.prompt_tokens}\n"
                    md += f"- Completion Tokens: {interaction.output.usage.completion_tokens}\n"
                    md += f"- Total Tokens: {interaction.output.usage.total_tokens}\n\n"

            # Error section
            if interaction.error:
                md += "### Error\n\n"
                md += f"```\n{interaction.error}\n```\n\n"

        return md


# 全局单例实例
_global_tracker: Optional[InteractionTracker] = None


def get_tracker(log_dir: Optional[str] = None) -> InteractionTracker:
    """获取全局交互追踪器实例"""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = InteractionTracker(log_dir)
    return _global_tracker


# 便捷函数
def start_tracking(
    session_id: str,
    model: InteractionModel,
    agent: InteractionAgent,
    system: List[str],
    messages: List[Dict[str, Any]],
    tools: List[str],
    **kwargs
) -> str:
    """开始追踪交互（使用全局追踪器）"""
    tracker = get_tracker()
    return tracker.start(
        session_id=session_id,
        model=model,
        agent=agent,
        system=system,
        messages=messages,
        tools=tools,
        **kwargs
    )


def record_output(
    text: str,
    tool_calls: List[ToolCallRecord],
    finish_reason: str,
    usage: Optional[TokenUsageRecord] = None,
    events: Optional[List[EventRecord]] = None,
) -> None:
    """记录交互输出（使用全局追踪器）"""
    tracker = get_tracker()
    tracker.record_output(text, tool_calls, finish_reason, usage, events)


def record_error(error: str) -> None:
    """记录交互错误（使用全局追踪器）"""
    tracker = get_tracker()
    tracker.record_error(error)


async def save_tracking() -> None:
    """保存交互记录（使用全局追踪器）"""
    tracker = get_tracker()
    await tracker.save()
