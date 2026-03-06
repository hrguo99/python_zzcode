"""
主编排器

整合所有模块，实现完整的对话系统工作流程。
"""

import logging
from typing import Dict, Any, List, AsyncGenerator, Optional
from pathlib import Path

from session_management import (
    UserMessage,
    AssistantMessage,
    ModelMessage,
    AgentInfo,
    ModelInfo,
    MessageRole,
    TimeInfo,
)
from agent import Agent, AgentConfig
from agent.permissions import PermissionNext
from interpreter import OpenCodeInterpreter, InterpreterConfig
from skill import SkillManager, SkillManagerConfig
from lsp import LSPManager

from .parser import InputParser, InputType
from .command_handler import CommandHandler
from .agent_switcher import AgentSwitcher
from .permission_manager import PermissionManager
from .tool_provider import ToolCollector
from .prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    主编排器

    职责：
    - 接收用户输入并分流处理
    - 协调命令处理、智能体切换、普通消息处理
    - 管理会话和工具注册
    - 集成 Agent、Skill、LSP 系统
    """

    def __init__(
        self,
        config: InterpreterConfig,
        agent_config: Optional[AgentConfig] = None,
        project_dir: str = ".",
    ):
        self.config = config
        self.project_dir = Path(project_dir).resolve()

        # 核心组件
        self.parser = InputParser()
        self.command_handler = CommandHandler()
        self.agent_switcher = AgentSwitcher()

        # Agent 管理（使用真正的 Agent 类）
        self.agent_manager = Agent(agent_config or AgentConfig())

        # Skill 管理
        self.skill_manager = SkillManager(
            SkillManagerConfig(
                project_dir=str(self.project_dir),
                worktree_dir=str(self.project_dir),
            )
        )

        # LSP 管理
        self.lsp_manager: Optional[LSPManager] = None

        # 会话管理
        self._sessions: Dict[str, List[ModelMessage]] = {}
        self._all_tools: Dict[str, Any] = {}  # 所有可用工具（包括内置工具）
        self._interpreter: Optional[OpenCodeInterpreter] = None

        # 初始化 LSP
        self._init_lsp()

        # 优化组件
        self.permission_manager = PermissionManager()
        self.tool_collector = ToolCollector(self.skill_manager, self.lsp_manager)
        self.prompt_builder = PromptBuilder(str(self.project_dir))

    def _init_lsp(self):
        """初始化 LSP 管理器（优化：添加重试机制）"""
        try:
            self.lsp_manager = LSPManager(project_dir=str(self.project_dir))
            # 更新 ToolCollector 的 LSP 引用
            if hasattr(self, 'tool_collector'):
                self.tool_collector.lsp_manager = self.lsp_manager
            logger.info(f"LSP manager initialized for {self.project_dir}")
        except Exception as e:
            logger.warning(f"Failed to initialize LSP manager: {e}")
            self.lsp_manager = None

    async def __aenter__(self):
        """初始化解释器"""
        self._interpreter = OpenCodeInterpreter(config=self.config)
        await self._interpreter.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """清理资源"""
        if self._interpreter:
            await self._interpreter.__aexit__(exc_type, exc_val, exc_tb)

    def register_tool(self, name: str, tool: Any) -> None:
        """
        注册工具到全局工具注册表

        Args:
            name: 工具名称
            tool: 工具对象
        """
        self._all_tools[name] = tool
        logger.debug(f"Registered tool: {name}")

    async def register_agent(self, name: str, agent: AgentInfo) -> None:
        """
        注册智能体

        注意：推荐使用 AgentConfig 来配置自定义 agent，
        而不是动态注册。

        Args:
            name: Agent 名称
            agent: AgentInfo 对象
        """
        self.agent_switcher.register(name, agent)
        logger.debug(f"Registered agent: {name}")

    def register_command(self, name: str, handler) -> None:
        """
        注册命令处理器

        Args:
            name: 命令名称
            handler: 处理函数
        """
        self.command_handler.register(name, handler)
        logger.debug(f"Registered command: {name}")

    async def _filter_tools_by_agent(
        self,
        agent: AgentInfo,
        all_tools: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        根据 agent 权限过滤工具（使用缓存优化）

        Args:
            agent: Agent 信息（包含权限规则）
            all_tools: 所有可用工具

        Returns:
            过滤后的工具字典
        """
        filtered_tools = {}

        for tool_name, tool in all_tools.items():
            action = self.permission_manager.evaluate(agent, tool_name)

            if action in ("allow", "ask"):
                filtered_tools[tool_name] = tool
                logger.debug(f"Tool {tool_name} {action} for agent {agent.name}")
            else:
                logger.debug(f"Tool {tool_name} denied for agent {agent.name}")

        return filtered_tools

    async def _collect_all_tools(self, agent: AgentInfo) -> Dict[str, Any]:
        """
        收集所有工具（使用 ToolCollector 优化）

        Args:
            agent: Agent 信息

        Returns:
            所有工具字典
        """
        return await self.tool_collector.collect_all(agent)

    async def process(
        self,
        user_input: str,
        session_id: str = "default",
        system: Optional[List[str]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        处理用户输入

        Args:
            user_input: 用户输入
            session_id: 会话 ID
            system: 系统提示词（可选，如果不提供则使用 agent 的 prompt）

        Yields:
            处理事件
        """
        # 1. 解析输入
        input_type, content = self.parser.parse(user_input)

        # 2. 根据输入类型分流处理
        if input_type == InputType.COMMAND:
            result = await self.command_handler.execute(content)
            yield {"type": "command_result", "result": result}
            return

        if input_type == InputType.AGENT_SWITCH:
            agent, message = await self.agent_switcher.switch(content)
            yield {"type": "agent_switch", "agent": agent, "message": message}
            return

        # 3. 普通消息处理 - 进入主循环
        yield {"type": "processing", "message": "开始处理消息"}

        # 获取/创建会话
        if session_id not in self._sessions:
            self._sessions[session_id] = []

        # 创建用户消息
        user_message = ModelMessage(
            role="user",
            content=content,
        )

        # 存储用户消息
        self._sessions[session_id].append(user_message)

        # 4. 主循环准备阶段
        # 获取历史消息
        history = self._sessions[session_id]

        # 获取当前 Agent 名称
        current_agent_name = self.agent_switcher.get_current_name()
        if not current_agent_name:
            # 使用默认 agent
            try:
                current_agent_name = await self.agent_manager.default_agent()
            except ValueError:
                # 如果没有默认 agent，使用第一个可用的
                agents = await self.agent_manager.list()
                if agents:
                    current_agent_name = agents[0].name
                else:
                    # 如果仍然没有，使用内置的 build agent
                    current_agent_name = "build"

        # 获取 Agent 信息（使用 Agent 类）
        agent = await self.agent_manager.get(current_agent_name)
        if agent is None:
            # 如果找不到 agent，使用默认配置
            agent = AgentInfo(
                name="default",
                mode="all",
                prompt=None,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
            )

        # 收集所有工具（优化：使用 ToolCollector）
        all_tools = self._all_tools.copy()

        try:
            collected_tools = await self._collect_all_tools(agent)
            all_tools.update(collected_tools)
        except Exception as e:
            logger.error(f"Failed to collect tools for agent {agent.name}: {e}")
            # Continue with built-in tools only

        # 根据 agent 权限过滤工具（优化：使用 PermissionManager 缓存）
        tools = await self._filter_tools_by_agent(agent, all_tools)

        # 验证至少有一些工具可用
        if not tools:
            logger.warning(f"No tools available for agent {agent.name}")


        # 构建系统提示词（优化：使用动态 PromptBuilder）
        if system is None:
            model_id = agent.model.model_id if agent.model else self.config.model
            system = await self.prompt_builder.build(
                model_id=model_id,
                agent_name=agent.name
            )

            # 如果 agent 有自定义 prompt，追加到末尾
            if agent.prompt:
                system.append(agent.prompt)

        # 5. AI SDK 调用与流式处理
        if not self._interpreter:
            raise RuntimeError("Orchestrator not initialized")

        # 获取模型信息
        model = ModelInfo(
            provider_id=agent.model.provider_id if agent.model else self.config.provider,
            model_id=agent.model.model_id if agent.model else self.config.model,
        )

        async with self._interpreter.session(
            session_id=session_id,
            agent=agent,
            model=model,
        ) as session:
            async for event in session.process(
                messages=history,
                tools=tools,
                system=system,
            ):
                # 转发事件
                yield event

                # 存储助手消息
                if event.get("type") == "result":
                    assistant_message = event.get("message")
                    if assistant_message:
                        self._sessions[session_id].append(assistant_message)


__all__ = ["Orchestrator"]
