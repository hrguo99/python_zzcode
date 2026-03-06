"""
会话存储模块

提供基于SQLite的会话持久化存储。
"""

import sqlite3
import json
import time
from typing import Optional, List, Dict, Any, AsyncGenerator
from pathlib import Path
from contextlib import asynccontextmanager

from .message_types import (
    Message,
    Part,
    UserMessage,
    AssistantMessage,
    MessageRole,
    create_message_from_dict,
    create_part_from_dict,
)


class SessionStorage:
    """会话存储管理器"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")

        # 会话表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS session (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                parent_id TEXT,
                slug TEXT NOT NULL,
                title TEXT NOT NULL,
                directory TEXT NOT NULL,
                version TEXT NOT NULL,
                summary_additions INTEGER DEFAULT 0,
                summary_deletions INTEGER DEFAULT 0,
                summary_files INTEGER DEFAULT 0,
                share_url TEXT,
                revert TEXT,
                permission TEXT,
                time_created INTEGER NOT NULL,
                time_updated INTEGER NOT NULL,
                time_archived INTEGER
            )
        """)

        # 消息表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS message (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                time_created INTEGER NOT NULL,
                data TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES session(id) ON DELETE CASCADE
            )
        """)

        # 部件表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS part (
                id TEXT PRIMARY KEY,
                message_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                time_created INTEGER NOT NULL,
                data TEXT NOT NULL,
                FOREIGN KEY (message_id) REFERENCES message(id) ON DELETE CASCADE,
                FOREIGN KEY (session_id) REFERENCES session(id) ON DELETE CASCADE
            )
        """)

        # 索引
        conn.execute("CREATE INDEX IF NOT EXISTS session_project_idx ON session(project_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS message_session_idx ON message(session_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS part_message_idx ON part(message_id)")

        conn.commit()
        conn.close()

    def create_session(self, session_data: Dict[str, Any]) -> str:
        """创建会话"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO session (id, project_id, parent_id, slug, title, directory,
                version, time_created, time_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_data["id"],
            session_data["project_id"],
            session_data.get("parent_id"),
            session_data["slug"],
            session_data["title"],
            session_data["directory"],
            session_data["version"],
            session_data["time_created"],
            session_data["time_updated"],
        ))
        conn.commit()
        conn.close()
        return session_data["id"]

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM session WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return dict(row)

    def update_session(self, session_id: str, updates: Dict[str, Any]) -> None:
        """更新会话"""
        conn = sqlite3.connect(self.db_path)
        updates["time_updated"] = int(time.time() * 1000)

        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [session_id]

        conn.execute(f"UPDATE session SET {set_clause} WHERE id = ?", values)
        conn.commit()
        conn.close()

    def delete_session(self, session_id: str) -> None:
        """删除会话（级联删除消息和部件）"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM session WHERE id = ?", (session_id,))
        conn.commit()
        conn.close()

    def save_message(self, message: Message) -> None:
        """保存消息"""
        conn = sqlite3.connect(self.db_path)
        data = json.dumps({
            "id": message.id,
            "session_id": message.session_id,
            "role": message.role.value,
            "time": {"created": message.time.created},
            **self._message_to_dict(message)
        })

        conn.execute("""
            INSERT OR REPLACE INTO message (id, session_id, time_created, data)
            VALUES (?, ?, ?, ?)
        """, (message.id, message.session_id, message.time.created, data))
        conn.commit()
        conn.close()

    def save_part(self, part: Part) -> None:
        """保存部件"""
        conn = sqlite3.connect(self.db_path)
        data = json.dumps(self._part_to_dict(part))

        conn.execute("""
            INSERT OR REPLACE INTO part (id, message_id, session_id, time_created, data)
            VALUES (?, ?, ?, ?, ?)
        """, (part.id, part.message_id, part.session_id, int(time.time() * 1000), data))
        conn.commit()
        conn.close()

    def get_messages(self, session_id: str) -> List[Message]:
        """获取会话的所有消息"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT data FROM message WHERE session_id = ? ORDER BY time_created",
            (session_id,)
        )
        rows = cursor.fetchall()
        conn.close()

        return [create_message_from_dict(json.loads(row["data"])) for row in rows]

    def stream_messages(self, session_id: str, batch_size: int = 50):
        """
        流式获取消息（从新到旧，DESC顺序）

        Args:
            session_id: 会话ID
            batch_size: 批次大小

        Yields:
            MessageWithParts: 包含部件的消息
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        offset = 0
        while True:
            # 从新到旧读取消息
            cursor = conn.execute(
                """SELECT data FROM message
                   WHERE session_id = ?
                   ORDER BY time_created DESC
                   LIMIT ? OFFSET ?""",
                (session_id, batch_size, offset)
            )
            rows = cursor.fetchall()

            if not rows:
                break

            # 批量加载部件
            message_ids = [json.loads(row["data"])["id"] for row in rows]
            parts_map = self._load_parts_batch(message_ids)

            # 逐条yield消息
            for row in rows:
                msg_data = json.loads(row["data"])
                msg = create_message_from_dict(msg_data)
                parts = parts_map.get(msg.id, [])

                from .message_types import MessageWithParts
                yield MessageWithParts(info=msg, parts=parts)

            offset += batch_size

        conn.close()

    def _load_parts_batch(self, message_ids: List[str]) -> Dict[str, List[Part]]:
        """批量加载多个消息的部件"""
        if not message_ids:
            return {}

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        placeholders = ",".join("?" * len(message_ids))
        cursor = conn.execute(
            f"""SELECT message_id, data FROM part
                WHERE message_id IN ({placeholders})
                ORDER BY time_created""",
            message_ids
        )
        rows = cursor.fetchall()
        conn.close()

        # 按message_id分组
        parts_map: Dict[str, List[Part]] = {}
        for row in rows:
            msg_id = row["message_id"]
            part = create_part_from_dict(json.loads(row["data"]))
            if msg_id not in parts_map:
                parts_map[msg_id] = []
            parts_map[msg_id].append(part)

        return parts_map

    def get_parts(self, message_id: str) -> List[Part]:
        """获取消息的所有部件"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT data FROM part WHERE message_id = ? ORDER BY time_created",
            (message_id,)
        )
        rows = cursor.fetchall()
        conn.close()

        return [create_part_from_dict(json.loads(row["data"])) for row in rows]

    def _message_to_dict(self, message: Message) -> Dict[str, Any]:
        """消息转字典"""
        if isinstance(message, UserMessage):
            return {
                "agent": message.agent,
                "model": {"provider_id": message.model.provider_id, "model_id": message.model.model_id},
                "system": message.system,
            }
        elif isinstance(message, AssistantMessage):
            return {
                "parent_id": message.parent_id,
                "model_id": message.model_id,
                "provider_id": message.provider_id,
                "finish": message.finish,
                "tokens": {
                    "input": message.tokens.input,
                    "output": message.tokens.output,
                    "total": message.tokens.total,
                }
            }
        return {}

    def _part_to_dict(self, part: Part) -> Dict[str, Any]:
        """部件转字典"""
        from dataclasses import asdict
        return asdict(part)
