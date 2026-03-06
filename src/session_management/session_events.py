"""
会话事件系统

提供会话操作的事件发布和订阅机制。
"""

from typing import Callable, Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class SessionEventType(str, Enum):
    """会话事件类型"""
    CREATED = "session.created"
    UPDATED = "session.updated"
    DELETED = "session.deleted"
    COMPACTED = "session.compacted"
    MESSAGE_UPDATED = "message.updated"
    PART_UPDATED = "part.updated"


@dataclass
class SessionEvent:
    """会话事件"""
    type: SessionEventType
    data: Dict[str, Any]


class EventBus:
    """事件总线"""

    def __init__(self):
        self._subscribers: Dict[SessionEventType, List[Callable]] = {}

    def subscribe(self, event_type: SessionEventType, handler: Callable) -> None:
        """订阅事件"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def publish(self, event_type: SessionEventType, data: Dict[str, Any]) -> None:
        """发布事件"""
        if event_type in self._subscribers:
            event = SessionEvent(type=event_type, data=data)
            for handler in self._subscribers[event_type]:
                try:
                    handler(event)
                except Exception as e:
                    print(f"Event handler error: {e}")


# 全局事件总线实例
_event_bus = EventBus()


def get_event_bus() -> EventBus:
    """获取全局事件总线"""
    return _event_bus
