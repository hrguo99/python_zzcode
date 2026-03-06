"""
Progressive Tool Disclosure - 按需加载工具描述

这个模块实现了正确的渐进式披露功能：
- 初始时只向模型暴露工具的简要描述
- 模型决定调用工具时，才提供完整的参数schema
- 这样可以减少初始token使用，避免信息过载
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ToolDescription:
    """
    工具描述包装器

    存储工具的简要描述和完整schema，实现按需加载
    """
    name: str
    """工具名称"""

    short_description: str
    """简短描述（用于初始暴露）"""

    full_schema: Dict[str, Any]
    """完整的参数schema（按需加载）"""

    execute_fn: Any
    """执行函数"""

    metadata: Dict[str, Any]
    """元数据"""

    def to_simple_dict(self) -> Dict[str, Any]:
        """
        转换为简化格式（用于初始工具列表）

        只包含名称和简短描述，不包含详细参数
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.short_description,
                # 注意：这里不包含 parameters，减少token使用
            }
        }

    def to_full_dict(self) -> Dict[str, Any]:
        """
        转换为完整格式（用于工具调用时）

        包含完整的参数schema
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.short_description,
                "parameters": self.full_schema
            }
        }


class ProgressiveToolRegistry:
    """
    渐进式工具注册表

    管理工具的渐进式披露：
    1. 列出工具时只返回简要描述
    2. 调用工具时提供完整schema
    """

    def __init__(self):
        self._tools: Dict[str, ToolDescription] = {}

    def register(
        self,
        name: str,
        short_description: str,
        full_schema: Dict[str, Any],
        execute_fn: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        注册一个工具

        Args:
            name: 工具名称
            short_description: 简短描述（一句话）
            full_schema: 完整的参数schema
            execute_fn: 执行函数
            metadata: 元数据
        """
        self._tools[name] = ToolDescription(
            name=name,
            short_description=short_description,
            full_schema=full_schema,
            execute_fn=execute_fn,
            metadata=metadata or {}
        )
        logger.debug(f"Registered tool: {name}")

    def unregister(self, name: str) -> None:
        """注销工具"""
        if name in self._tools:
            del self._tools[name]

    def get_tool(self, name: str) -> Optional[ToolDescription]:
        """获取工具描述"""
        return self._tools.get(name)

    def list_simple(self) -> List[Dict[str, Any]]:
        """
        列出所有工具的简化描述

        用于初始工具列表，只包含名称+简短描述
        这样可以大幅减少token使用
        """
        return [tool.to_simple_dict() for tool in self._tools.values()]

    def get_full_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        获取工具的完整schema

        用于模型决定调用工具时，提供详细的参数信息

        Args:
            tool_name: 工具名称

        Returns:
            完整的工具定义，包含参数schema
        """
        tool = self._tools.get(tool_name)
        if tool:
            return tool.to_full_dict()
        return None

    def has_tool(self, name: str) -> bool:
        """检查工具是否存在"""
        return name in self._tools

    def get_all_names(self) -> List[str]:
        """获取所有工具名称"""
        return list(self._tools.keys())


def calculate_token_savings(tools: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    计算使用渐进式披露节省的token数量

    Args:
        tools: 完整的工具列表

    Returns:
        包含节省统计的字典
    """
    # 简化版工具的大小（约）
    simple_size = 50  # {type: function, function: {name, description}}

    # 完整版工具的平均大小（估计）
    # 包含详细的parameters schema
    full_size_avg = 300  # 包含复杂的参数定义

    total_tools = len(tools)
    simple_tokens = total_tools * simple_size
    full_tokens = total_tools * full_size_avg

    saved_tokens = full_tokens - simple_tokens
    savings_percentage = (saved_tokens / full_tokens) * 100 if full_tokens > 0 else 0

    return {
        "tool_count": total_tools,
        "simple_tokens": simple_tokens,
        "full_tokens_estimate": full_tokens,
        "saved_tokens": saved_tokens,
        "savings_percentage": savings_percentage,
    }


__all__ = [
    "ToolDescription",
    "ProgressiveToolRegistry",
    "calculate_token_savings",
]
