"""
Core Agent management class.

This module provides the main Agent class for managing agent lifecycle and operations.
Corresponds to the Agent namespace in agent.ts.
"""

import asyncio
from typing import Dict, Optional, List
from .models import AgentInfo, AgentMode, GeneratedAgent, ModelInfo
from .permissions import PermissionNext
from .builtin_agents import BuiltinAgents


class AgentConfig:
    """
    Configuration for the Agent system.

    This class holds the configuration that affects agent behavior,
    similar to how the original implementation reads from Config.
    """

    def __init__(
        self,
        default_agent: Optional[str] = None,
        permissions: Optional[dict] = None,
        agents: Optional[dict] = None,
        whitelisted_dirs: Optional[List[str]] = None,
    ):
        """
        Initialize AgentConfig.

        Args:
            default_agent: Name of the default agent to use
            permissions: User-defined permission rules
            agents: Custom agent configurations
            whitelisted_dirs: List of whitelisted directories
        """
        self.default_agent = default_agent
        self.permissions = permissions or {}
        self.agents = agents or {}
        self.whitelisted_dirs = whitelisted_dirs or []


class Agent:
    """
    Main Agent management class.

    This class provides methods to get, list, and generate agents.
    It manages the agent state and provides access to built-in and custom agents.

    Corresponds to the Agent namespace in the original TypeScript implementation.
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        """
        Initialize the Agent manager.

        Args:
            config: Optional AgentConfig instance
        """
        self.config = config or AgentConfig()
        self._state: Optional[Dict[str, AgentInfo]] = None

    async def _load_state(self) -> Dict[str, AgentInfo]:
        """
        Load and initialize the agent state.

        This builds the complete agent registry by:
        1. Loading all built-in agents
        2. Applying custom agent configurations from config
        3. Ensuring Truncate.GLOB is allowed unless explicitly denied

        Returns:
            Dictionary mapping agent names to AgentInfo objects
        """
        if self._state is not None:
            return self._state

        # Start with built-in agents
        result = BuiltinAgents.get_all_builtin_agents(
            custom_permissions=self.config.permissions,
            whitelisted_dirs=self.config.whitelisted_dirs,
        )

        # Apply custom agent configurations
        for name, agent_config in self.config.agents.items():
            if agent_config.get("disable"):
                # Remove disabled agent
                if name in result:
                    del result[name]
                continue

            # Get or create agent info
            if name not in result:
                result[name] = AgentInfo(
                    name=name,
                    mode=AgentMode.ALL,
                    permission=BuiltinAgents.get_default_permissions(
                        custom_permissions=self.config.permissions,
                    ),
                    options={},
                    native=False,
                )

            agent = result[name]

            # Apply overrides from config
            if "model" in agent_config:
                model_data = agent_config["model"]
                if isinstance(model_data, str) and "/" in model_data:
                    provider_id, model_id = model_data.split("/", 1)
                    agent.model = ModelInfo(
                        provider_id=provider_id,
                        model_id=model_id,
                    )

            agent.variant = agent_config.get("variant", agent.variant)
            agent.prompt = agent_config.get("prompt", agent.prompt)
            agent.description = agent_config.get("description", agent.description)
            agent.temperature = agent_config.get("temperature", agent.temperature)
            agent.top_p = agent_config.get("top_p", agent.top_p)
            agent.mode = AgentMode(agent_config.get("mode", agent.mode.value))
            agent.color = agent_config.get("color", agent.color)
            agent.hidden = agent_config.get("hidden", agent.hidden)
            agent.name = agent_config.get("name", agent.name)
            agent.steps = agent_config.get("steps", agent.steps)

            # Merge options
            if "options" in agent_config:
                agent.options.update(agent_config["options"])

            # Merge permissions
            if "permission" in agent_config:
                custom_perms = PermissionNext.from_config(agent_config["permission"])
                agent.permission = PermissionNext.merge(agent.permission, custom_perms)

        # Ensure Truncate.GLOB is allowed unless explicitly configured
        # Note: This is a placeholder for the actual Truncate.GLOB constant
        # In a full implementation, this would reference the actual truncate module
        for name, agent in result.items():
            # Check if there's an explicit deny for the truncate glob
            explicit_deny = any(
                r.permission == "external_directory"
                and r.action.value == "deny"
                and r.pattern == "**/.opencode/truncate/*"
                for r in agent.permission
            )
            if not explicit_deny:
                # Add allow rule for truncate glob
                agent.permission = PermissionNext.merge(
                    agent.permission,
                    PermissionNext.from_config({
                        "external_directory": {
                            "**/.opencode/truncate/*": "allow",
                        },
                    }),
                )

        self._state = result
        return result

    async def get(self, agent_name: str) -> Optional[AgentInfo]:
        """
        Get an agent by name.

        Args:
            agent_name: Name of the agent to retrieve

        Returns:
            AgentInfo if found, None otherwise
        """
        state = await self._load_state()
        return state.get(agent_name)

    async def list(self) -> List[AgentInfo]:
        """
        List all available agents.

        Returns agents sorted with the default agent first (if configured),
        then alphabetically by name.

        Returns:
            List of AgentInfo objects
        """
        state = await self._load_state()

        # Sort: default agent first (if set), then by name
        def sort_key(agent: AgentInfo) -> tuple:
            if self.config.default_agent and agent.name == self.config.default_agent:
                return (0, agent.name)
            return (1, agent.name)

        return sorted(state.values(), key=sort_key)

    async def default_agent(self) -> str:
        """
        Get the name of the default agent.

        Returns the configured default agent if valid, otherwise the first
        visible primary agent.

        Returns:
            Name of the default agent

        Raises:
            ValueError: If no valid default agent can be found
        """
        state = await self._load_state()

        if self.config.default_agent:
            agent = state.get(self.config.default_agent)
            if not agent:
                raise ValueError(f'Default agent "{self.config.default_agent}" not found')
            if agent.mode == AgentMode.SUBAGENT:
                raise ValueError(f'Default agent "{self.config.default_agent}" is a subagent')
            if agent.hidden:
                raise ValueError(f'Default agent "{self.config.default_agent}" is hidden')
            return agent.name

        # Find first visible primary agent
        for agent in state.values():
            if agent.is_primary() and agent.is_visible():
                return agent.name

        raise ValueError("No primary visible agent found")

    async def generate(
        self,
        description: str,
        model: Optional[ModelInfo] = None,
    ) -> GeneratedAgent:
        """
        Generate a new agent configuration based on a description.

        This method uses an LLM to generate an appropriate agent configuration
        for the given description. In the original implementation, this uses
        the AI SDK's generateObject function.

        Args:
            description: Description of the desired agent
            model: Optional model to use for generation

        Returns:
            GeneratedAgent with identifier, when_to_use, and system_prompt

        Note:
            This is a placeholder implementation. The full implementation would:
            1. Load the PROMPT_GENERATE template
            2. Call the LLM with structured output
            3. Parse and return the result
        """
        # Get list of existing agents to avoid name conflicts
        existing = await self.list()
        existing_names = [agent.name for agent in existing]

        # In a full implementation, this would:
        # 1. Load the prompt template from generate.txt
        # 2. Call the LLM with the description
        # 3. Return structured output

        # For now, return a placeholder
        return GeneratedAgent(
            identifier="custom_agent",
            when_to_use=f"Use this agent for: {description}",
            system_prompt=f"You are a custom agent designed to: {description}",
        )

    def reset_state(self):
        """
        Reset the cached agent state.

        This forces a reload of the agent configuration on next access.
        Useful for testing or when configuration changes.
        """
        self._state = None


# Convenience functions for backward compatibility
async def get_agent(agent_name: str, config: Optional[AgentConfig] = None) -> Optional[AgentInfo]:
    """
    Get an agent by name.

    Convenience function that creates an Agent instance and retrieves the agent.
    """
    manager = Agent(config)
    return await manager.get(agent_name)


async def list_agents(config: Optional[AgentConfig] = None) -> List[AgentInfo]:
    """
    List all available agents.

    Convenience function that creates an Agent instance and lists agents.
    """
    manager = Agent(config)
    return await manager.list()


async def get_default_agent_name(config: Optional[AgentConfig] = None) -> str:
    """
    Get the name of the default agent.

    Convenience function that creates an Agent instance and gets the default.
    """
    manager = Agent(config)
    return await manager.default_agent()
