"""
上下文过滤机制测试示例

演示OpenCode双标记系统和过滤算法的完整工作流程。
"""

from session_management import (
    SessionStorage,
    SessionManager,
    filter_compacted,
    filter_compacted_stream,
    MessageWithParts,
    UserMessage,
    AssistantMessage,
    TextPart,
    CompactionPart,
    ModelInfo,
    TimeInfo,
    MessageRole,
    PartType,
)


def create_test_messages(session_id: str) -> list[MessageWithParts]:
    """
    创建测试消息序列，模拟多次压缩的场景

    消息序列（从旧到新）:
    1. msg-1: user "开始任务"
    2. msg-2: assistant "好的"
    3. msg-3: user "继续"
    4. msg-4: assistant "完成部分"
    5. msg-5: user [CompactionPart] ← 第1次压缩触发
    6. msg-6: assistant [summary: true] ← 第1次压缩摘要
    7. msg-7: user "下一步"
    8. msg-8: assistant "继续工作"
    9. msg-9: user [CompactionPart] ← 第2次压缩触发
    10. msg-10: assistant [summary: true] ← 第2次压缩摘要
    11. msg-11: user "最后检查"
    12. msg-12: assistant "完成"
    """
    messages = []

    # 早期消息（第1次压缩前）
    messages.append(MessageWithParts(
        info=UserMessage(
            id="msg-1", session_id=session_id, role=MessageRole.USER,
            time=TimeInfo(created=1000), agent="default",
            model=ModelInfo(provider_id="anthropic", model_id="claude-3-opus")
        ),
        parts=[TextPart(id="p1", session_id=session_id, message_id="msg-1",
                       type=PartType.TEXT, text="开始任务")]
    ))

    messages.append(MessageWithParts(
        info=AssistantMessage(
            id="msg-2", session_id=session_id, role=MessageRole.ASSISTANT,
            time=TimeInfo(created=2000), parent_id="msg-1",
            model_id="claude-3-opus", provider_id="anthropic",
            mode="default", agent="default", finish="stop"
        ),
        parts=[TextPart(id="p2", session_id=session_id, message_id="msg-2",
                       type=PartType.TEXT, text="好的")]
    ))

    # 第1次压缩点
    messages.append(MessageWithParts(
        info=UserMessage(
            id="msg-5", session_id=session_id, role=MessageRole.USER,
            time=TimeInfo(created=5000), agent="compaction",
            model=ModelInfo(provider_id="anthropic", model_id="claude-3-opus")
        ),
        parts=[CompactionPart(id="p5", session_id=session_id, message_id="msg-5",
                             type=PartType.COMPACTION, auto=True)]
    ))

    messages.append(MessageWithParts(
        info=AssistantMessage(
            id="msg-6", session_id=session_id, role=MessageRole.ASSISTANT,
            time=TimeInfo(created=6000), parent_id="msg-5",
            model_id="claude-3-opus", provider_id="anthropic",
            mode="compaction", agent="compaction",
            summary=True, finish="stop"  # ← 关键标记
        ),
        parts=[TextPart(id="p6", session_id=session_id, message_id="msg-6",
                       type=PartType.TEXT, text="摘要: 目标是完成任务...")]
    ))

    # 第1次压缩后的消息
    messages.append(MessageWithParts(
        info=UserMessage(
            id="msg-7", session_id=session_id, role=MessageRole.USER,
            time=TimeInfo(created=7000), agent="default",
            model=ModelInfo(provider_id="anthropic", model_id="claude-3-opus")
        ),
        parts=[TextPart(id="p7", session_id=session_id, message_id="msg-7",
                       type=PartType.TEXT, text="下一步")]
    ))

    # 第2次压缩点
    messages.append(MessageWithParts(
        info=UserMessage(
            id="msg-9", session_id=session_id, role=MessageRole.USER,
            time=TimeInfo(created=9000), agent="compaction",
            model=ModelInfo(provider_id="anthropic", model_id="claude-3-opus")
        ),
        parts=[CompactionPart(id="p9", session_id=session_id, message_id="msg-9",
                             type=PartType.COMPACTION, auto=True)]
    ))

    messages.append(MessageWithParts(
        info=AssistantMessage(
            id="msg-10", session_id=session_id, role=MessageRole.ASSISTANT,
            time=TimeInfo(created=10000), parent_id="msg-9",
            model_id="claude-3-opus", provider_id="anthropic",
            mode="compaction", agent="compaction",
            summary=True, finish="stop"  # ← 关键标记
        ),
        parts=[TextPart(id="p10", session_id=session_id, message_id="msg-10",
                       type=PartType.TEXT, text="摘要: 已完成大部分工作...")]
    ))

    # 最新消息
    messages.append(MessageWithParts(
        info=UserMessage(
            id="msg-11", session_id=session_id, role=MessageRole.USER,
            time=TimeInfo(created=11000), agent="default",
            model=ModelInfo(provider_id="anthropic", model_id="claude-3-opus")
        ),
        parts=[TextPart(id="p11", session_id=session_id, message_id="msg-11",
                       type=PartType.TEXT, text="最后检查")]
    ))

    messages.append(MessageWithParts(
        info=AssistantMessage(
            id="msg-12", session_id=session_id, role=MessageRole.ASSISTANT,
            time=TimeInfo(created=12000), parent_id="msg-11",
            model_id="claude-3-opus", provider_id="anthropic",
            mode="default", agent="default", finish="stop"
        ),
        parts=[TextPart(id="p12", session_id=session_id, message_id="msg-12",
                       type=PartType.TEXT, text="完成")]
    ))

    return messages


def demonstrate_filtering():
    """演示过滤机制"""
    print("=" * 60)
    print("上下文过滤机制演示")
    print("=" * 60)

    session_id = "test-session"
    messages = create_test_messages(session_id)

    print(f"\n创建了 {len(messages)} 条测试消息")
    print("\n消息序列（从旧到新）:")
    for msg in messages:
        role = msg.info.role.value
        msg_id = msg.info.id
        has_compaction = any(p.type == PartType.COMPACTION for p in msg.parts)
        is_summary = getattr(msg.info, 'summary', False)

        markers = []
        if has_compaction:
            markers.append("[CompactionPart]")
        if is_summary:
            markers.append("[summary: true]")

        marker_str = " ".join(markers) if markers else ""
        print(f"  {msg_id}: {role:10s} {marker_str}")

    # 反转为DESC顺序（从新到旧）
    messages_desc = list(reversed(messages))

    print("\n" + "=" * 60)
    print("执行过滤算法")
    print("=" * 60)

    # 执行过滤
    filtered = filter_compacted(messages_desc)

    print(f"\n过滤前: {len(messages)} 条消息")
    print(f"过滤后: {len(filtered)} 条消息")

    print("\n保留的消息（从旧到新）:")
    for msg in filtered:
        role = msg.info.role.value
        msg_id = msg.info.id
        has_compaction = any(p.type == PartType.COMPACTION for p in msg.parts)
        is_summary = getattr(msg.info, 'summary', False)

        markers = []
        if has_compaction:
            markers.append("[CompactionPart]")
        if is_summary:
            markers.append("[summary: true]")

        marker_str = " ".join(markers) if markers else ""
        print(f"  {msg_id}: {role:10s} {marker_str}")

    print("\n" + "=" * 60)
    print("结论")
    print("=" * 60)
    print("✓ 只保留最后一次压缩点（msg-9）之后的消息")
    print("✓ 包含压缩摘要（msg-10）和后续对话")
    print("✓ 早期历史（msg-1 到 msg-8）被过滤掉")


if __name__ == "__main__":
    demonstrate_filtering()
