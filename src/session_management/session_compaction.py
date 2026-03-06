"""
会话压缩模块

提供会话上下文压缩功能，当token使用接近上下文窗口限制时自动触发。
"""

import logging
from typing import List, Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass
from enum import Enum

from .message_types import (
    MessageWithParts,
    Part,
    ToolPart,
    TokenUsage,
    ModelInfo,
    Message,
    UserMessage,
    AssistantMessage,
    ToolStatus,
)

logger = logging.getLogger(__name__)


class CompactionResult(str, Enum):
    """压缩结果"""
    CONTINUE = "continue"
    STOP = "stop"


@dataclass
class CompactionConfig:
    """压缩配置"""
    auto: bool = True
    reserved: int = 20000  # 保留的token数量


class SessionCompaction:
    """
    会话压缩处理器

    功能：
    - 检测上下文是否溢出（接近token限制）
    - 修剪旧的工具调用输出
    - 生成会话摘要以减少上下文大小

    常量：
        COMPACTION_BUFFER: 压缩缓冲区大小（token）
        PRUNE_MINIMUM: 最小修剪量（token）
        PRUNE_PROTECT: 保护的token数量
        PRUNE_PROTECTED_TOOLS: 被保护的工具列表（不会被修剪）

    示例：
        ```python
        compaction = SessionCompaction(
            model_limit=ModelLimits(max_context=200000, max_output=8192),
            config=CompactionConfig(auto=True, reserved=20000)
        )

        # 检查是否需要压缩
        if await compaction.is_overflow(tokens, model):
            # 执行修剪
            await compaction.prune(session_id)

            # 生成摘要
            result = await compaction.process(
                parent_id=parent_id,
                messages=messages,
                session_id=session_id,
                abort=abort_signal,
            )
        ```
    """

    COMPACTION_BUFFER = 20000
    PRUNE_MINIMUM = 20000
    PRUNE_PROTECT = 40000
    PRUNE_PROTECTED_TOOLS = ["skill"]

    def __init__(
        self,
        model_limit: 'ModelLimits',
        config: Optional[CompactionConfig] = None,
        max_output_tokens: int = 8192,
    ):
        """
        初始化会话压缩器

        Args:
            model_limit: 模型限制
            config: 压缩配置
            max_output_tokens: 最大输出token数
        """
        self.model_limit = model_limit
        self.config = config or CompactionConfig()
        self.max_output_tokens = max_output_tokens

    async def is_overflow(
        self,
        tokens: TokenUsage,
        model: ModelInfo,
    ) -> bool:
        """
        检查token使用是否溢出

        Args:
            tokens: Token使用统计
            model: 模型信息

        Returns:
            是否溢出（需要压缩）
        """
        if not self.config.auto:
            return False

        context = self.model_limit.max_context
        if context == 0:
            return False

        # 计算总token使用
        count = (
            tokens.total or
            tokens.input + tokens.output + tokens.cache_read + tokens.cache_write
        )

        # 计算可用token
        reserved = self.config.reserved
        if self.model_limit.max_input:
            usable = self.model_limit.max_input - reserved
        else:
            usable = context - self.max_output_tokens

        return count >= usable

    async def prune(self, session_id: str) -> None:
        """
        修剪旧的工具调用输出

        从后向前遍历消息，直到找到40000 token的工具调用，
        然后清除更早的工具调用输出。

        Args:
            session_id: 会话ID
        """
        if not self.config.auto:
            return

        logger.info("Pruning session", extra={"session_id": session_id})

        # 获取消息（需要从数据库或存储中获取）
        # 这里是简化版本，实际实现需要从session存储中获取
        messages: List[MessageWithParts] = []  # TODO: 从存储获取

        total = 0
        pruned = 0
        to_prune: List[ToolPart] = []
        turns = 0

        # 从后向前遍历
        for msg_index in range(len(messages) - 1, -1, -1):
            msg = messages[msg_index]
            if msg.info.role == "user":
                turns += 1
            if turns < 2:
                continue

            # 如果遇到摘要消息，停止
            if isinstance(msg.info, AssistantMessage) and msg.info.summary:
                break

            # 遍历部分
            for part_index in range(len(msg.parts) - 1, -1, -1):
                part = msg.parts[part_index]
                if isinstance(part, ToolPart):
                    if part.state.status == ToolStatus.COMPLETED:
                        # 跳过被保护的工具
                        if part.tool in self.PRUNE_PROTECTED_TOOLS:
                            continue

                        # 如果已经压缩过，停止
                        if isinstance(part.state, ToolStateCompleted) and part.state.time_compacted:
                            break

                        # 估算token数
                        estimate = self._estimate_tokens(part.state.output)
                        total += estimate

                        if total > self.PRUNE_PROTECT:
                            pruned += estimate
                            to_prune.append(part)

        logger.info("Found parts to prune", extra={"pruned": pruned, "total": total})

        if pruned > self.PRUNE_MINIMUM:
            for part in to_prune:
                if isinstance(part.state, ToolStateCompleted):
                    # 标记为已压缩
                    part.state.time_compacted = int(time.time() * 1000)
                    # TODO: 更新到存储

            logger.info("Pruned parts", extra={"count": len(to_prune)})

    async def process(
        self,
        parent_id: str,
        messages: List[MessageWithParts],
        session_id: str,
        abort: 'AbortSignal',
        auto: bool = True,
    ) -> CompactionResult:
        """
        执行会话压缩

        生成会话摘要以减少上下文大小。

        Args:
            parent_id: 父消息ID
            messages: 消息列表
            session_id: 会话ID
            abort: 中止信号
            auto: 是否自动继续

        Returns:
            压缩结果
        """
        # 找到用户消息
        user_message: Optional[UserMessage] = None
        for msg in reversed(messages):
            if msg.info.id == parent_id and isinstance(msg.info, UserMessage):
                user_message = msg.info
                break

        if not user_message:
            logger.error("User message not found for compaction")
            return CompactionResult.STOP

        # 生成摘要提示
        prompt_text = self._get_compaction_prompt()

        # 构建消息历史
        model_messages = self._to_model_messages(messages, model=user_message.model)

        # 添加压缩提示
        model_messages.append({
            "role": "user",
            "content": prompt_text,
        })

        # TODO: 调用LLM生成摘要
        # 这里需要集成LLM接口

        # 如果自动继续，添加继续消息
        if auto:
            # TODO: 创建继续消息
            pass

        return CompactionResult.CONTINUE

    def _get_compaction_prompt(self) -> str:
        """获取压缩提示"""
        return """Provide a detailed prompt for continuing our conversation above.
Focus on information that would be helpful for continuing the conversation, including what we did, what we're doing, which files we're working on, and what we're going to do next.
The summary that you construct will be used so that another agent can read it and continue the work.

When constructing the summary, try to stick to this template:
---
## Goal

[What goal(s) is the user trying to accomplish?]

## Instructions

- [What important instructions did the user give you that are relevant]
- [If there is a plan or spec, include information about it so next agent can continue using it]

## Discoveries

[What notable things were learned during this conversation that would be useful for the next agent to know when continuing the work]

## Accomplished

[What work has been completed, what work is still in progress, and what work is left?]

## Relevant files / directories

[Construct a structured list of relevant files that have been read, edited, or created that pertain to the task at hand. If all the files in a directory are relevant, include the path to the directory.]
---"""

    def _estimate_tokens(self, text: str) -> int:
        """
        估算文本的token数

        简单估算：英文约4字符/token，中文约1.5字符/token
        """
        # 简化估算：每4个字符约1个token
        return len(text) // 4

    def _to_model_messages(
        self,
        messages: List[MessageWithParts],
        model: ModelInfo,
    ) -> List[Dict[str, Any]]:
        """
        将消息转换为模型格式

        Args:
            messages: 消息列表
            model: 模型信息

        Returns:
            模型消息列表
        """
        result = []

        for msg in messages:
            if not msg.parts:
                continue

            if isinstance(msg.info, UserMessage):
                content = []
                for part in msg.parts:
                    if part.type == "text" and not getattr(part, "ignored", False):
                        content.append({
                            "type": "text",
                            "text": part.text,
                        })
                    elif part.type == "compaction":
                        content.append({
                            "type": "text",
                            "text": "What did we do so far?",
                        })
                    elif part.type == "subtask":
                        content.append({
                            "type": "text",
                            "text": "The following tool was executed by the user",
                        })

                if content:
                    result.append({
                        "role": "user",
                        "content": content,
                    })

            elif isinstance(msg.info, AssistantMessage):
                # 跳过有错误的消息
                if msg.info.error:
                    continue

                content = []
                for part in msg.parts:
                    if part.type == "text":
                        content.append({
                            "type": "text",
                            "text": part.text,
                        })
                    elif part.type == "tool":
                        if isinstance(part.state, ToolStateCompleted):
                            # 检查是否已压缩
                            output_text = (
                                "[Old tool result content cleared]"
                                if part.state.time_compacted
                                else part.state.output
                            )

                            content.append({
                                "type": "tool-result",
                                "tool_name": part.tool,
                                "tool_call_id": part.call_id,
                                "output": output_text,
                            })

                if content:
                    result.append({
                        "role": "assistant",
                        "content": content,
                    })

        return result


@dataclass
class ModelLimits:
    """模型限制"""
    max_context: int
    max_output: int
    max_input: Optional[int] = None


import time


# 便捷函数
async def check_overflow(
    tokens: TokenUsage,
    model: ModelInfo,
    model_limit: ModelLimits,
    config: Optional[CompactionConfig] = None,
    max_output_tokens: int = 8192,
) -> bool:
    """检查是否溢出（便捷函数）"""
    compaction = SessionCompaction(model_limit, config, max_output_tokens)
    return await compaction.is_overflow(tokens, model)


async def prune_session(
    session_id: str,
    model_limit: ModelLimits,
    config: Optional[CompactionConfig] = None,
    max_output_tokens: int = 8192,
) -> None:
    """修剪会话（便捷函数）"""
    compaction = SessionCompaction(model_limit, config, max_output_tokens)
    await compaction.prune(session_id)
