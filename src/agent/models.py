"""
Data models for the Agent system.

This module defines the core data structures used throughout the agent system,
corresponding to the TypeScript Zod schemas in the original implementation.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum


class AgentMode(str, Enum):
    """Agent operation modes."""
    SUBAGENT = "subagent"
    PRIMARY = "primary"
    ALL = "all"


class PermissionAction(str, Enum):
    """Permission actions."""
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


@dataclass
class ModelInfo:
    """Model information for an agent."""
    model_id: str
    provider_id: str

    def __str__(self) -> str:
        return f"{self.provider_id}/{self.model_id}"


@dataclass
class PermissionRule:
    """
    A single permission rule.

    Attributes:
        permission: The permission identifier (e.g., "edit", "bash", "read")
        action: The action to take (allow, deny, ask)
        pattern: Optional pattern for matching (e.g., file paths)
    """
    permission: str
    action: PermissionAction
    pattern: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        result = {
            "permission": self.permission,
            "action": self.action.value,
        }
        if self.pattern:
            result["pattern"] = self.pattern
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PermissionRule":
        """Create from dictionary representation."""
        return cls(
            permission=data["permission"],
            action=PermissionAction(data["action"]),
            pattern=data.get("pattern"),
        )


PermissionRuleset = List[PermissionRule]


@dataclass
class AgentInfo:
    """
    Complete agent information.

    This corresponds to the Zod schema in the original TypeScript implementation:
    ```typescript
    export const Info = z.object({
      name: z.string(),
      description: z.string().optional(),
      mode: z.enum(["subagent", "primary", "all"]),
      native: z.boolean().optional(),
      hidden: z.boolean().optional(),
      topP: z.number().optional(),
      temperature: z.number().optional(),
      color: z.string().optional(),
      permission: PermissionNext.Ruleset,
      model: z.object({
        modelID: z.string(),
        providerID: z.string(),
      }).optional(),
      variant: z.string().optional(),
      prompt: z.string().optional(),
      options: z.record(z.string(), z.any()),
      steps: z.number().int().positive().optional(),
    })
    ```

    Attributes:
        name: Unique identifier for the agent
        description: Human-readable description
        mode: Operating mode (subagent, primary, or all)
        native: Whether this is a built-in native agent
        hidden: Whether this agent should be hidden from listings
        top_p: Top-p sampling parameter
        temperature: Temperature parameter for generation
        color: Display color for UI
        permission: List of permission rules
        model: Optional model configuration
        variant: Optional model variant
        prompt: Optional custom system prompt
        options: Additional configuration options
        steps: Optional maximum steps for execution
    """
    name: str
    description: Optional[str] = None
    mode: AgentMode = AgentMode.ALL
    native: bool = False
    hidden: bool = False
    top_p: Optional[float] = None
    temperature: Optional[float] = None
    color: Optional[str] = None
    permission: PermissionRuleset = field(default_factory=list)
    model: Optional[ModelInfo] = None
    variant: Optional[str] = None
    prompt: Optional[str] = None
    options: Dict[str, Any] = field(default_factory=dict)
    steps: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "mode": self.mode.value,
            "native": self.native,
            "hidden": self.hidden,
            "topP": self.top_p,
            "temperature": self.temperature,
            "color": self.color,
            "permission": [rule.to_dict() for rule in self.permission],
            "model": {
                "modelID": self.model.model_id,
                "providerID": self.model.provider_id,
            } if self.model else None,
            "variant": self.variant,
            "prompt": self.prompt,
            "options": self.options,
            "steps": self.steps,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentInfo":
        """Create from dictionary representation."""
        model_data = data.get("model")
        model = ModelInfo(
            model_id=model_data["modelID"],
            provider_id=model_data["providerID"],
        ) if model_data else None

        permission_data = data.get("permission", [])
        permission = [PermissionRule.from_dict(p) for p in permission_data] if permission_data else []

        return cls(
            name=data["name"],
            description=data.get("description"),
            mode=AgentMode(data.get("mode", "all")),
            native=data.get("native", False),
            hidden=data.get("hidden", False),
            top_p=data.get("topP"),
            temperature=data.get("temperature"),
            color=data.get("color"),
            permission=permission,
            model=model,
            variant=data.get("variant"),
            prompt=data.get("prompt"),
            options=data.get("options", {}),
            steps=data.get("steps"),
        )

    def is_visible(self) -> bool:
        """Check if agent should be visible in listings."""
        return not self.hidden

    def is_primary(self) -> bool:
        """Check if agent can run as primary."""
        return self.mode in (AgentMode.PRIMARY, AgentMode.ALL)

    def is_subagent(self) -> bool:
        """Check if agent can run as subagent."""
        return self.mode in (AgentMode.SUBAGENT, AgentMode.ALL)


@dataclass
class GeneratedAgent:
    """
    Result from agent generation.

    This corresponds to the generateObject schema in the original implementation.
    """
    identifier: str
    when_to_use: str
    system_prompt: str

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary representation."""
        return {
            "identifier": self.identifier,
            "whenToUse": self.when_to_use,
            "systemPrompt": self.system_prompt,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "GeneratedAgent":
        """Create from dictionary representation."""
        return cls(
            identifier=data["identifier"],
            when_to_use=data["whenToUse"],
            system_prompt=data["systemPrompt"],
        )
