"""
消息过滤模块

实现上下文压缩后的消息过滤机制。

基于OpenCode的双标记系统：
1. CompactionPart - 标记压缩触发点（用户消息）
2. summary: true - 标记摘要完成（助手消息）

核心原理：标记-识别-截断
- 压缩时添加标记
- 过滤时识别标记
- 在标记处截断消息流
"""

from typing import List, Set, Generator
from .message_types import MessageWithParts, PartType, MessageRole


def filter_compacted(messages: List[MessageWithParts]) -> List[MessageWithParts]:
    """
    过滤已压缩的消息，只保留最后一次压缩后的消息

    算法步骤（对齐OpenCode实现）：

    第一步：正向遍历（从新到旧）
    - 遍历消息流，将每条消息添加到结果
    - 识别摘要消息（summary: true），记录其父用户消息ID
    - 遇到带CompactionPart的已标记用户消息时停止（压缩点）

    第二步：反转结果
    - 将结果反转为从旧到新的顺序
    - 只包含压缩点之后的消息

    示例：
        输入（从新到旧）:
        - msg-7: user "当前问题"
        - msg-6: assistant (finish)
        - msg-5: user [CompactionPart] ← 压缩点
        - msg-4: assistant (summary: true) ← 摘要标记
        - msg-3: user "旧问题"
        - msg-2: assistant

        输出（从旧到新）:
        - msg-4: assistant (summary: true)
        - msg-5: user [CompactionPart]
        - msg-6: assistant
        - msg-7: user

    Args:
        messages: 消息列表（从新到旧，DESC顺序）

    Returns:
        过滤后的消息列表（从旧到新，ASC顺序）
    """
    result: List[MessageWithParts] = []
    completed: Set[str] = set()  # 存储已压缩的用户消息ID

    # 第一步：正向遍历，识别压缩点
    for msg in messages:
        result.append(msg)  # 先添加到结果

        # 关键判断：是否到达压缩点？
        if msg.info.role == MessageRole.USER:
            # 检查是否为已标记的用户消息
            if msg.info.id in completed:
                # 检查是否包含CompactionPart
                has_compaction = any(
                    part.type == PartType.COMPACTION
                    for part in msg.parts
                )
                if has_compaction:
                    # 到达压缩点，停止遍历
                    break

        # 记录已完成压缩的用户消息
        if msg.info.role == MessageRole.ASSISTANT:
            # 检查是否为摘要消息
            is_summary = getattr(msg.info, 'summary', False)
            is_finished = getattr(msg.info, 'finish', None) is not None

            if is_summary and is_finished:
                # 标记其父用户消息为"已压缩"
                parent_id = getattr(msg.info, 'parent_id', None)
                if parent_id:
                    completed.add(parent_id)

    # 第二步：反转结果（从旧到新）
    result.reverse()
    return result


def filter_compacted_stream(stream: Generator[MessageWithParts, None, None]) -> List[MessageWithParts]:
    """
    从流式消息中过滤已压缩的消息

    Args:
        stream: 消息流生成器（从新到旧）

    Returns:
        过滤后的消息列表（从旧到新）
    """
    result: List[MessageWithParts] = []
    completed: Set[str] = set()

    for msg in stream:
        result.append(msg)

        # 检查压缩点
        if msg.info.role == MessageRole.USER and msg.info.id in completed:
            has_compaction = any(part.type == PartType.COMPACTION for part in msg.parts)
            if has_compaction:
                break

        # 记录摘要消息
        if msg.info.role == MessageRole.ASSISTANT:
            if getattr(msg.info, 'summary', False) and getattr(msg.info, 'finish', None):
                parent_id = getattr(msg.info, 'parent_id', None)
                if parent_id:
                    completed.add(parent_id)

    result.reverse()
    return result
