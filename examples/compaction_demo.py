"""
上下文压缩机制使用示例

展示OpenCode三层防护系统的完整使用流程。
"""

import asyncio
from session_management import (
    SessionStorage,
    SessionManager,
    SessionCompaction,
    CompactionConfig,
    ModelLimits,
    filter_compacted,
    MessageWithParts,
    UserMessage,
    AssistantMessage,
    ToolPart,
    TextPart,
    CompactionPart,
    ModelInfo,
    TimeInfo,
    TokenUsage,
    MessageRole,
    PartType,
    ToolStatus,
    ToolStateCompleted,
)


async def demonstrate_three_layer_protection():
    """
    演示三层防护系统：
    1. 剪枝 (Pruning) - 删除旧工具输出
    2. 消息过滤 (filterCompacted) - 只保留最后压缩后的消息
    3. 自动压缩 (Auto Compaction) - 生成结构化摘要
    """

    # 初始化
    storage = SessionStorage("/tmp/compaction_demo.db")
    manager = SessionManager(storage, "demo-project")

    # 创建会话
    session = manager.create(directory="/home/user/project", title="Compaction Demo")
    print(f"Created session: {session.id}\n")

    # 模拟长对话历史
    messages = create_mock_messages(session.id)
    print(f"Created {len(messages)} mock messages\n")

    # === 第一层：剪枝 (Pruning) ===
    print("=== Layer 1: Pruning ===")
    model_limits = ModelLimits(
        max_context=200000,
        max_output=8192,
        max_input=180000
    )

    compaction = SessionCompaction(
        model_limit=model_limits,
        config=CompactionConfig(auto=True, reserved=20000),
        storage=storage
    )

    # 执行剪枝
    await compaction.prune(session.id)
    print("✓ Pruning completed: Old tool outputs marked as compacted\n")

    # === 第二层：消息过滤 ===
    print("=== Layer 2: Message Filtering ===")

    # 过滤已压缩的消息
    filtered_messages = filter_compacted(messages)
    print(f"Before filtering: {len(messages)} messages")
    print(f"After filtering: {len(filtered_messages)} messages")
    print("✓ Only messages after last compaction are kept\n")

    # === 第三层：自动压缩 ===
    print("=== Layer 3: Auto Compaction ===")

    # 检查是否需要压缩
    last_assistant = next(
        (m for m in reversed(messages) if m.info.role == "assistant"),
        None
    )

    if last_assistant and hasattr(last_assistant.info, 'tokens'):
        is_overflow = await compaction.is_overflow(
            tokens=last_assistant.info.tokens,
            model=ModelInfo(provider_id="anthropic", model_id="claude-3-opus")
        )

        if is_overflow:
            print("✓ Context overflow detected, compaction needed")
            # 执行压缩
            # result = await compaction.process(...)
        else:
            print("✓ Context within limits, no compaction needed")

    print("\n=== Summary ===")
    print("Three-layer protection system demonstrated:")
    print("1. Pruning: Removes old tool outputs (>40K tokens)")
    print("2. Filtering: Keeps only post-compaction messages")
    print("3. Compaction: Generates structured summary when needed")


def create_mock_messages(session_id: str) -> list[MessageWithParts]:
    """创建模拟消息用于演示"""
    messages = []

    # 用户消息1
    user1 = UserMessage(
        id="msg_001",
        session_id=session_id,
        role=MessageRole.USER,
        time=TimeInfo(created=1000),
        agent="default",
        model=ModelInfo(provider_id="anthropic", model_id="claude-3-opus")
    )
    messages.append(MessageWithParts(info=user1, parts=[
        TextPart(
            id="part_001",
            session_id=session_id,
            message_id=user1.id,
            type=PartType.TEXT,
            text="Help me analyze this code"
        )
    ]))

    # 助手消息1（带工具调用）
    assistant1 = AssistantMessage(
        id="msg_002",
        session_id=session_id,
        role=MessageRole.ASSISTANT,
        time=TimeInfo(created=2000),
        parent_id=user1.id,
        model_id="claude-3-opus",
        provider_id="anthropic",
        mode="default",
        agent="default",
        tokens=TokenUsage(input=1000, output=500, total=1500)
    )
    messages.append(MessageWithParts(info=assistant1, parts=[
        ToolPart(
            id="part_002",
            session_id=session_id,
            message_id=assistant1.id,
            type=PartType.TOOL,
            tool="read_file",
            call_id="call_001",
            state=ToolStateCompleted(
                status=ToolStatus.COMPLETED,
                input={"path": "main.py"},
                output="# Large file content..." * 1000,  # 模拟大输出
                title="Read main.py",
                time_start=2000,
                time_end=2100
            )
        )
    ]))

    return messages


if __name__ == "__main__":
    asyncio.run(demonstrate_three_layer_protection())
