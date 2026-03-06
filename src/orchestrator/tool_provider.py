"""Tool provider abstraction for collecting tools from different sources."""

from typing import Dict, Any
from agent.models import AgentInfo
from skill import SkillManager
from lsp import LSPManager
from tool.factory import ToolFactory
import logging

logger = logging.getLogger(__name__)


class ToolCollector:
    """Collects tools from various sources (skills, LSP, built-in)."""

    def __init__(self, skill_manager: SkillManager, lsp_manager: LSPManager = None):
        self.skill_manager = skill_manager
        self.lsp_manager = lsp_manager

    async def collect_all(self, agent: AgentInfo) -> Dict[str, Any]:
        """Collect all available tools for an agent."""
        tools = {}

        # Collect from each source
        tools.update(await self._collect_skills(agent))
        tools.update(await self._collect_lsp(agent))

        return tools

    async def _collect_skills(self, agent: AgentInfo) -> Dict[str, Any]:
        """Collect skill tools."""
        from ai_sdk.tool import Tool as AI_SDK_Tool
        from agent.permissions import PermissionNext

        skill_tools = {}

        try:
            all_skills = await self.skill_manager.all()
            filtered_skills = await self.skill_manager.filter_by_permissions(
                list(all_skills.values()),
                lambda perm, pattern: PermissionNext.evaluate(
                    rules=agent.permission,
                    permission=perm,
                    pattern=pattern,
                ).value,
            )

            for skill in filtered_skills:
                async def skill_executor(skill_name: str = skill.name) -> str:
                    return f"Skill {skill_name} executed"

                skill_tools[f"skill:{skill.name}"] = AI_SDK_Tool(
                    name=f"skill:{skill.name}",
                    description=skill.description,
                    input_schema={"type": "object", "properties": {}},
                    execute=skill_executor,
                )
        except Exception as e:
            logger.error(f"Failed to collect skills: {e}")

        return skill_tools

    async def _collect_lsp(self, agent: AgentInfo) -> Dict[str, Any]:
        """Collect LSP tools using factory pattern."""
        from agent.permissions import PermissionNext

        if not self.lsp_manager:
            return {}

        try:
            action = PermissionNext.evaluate(
                rules=agent.permission,
                permission="lsp",
            )

            if action.value == "allow":
                return ToolFactory.create_lsp_tools(self.lsp_manager)
            else:
                logger.debug(f"LSP tools denied for agent {agent.name}")
        except Exception as e:
            logger.error(f"Failed to collect LSP tools: {e}")

        return {}
