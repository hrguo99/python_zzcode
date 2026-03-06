"""Permission cache manager for optimizing permission evaluations."""

from typing import Dict, Tuple
from functools import lru_cache
from session_management import AgentInfo
from agent.permissions import PermissionNext


class PermissionCache:
    """Cache for permission evaluation results."""

    def __init__(self, max_size: int = 1000):
        self._cache: Dict[Tuple[str, str, str], str] = {}
        self._max_size = max_size

    def get(self, agent_name: str, tool_name: str, pattern: str = "") -> str | None:
        """Get cached permission result."""
        key = (agent_name, tool_name, pattern)
        return self._cache.get(key)

    def set(self, agent_name: str, tool_name: str, pattern: str, result: str) -> None:
        """Cache permission result."""
        if len(self._cache) >= self._max_size:
            # Simple eviction: clear oldest half
            items = list(self._cache.items())
            self._cache = dict(items[len(items) // 2:])

        key = (agent_name, tool_name, pattern)
        self._cache[key] = result

    def clear(self) -> None:
        """Clear all cached results."""
        self._cache.clear()

    def invalidate_agent(self, agent_name: str) -> None:
        """Invalidate all cache entries for an agent."""
        self._cache = {
            k: v for k, v in self._cache.items()
            if k[0] != agent_name
        }


class PermissionManager:
    """Centralized permission management with caching."""

    def __init__(self):
        self._cache = PermissionCache()

    def evaluate(
        self,
        agent: AgentInfo,
        tool_name: str,
        pattern: str = "",
        use_cache: bool = True,
    ) -> str:
        """
        Evaluate permission with caching.

        Args:
            agent: Agent information
            tool_name: Tool name to check
            pattern: Optional pattern for permission
            use_cache: Whether to use cache

        Returns:
            Permission action: "allow", "ask", or "deny"
        """
        if use_cache:
            cached = self._cache.get(agent.name, tool_name, pattern)
            if cached is not None:
                return cached

        action = PermissionNext.evaluate(
            rules=agent.permission,
            permission=tool_name,
            pattern=pattern,
        )

        result = action.value

        if use_cache:
            self._cache.set(agent.name, tool_name, pattern, result)

        return result

    def clear_cache(self) -> None:
        """Clear permission cache."""
        self._cache.clear()

    def invalidate_agent(self, agent_name: str) -> None:
        """Invalidate cache for specific agent."""
        self._cache.invalidate_agent(agent_name)
