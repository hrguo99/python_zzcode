#!/usr/bin/env python3
"""
OpenCode Python 项目启动脚本
"""

import asyncio
import sys
from pathlib import Path

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from interpreter import InterpreterConfig
from orchestrator import Orchestrator
from agent import AgentConfig
from tool import ReadTool, WriteTool, BashTool, GlobTool, GrepTool


async def main():
    """主函数"""
    print("=" * 60)
    print("🚀 OpenCode Python - AI 编程助手")
    print("=" * 60)
    print()

    # 1. 创建配置
    print("⚙️  初始化配置...")

    # 使用 .env 中的默认配置
    interpreter_config = InterpreterConfig(
        provider="glm",
        model="glm-4-flash",
        temperature=0.7,
    )

    agent_config = AgentConfig(
        default_agent="build",
    )

    # 2. 创建 Orchestrator（已优化：权限缓存 + 工具工厂）
    print("✅ 创建 Orchestrator（支持渐进式工具披露 + 性能优化）...")

    orch = Orchestrator(
        config=interpreter_config,
        agent_config=agent_config,
        project_dir=str(Path.cwd()),
    )

    # 3. 注册工具
    print("🔧 注册工具...")
    orch.register_tool("read", ReadTool())
    orch.register_tool("write", WriteTool())
    orch.register_tool("bash", BashTool())
    orch.register_tool("glob", GlobTool())
    orch.register_tool("grep", GrepTool())

    # 4. 初始化
    print("🎯 初始化系统...")
    async with orch:
        print()
        print("=" * 60)
        print("✅ 系统启动成功！")
        print("=" * 60)
        print()
        print("⌨️  进入交互模式...")
        print("-" * 60)
        print()

        # 简单的交互循环
        session_id = "user_001"

        while True:
            try:
                # 获取用户输入
                user_input = input("\n用户: ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ['exit', 'quit', '退出', 'q']:
                    print("\n👋 再见！")
                    break

                # 处理输入
                print("\nzz_code: ", end="", flush=True)

                response_parts = []
                tool_used = None
                event_count = {}  # 调试：统计事件类型
                async for event in orch.process(
                    user_input=user_input,
                    session_id=session_id,
                ):
                    event_type = event.get("type")
                    event_count[event_type] = event_count.get(event_type, 0) + 1

                    # 只显示文本内容给用户
                    if event_type == "content":
                        content = event.get("content", "")
                        print(content, end="", flush=True)
                        response_parts.append(content)
                    elif event_type == "text":
                        text = event.get("text", "")
                        print(text, end="", flush=True)
                        response_parts.append(text)
                    elif event_type == "result":
                        # 调试：查看 result 事件内容
                        print(f"\n[DEBUG] result 事件: {event}", flush=True)
                    # 记录工具调用
                    elif event_type == "tool-call":
                        tool_used = event.get("tool_name")
                    # 工具调用和结果在后台静默处理
                    # 只在出错时显示错误信息
                    elif event_type == "error":
                        error_msg = event.get("error", "Unknown error")
                        print(f"\n\n⚠️  执行过程中出现错误: {error_msg}")
                    elif event_type == "tool-error":
                        error_msg = event.get("error", "")
                        print(f"\n\n⚠️  工具执行失败: {error_msg}")

                # 调试信息
                print(f"\n[DEBUG] 事件统计: {event_count}", flush=True)
                print(f"[DEBUG] response_parts 长度: {len(response_parts)}", flush=True)
                print(f"[DEBUG] tool_used: {tool_used}", flush=True)

                # 如果AI没有生成文本但使用了工具，显示友好的确认消息
                if not response_parts and tool_used:
                    print("\n[DEBUG] 触发备用消息逻辑", flush=True)
                    tool_messages = {
                        "write": "好的，文件已创建完成。",
                        "read": "好的，文件内容已读取。",
                        "bash": "好的，命令已执行完成。",
                        "edit": "好的，文件已修改完成。",
                    }
                    default_msg = "好的，操作已完成。"
                    print(tool_messages.get(tool_used, default_msg), end="", flush=True)

                print()  # 换行

            except KeyboardInterrupt:
                print("\n\n👋 再见！")
                break
            except Exception as e:
                print(f"\n⚠️  发生错误: {e}")
                import traceback
                traceback.print_exc()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 程序已退出")
