"""
会话管理使用示例

展示如何使用优化后的会话管理系统。
"""

import asyncio
from pathlib import Path

from session_management import (
    SessionStorage,
    SessionManager,
    SessionEventType,
    get_event_bus,
    UserMessage,
    AssistantMessage,
    TextPart,
    ModelInfo,
    TimeInfo,
    MessageRole,
    PartType,
)


def setup_event_listeners():
    """设置事件监听器"""
    bus = get_event_bus()

    def on_session_created(event):
        print(f"✓ Session created: {event.data.get('info', {}).get('id')}")

    def on_session_updated(event):
        print(f"✓ Session updated: {event.data.get('session_id')}")

    def on_session_deleted(event):
        print(f"✓ Session deleted: {event.data.get('session_id')}")

    bus.subscribe(SessionEventType.CREATED, on_session_created)
    bus.subscribe(SessionEventType.UPDATED, on_session_updated)
    bus.subscribe(SessionEventType.DELETED, on_session_deleted)


def main():
    """主函数"""
    # 1. 初始化存储和管理器
    db_path = "/tmp/opencode_sessions.db"
    storage = SessionStorage(db_path)
    manager = SessionManager(
        storage=storage,
        project_id="demo-project",
        version="1.0.0"
    )

    # 2. 设置事件监听
    setup_event_listeners()

    # 3. 创建会话
    session = manager.create(
        directory="/home/user/project",
        title="Demo Session"
    )
    print(f"\nCreated session: {session.id}")

    # 4. 保存消息
    user_msg = UserMessage(
        id="msg_001",
        session_id=session.id,
        role=MessageRole.USER,
        time=TimeInfo(created=1234567890),
        agent="default",
        model=ModelInfo(provider_id="anthropic", model_id="claude-3-opus"),
    )
    manager.save_message(user_msg)

    # 5. 保存部件
    text_part = TextPart(
        id="part_001",
        session_id=session.id,
        message_id=user_msg.id,
        type=PartType.TEXT,
        text="Hello, how can I help you?",
    )
    manager.save_part(text_part)

    # 6. 更新会话标题
    manager.update_title(session.id, "Updated Demo Session")

    # 7. Fork会话
    forked = manager.fork(session.id)
    print(f"Forked session: {forked.id} - {forked.title}")

    # 8. 查询会话
    retrieved = manager.get(session.id)
    print(f"\nRetrieved session: {retrieved.title}")

    # 9. 获取消息
    messages = manager.get_messages(session.id)
    print(f"Messages in session: {len(messages)}")

    # 10. 归档会话
    manager.archive(forked.id)
    print(f"Archived session: {forked.id}")

    # 11. 删除会话
    manager.delete(forked.id)

    print("\n✓ All operations completed successfully!")


if __name__ == "__main__":
    main()
