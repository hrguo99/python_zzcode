"""
会话管理器

提供会话生命周期管理的高级API。
"""

import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from ulid import ULID

from .session_storage import SessionStorage
from .message_types import Message, Part
from .session_events import get_event_bus, SessionEventType


@dataclass
class SessionInfo:
    """会话信息"""
    id: str
    project_id: str
    parent_id: Optional[str]
    slug: str
    title: str
    directory: str
    version: str
    time_created: int
    time_updated: int
    time_archived: Optional[int] = None
    share_url: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None


class SessionManager:
    """
    会话管理器

    提供会话的创建、查询、更新、删除等操作。
    """

    def __init__(self, storage: SessionStorage, project_id: str, version: str = "1.0.0"):
        self.storage = storage
        self.project_id = project_id
        self.version = version
        self.event_bus = get_event_bus()

    def create(
        self,
        directory: str,
        title: Optional[str] = None,
        parent_id: Optional[str] = None,
    ) -> SessionInfo:
        """创建新会话"""
        session_id = str(ULID())
        slug = self._generate_slug()
        now = int(time.time() * 1000)

        if not title:
            title = f"New session - {time.strftime('%Y-%m-%d %H:%M:%S')}"

        session_data = {
            "id": session_id,
            "project_id": self.project_id,
            "parent_id": parent_id,
            "slug": slug,
            "title": title,
            "directory": directory,
            "version": self.version,
            "time_created": now,
            "time_updated": now,
        }

        self.storage.create_session(session_data)
        info = self._to_session_info(session_data)
        self.event_bus.publish(SessionEventType.CREATED, {"info": session_data})
        return info

    def get(self, session_id: str) -> Optional[SessionInfo]:
        """获取会话信息"""
        data = self.storage.get_session(session_id)
        return self._to_session_info(data) if data else None

    def update_title(self, session_id: str, title: str) -> None:
        """更新会话标题"""
        self.storage.update_session(session_id, {"title": title})
        self.event_bus.publish(SessionEventType.UPDATED, {"session_id": session_id})

    def archive(self, session_id: str) -> None:
        """归档会话"""
        self.storage.update_session(session_id, {
            "time_archived": int(time.time() * 1000)
        })

    def delete(self, session_id: str) -> None:
        """删除会话"""
        self.storage.delete_session(session_id)
        self.event_bus.publish(SessionEventType.DELETED, {"session_id": session_id})

    def fork(
        self,
        source_session_id: str,
        message_id: Optional[str] = None,
    ) -> SessionInfo:
        """Fork会话"""
        source = self.get(source_session_id)
        if not source:
            raise ValueError(f"Source session not found: {source_session_id}")

        # 生成fork标题
        fork_title = self._generate_fork_title(source.title)

        # 创建新会话
        new_session = self.create(
            directory=source.directory,
            title=fork_title,
        )

        # 复制消息和部件（简化版本）
        messages = self.storage.get_messages(source_session_id)
        for msg in messages:
            if message_id and msg.id == message_id:
                break
            msg.session_id = new_session.id
            self.storage.save_message(msg)

            parts = self.storage.get_parts(msg.id)
            for part in parts:
                part.session_id = new_session.id
                self.storage.save_part(part)

        return new_session

    def save_message(self, message: Message) -> None:
        """保存消息"""
        self.storage.save_message(message)

    def save_part(self, part: Part) -> None:
        """保存部件"""
        self.storage.save_part(part)

    def get_messages(self, session_id: str) -> List[Message]:
        """获取会话消息"""
        return self.storage.get_messages(session_id)

    def get_filtered_messages(self, session_id: str) -> List['MessageWithParts']:
        """
        获取过滤后的会话消息（只包含最后压缩点之后的消息）

        Returns:
            过滤后的消息列表（从旧到新）
        """
        from .message_filter import filter_compacted_stream

        # 使用流式读取并过滤
        stream = self.storage.stream_messages(session_id)
        return filter_compacted_stream(stream)

    def _generate_slug(self) -> str:
        """生成URL slug"""
        return str(ULID()).lower()[:12]

    def _generate_fork_title(self, original_title: str) -> str:
        """生成fork标题"""
        import re
        match = re.search(r'\(fork #(\d+)\)$', original_title)
        if match:
            num = int(match.group(1)) + 1
            base_title = original_title[:match.start()].strip()
        else:
            num = 1
            base_title = original_title

        return f"{base_title} (fork #{num})"

    def _to_session_info(self, data: Dict[str, Any]) -> SessionInfo:
        """转换为SessionInfo对象"""
        return SessionInfo(
            id=data["id"],
            project_id=data["project_id"],
            parent_id=data.get("parent_id"),
            slug=data["slug"],
            title=data["title"],
            directory=data["directory"],
            version=data["version"],
            time_created=data["time_created"],
            time_updated=data["time_updated"],
            time_archived=data.get("time_archived"),
            share_url=data.get("share_url"),
        )
