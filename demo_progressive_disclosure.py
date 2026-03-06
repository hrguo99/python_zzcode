#!/usr/bin/env python3
"""
渐进式工具披露 - 演示脚本

演示按需加载工具描述的功能
"""

import sys
from pathlib import Path

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from tool.progressive_disclosure import ProgressiveToolRegistry, calculate_token_savings
from tool.description_utils import create_tool_summary


def print_section(title: str):
    """打印分节标题"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def demo_progressive_disclosure():
    """演示渐进式披露功能"""
    print_section("渐进式工具披露演示")
    print("核心思想：")
    print("  1. 初始时只向模型发送工具名称 + 简短描述（~50 tokens/tool）")
    print("  2. 模型决定调用工具时，才提供完整的参数schema（~300 tokens/tool）")
    print("  3. 这样可以大幅减少初始token使用，避免信息过载")
    print()

    # 创建工具注册表
    registry = ProgressiveToolRegistry()

    # 注册一些示例工具
    print("【注册工具】")

    # Read tool
    registry.register(
        name="read",
        short_description="读取文件内容",
        full_schema={
            "type": "object",
            "properties": {
                "filePath": {
                    "type": "string",
                    "description": "文件的绝对或相对路径"
                },
                "offset": {
                    "type": "integer",
                    "description": "读取的起始字节位置（可选）"
                },
                "limit": {
                    "type": "integer",
                    "description": "读取的最大字节数（可选）"
                }
            },
            "required": ["filePath"]
        },
        execute_fn=lambda x: f"Reading {x['filePath']}",
    )
    print("  ✅ read - 读取文件内容")

    # Write tool
    registry.register(
        name="write",
        short_description="写入内容到文件",
        full_schema={
            "type": "object",
            "properties": {
                "filePath": {
                    "type": "string",
                    "description": "文件的绝对或相对路径"
                },
                "content": {
                    "type": "string",
                    "description": "要写入的内容"
                },
                "mode": {
                    "type": "string",
                    "description": "写入模式（overwrite, append）",
                    "enum": ["overwrite", "append"]
                }
            },
            "required": ["filePath", "content"]
        },
        execute_fn=lambda x: f"Writing to {x['filePath']}",
    )
    print("  ✅ write - 写入内容到文件")

    # Bash tool
    registry.register(
        name="bash",
        short_description="执行shell命令",
        full_schema={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的shell命令"
                },
                "workdir": {
                    "type": "string",
                    "description": "工作目录（可选）"
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时时间（秒）"
                }
            },
            "required": ["command"]
        },
        execute_fn=lambda x: f"Executing {x['command']}",
    )
    print("  ✅ bash - 执行shell命令")

    # Glob tool
    registry.register(
        name="glob",
        short_description="搜索文件",
        full_schema={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "文件匹配模式"
                },
                "path": {
                    "type": "string",
                    "description": "搜索路径（可选）"
                }
            },
            "required": ["pattern"]
        },
        execute_fn=lambda x: f"Globbing {x['pattern']}",
    )
    print("  ✅ glob - 搜索文件")

    # Grep tool
    registry.register(
        name="grep",
        short_description="在文件中搜索内容",
        full_schema={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "搜索模式"
                },
                "path": {
                    "type": "string",
                    "description": "搜索路径"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "是否递归搜索"
                }
            },
            "required": ["pattern", "path"]
        },
        execute_fn=lambda x: f"Grepping {x['pattern']} in {x['path']}",
    )
    print("  ✅ grep - 在文件中搜索内容")

    print()

    # 演示简化版工具列表
    print_section("初始工具列表（发送给模型）")

    simple_tools = registry.list_simple()
    print("这是发送给AI模型的初始工具列表：\n")

    import json
    for i, tool in enumerate(simple_tools, 1):
        tool_json = json.dumps(tool, ensure_ascii=False)
        token_count = len(tool_json)
        print(f"  工具 {i}: {tool['function']['name']}")
        print(f"    描述: {tool['function']['description']}")
        print(f"    Token数: ~{token_count}")
        print()

    # 计算节省
    print_section("Token 使用对比")

    # 估计完整版本的大小
    full_tools_example = []
    for tool_desc in registry._tools.values():
        full_tools_example.append(tool_desc.to_full_dict())

    savings = calculate_token_savings(full_tools_example)

    print(f"工具数量: {savings['tool_count']}")
    print(f"简化版本: ~{savings['simple_tokens']} tokens")
    print(f"完整版本: ~{savings['full_tokens_estimate']} tokens (估计)")
    print(f"节省 tokens: ~{savings['saved_tokens']} tokens")
    print(f"节省比例: {savings['savings_percentage']:.1f}%")
    print()

    # 演示按需获取完整schema
    print_section("按需加载完整Schema")

    print("场景：模型决定调用 read 工具\n")
    print("初始信息（模型已知）:")
    simple_read = registry.list_simple()[0]  # read tool
    print(f"  名称: {simple_read['function']['name']}")
    print(f"  描述: {simple_read['function']['description']}")
    print()

    print("按需加载完整信息:")
    full_read = registry.get_full_schema("read")
    print(f"  完整参数schema:")
    print(json.dumps(full_read['function']['parameters'], indent=4, ensure_ascii=False))
    print()

    # 使用示例
    print_section("使用示例")

    print("```python")
    print("# 初始：只获取简化工具列表")
    print("simple_tools = registry.list_simple()")
    print("send_to_model(simple_tools)  # ~250 tokens")
    print()
    print("# 模型决定调用 read 工具")
    print("if model_wants_to_use('read'):")
    print("    # 此时才获取完整schema")
    print("    full_schema = registry.get_full_schema('read')")
    print("    send_to_model({'name': 'read', 'parameters': full_schema})")
    print()
    print("# 执行工具")
    print("tool = registry.get_tool('read')")
    print("result = await tool.execute_fn({'filePath': 'test.py'})")
    print("```")
    print()

    print_section("总结")

    print("✅ 核心优势:")
    print("  1. 减少75-85%的初始token使用")
    print("  2. 避免模型被过多的参数信息淹没")
    print("  3. 工具详细信息只在需要时才加载")
    print("  4. 保持工具调用的一致性")
    print()
    print("💡 适用场景:")
    print("  - 工具数量多（>5个）")
    print("  - 参数schema复杂")
    print("  - 需要控制上下文大小")
    print("  - 按使用次数计费的API")
    print()


if __name__ == "__main__":
    demo_progressive_disclosure()
