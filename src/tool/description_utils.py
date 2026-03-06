"""
工具描述转换工具

将 ToolDefinition 转换为 ToolDescription，支持渐进式披露
"""

from typing import Dict, Any
from .base import ToolDefinition
from .progressive_disclosure import ToolDescription, ProgressiveToolRegistry


async def convert_tool_to_description(tool_def: ToolDefinition) -> ToolDescription:
    """
    将 ToolDefinition 转换为 ToolDescription

    提取工具的简要描述（取description的前100个字符）和完整schema

    Args:
        tool_def: 工具定义对象

    Returns:
        ToolDescription 对象
    """
    # 获取完整描述
    full_desc = tool_def.description
    parameters = tool_def.parameters_schema

    # 生成简短描述（截取或提取第一句话）
    short_desc = full_desc
    if len(full_desc) > 100:
        # 尝提取第一句话
        first_period = full_desc.find('。')
        first_dot = full_desc.find('. ')
        if first_period > 0 and first_period < 100:
            short_desc = full_desc[:first_period + 1]
        elif first_dot > 0 and first_dot < 100:
            short_desc = full_desc[:first_dot + 1]
        else:
            short_desc = full_desc[:97] + "..."

    # 创建 ToolDescription
    return ToolDescription(
        name=tool_def.id,
        short_description=short_desc,
        full_schema=parameters,
        execute_fn=tool_def,
        metadata={
            "full_description": full_desc,
            "tool_id": tool_def.tool_id
        }
    )


def create_tool_summary(tools: Dict[str, ToolDefinition]) -> str:
    """
    创建工具列表的文本摘要

    用于调试和日志记录

    Args:
        tools: 工具字典

    Returns:
        文本摘要
    """
    lines = [f"可用工具 ({len(tools)}):"]
    for name, tool in tools.items():
        desc = tool.description
        if len(desc) > 60:
            desc = desc[:57] + "..."
        lines.append(f"  - {name}: {desc}")
    return "\n".join(lines)


__all__ = [
    "convert_tool_to_description",
    "create_tool_summary",
]
