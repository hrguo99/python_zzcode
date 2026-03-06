"""
Orchestrator 使用示例

演示如何使用重构后的 Orchestrator，包括：
- Agent 管理
- 工具注册和权限过滤
- Skill 集成
- LSP 集成
"""

import asyncio
import sys
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from interpreter import InterpreterConfig
from orchestrator import Orchestrator
from agent import AgentConfig
from tool import ReadTool, WriteTool, BashTool


async def main():
    """主函数"""
    print("=" * 60)
    print("Orchestrator 使用示例")
    print("=" * 60)
    print()

    # 1. 创建配置
    print("1. 创建配置...")
    interpreter_config = InterpreterConfig(
        provider="anthropic",
        model="claude-3-5-sonnet-20241022",
        temperature=0.7,
        max_tokens=4096,
    )

    agent_config = AgentConfig(
        default_agent="build",
        whitelisted_dirs=["/home/jk-b-047/桌面/code/open_code/python-opencode"],
    )

    # 2. 创建 Orchestrator
    print("2. 创建 Orchestrator...")
    orch = Orchestrator(
        config=interpreter_config,
        agent_config=agent_config,
        project_dir="/home/jk-b-047/桌面/code/open_code/python-opencode",
    )

    # 3. 注册工具
    print("3. 注册工具...")
    orch.register_tool("read", ReadTool())
    orch.register_tool("write", WriteTool())
    orch.register_tool("bash", BashTool())
    print(f"   已注册 {len(orch._all_tools)} 个工具")

    # 4. 初始化 Orchestrator
    print("4. 初始化 Orchestrator...")
    async with orch as o:
        print("   Orchestrator 已初始化")
        print()

        # 5. 查看可用的 Agents
        print("5. 查看可用的 Agents:")
        agents = await o.agent_manager.list()
        for agent in agents:
            if not agent.hidden:
                print(f"   - {agent.name}: {agent.description or '无描述'}")
        print()

        # 6. 演示权限过滤
        print("6. 演示权限过滤:")
        build_agent = await o.agent_manager.get("build")
        if build_agent:
            print(f"   Build Agent 权限数量: {len(build_agent.permission)}")

            # 模拟工具过滤
            all_tools = {
                "read": {"name": "read"},
                "write": {"name": "write"},
                "bash": {"name": "bash"},
            }
            filtered_tools = await o._filter_tools_by_agent(build_agent, all_tools)
            print(f"   原始工具数量: {len(all_tools)}")
            print(f"   过滤后工具数量: {len(filtered_tools)}")
            print(f"   允许的工具: {', '.join(filtered_tools.keys())}")
        print()

        # 7. 演示 Skill 集成
        print("7. 演示 Skill 集成:")
        try:
            skill_tools = await o._collect_skill_tools(build_agent)
            print(f"   找到 {len(skill_tools)} 个 Skill 工具")
            for name, tool in list(skill_tools.items())[:3]:  # 只显示前3个
                print(f"   - {name}: {tool.get('description', '无描述')}")
        except Exception as e:
            print(f"   Skill 集成出错: {e}")
        print()

        # 8. 演示 LSP 集成
        print("8. 演示 LSP 集成:")
        try:
            lsp_tools = await o._collect_lsp_tools(build_agent)
            print(f"   找到 {len(lsp_tools)} 个 LSP 工具")
            for name in lsp_tools.keys():
                print(f"   - {name}")
        except Exception as e:
            print(f"   LSP 集成出错: {e}")
        print()

        # 9. 演示消息处理
        print("9. 演示消息处理:")
        print("   输入: '你好'")

        async for event in o.process("你好"):
            if event["type"] == "processing":
                print(f"   {event['message']}")
            elif event["type"] == "text":
                print(event["text"], end="", flush=True)
            elif event["type"] == "result":
                print()
                print(f"   结果: {event['result']}")
        print()

        # 10. 演示 Agent 切换
        print("10. 演示 Agent 切换:")
        async for event in o.process("@explore"):
            if event["type"] == "agent_switch":
                print(f"   {event['message']}")
        print()

    print("=" * 60)
    print("示例完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
