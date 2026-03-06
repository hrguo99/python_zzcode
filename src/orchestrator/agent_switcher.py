"""
智能体切换器

处理以 @ 开头的智能体切换输入。
"""

from typing import Dict, Optional
from session_management import AgentInfo


class AgentSwitcher:
    """
    智能体切换器

    职责：解析目标 Agent、获取配置、切换当前 Agent
    """

    def __init__(self):
        self._agents: Dict[str, AgentInfo] = {}
        self._current_agent: Optional[str] = None

    def register(self, name: str, agent: AgentInfo) -> None:
        """注册智能体"""
        self._agents[name] = agent

    async def switch(self, agent_input: str) -> tuple[Optional[AgentInfo], str]:
        """
        切换智能体

        Args:
            agent_input: 智能体名称（不含 @ 前缀）

        Returns:
            (智能体配置, 确认消息)
        """
        agent_name = agent_input.strip()

        if not agent_name:
            return None, "请指定智能体名称"

        agent = self._agents.get(agent_name)
        if not agent:
            available = ", ".join(self._agents.keys())
            return None, f"未知智能体: {agent_name}。可用: {available}"

        self._current_agent = agent_name
        return agent, f"已切换到智能体: {agent_name}"

    def get_current(self) -> Optional[AgentInfo]:
        """获取当前智能体"""
        if self._current_agent:
            return self._agents.get(self._current_agent)
        return None

    def get_current_name(self) -> Optional[str]:
        """获取当前智能体名称"""
        return self._current_agent


__all__ = ["AgentSwitcher"]
