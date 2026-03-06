"""
Interaction tracker for AI SDK.

This module tracks and logs all AI interactions for debugging, analysis, and optimization.
Inspired by OpenCode's interaction tracking system.
"""

from __future__ import annotations

from typing import Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json
import asyncio
from pathlib import Path


@dataclass
class InteractionInput:
    """Input data for an AI interaction."""
    session_id: str | None
    provider_id: str
    model_id: str
    messages: list[dict]
    tools: list[str]
    temperature: float | None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class InteractionOutput:
    """Output data from an AI interaction."""
    text: str
    tool_calls: list[dict[str, Any]]
    finish_reason: str
    usage: dict[str, int] | None
    reasoning: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Interaction:
    """Complete record of an AI interaction."""
    id: str
    timestamp: str
    input: InteractionInput
    output: InteractionOutput | None = None
    error: str | None = None
    duration_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert interaction to dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "input": asdict(self.input),
            "output": asdict(self.output) if self.output else None,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }

    def to_markdown(self) -> str:
        """Convert interaction to markdown format."""
        lines = [
            f"# AI Interaction - {self.id}",
            f"",
            f"**Timestamp:** {self.timestamp}",
            f"**Session:** {self.input.session_id or 'N/A'}",
            f"**Model:** {self.input.provider_id}/{self.input.model_id}",
            f"",
        ]

        if self.duration_ms:
            lines.append(f"**Duration:** {self.duration_ms:.2f}ms")
            lines.append("")

        # Input section
        lines.append("## Input")
        lines.append("")
        lines.append(f"**Temperature:** {self.input.temperature}")
        lines.append(f"**Tools:** {', '.join(self.input.tools) if self.input.tools else 'None'}")
        lines.append("")
        lines.append("### Messages")
        lines.append("")

        for i, msg in enumerate(self.input.messages, 1):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            lines.append(f"#### Message {i} - {role.upper()}")
            lines.append("")

            if isinstance(content, str):
                lines.append(content)
            elif isinstance(content, list):
                for part in content:
                    if part.get("type") == "text":
                        lines.append(part.get("text", ""))
            lines.append("")

        # Output section
        if self.output:
            lines.append("## Output")
            lines.append("")

            if self.output.reasoning:
                lines.append("### Reasoning")
                lines.append("")
                lines.append(self.output.reasoning)
                lines.append("")

            lines.append("### Response")
            lines.append("")
            lines.append(self.output.text)
            lines.append("")

            if self.output.tool_calls:
                lines.append("### Tool Calls")
                lines.append("")
                for tool_call in self.output.tool_calls:
                    lines.append(f"- **{tool_call.get('name', 'unknown')}**")
                    lines.append(f"  - ID: `{tool_call.get('id', 'N/A')}`")
                    lines.append(f"  - Arguments: ```json")
                    lines.append(f"    {json.dumps(tool_call.get('arguments', {}), indent=2)}")
                    lines.append(f"    ```")
                    lines.append("")

            if self.output.usage:
                lines.append("### Usage")
                lines.append("")
                lines.append(f"- **Prompt Tokens:** {self.output.usage.get('prompt_tokens', 'N/A')}")
                lines.append(f"- **Completion Tokens:** {self.output.usage.get('completion_tokens', 'N/A')}")
                lines.append(f"- **Total Tokens:** {self.output.usage.get('total_tokens', 'N/A')}")
                lines.append("")

            lines.append(f"**Finish Reason:** {self.output.finish_reason}")
            lines.append("")

        # Error section
        if self.error:
            lines.append("## Error")
            lines.append("")
            lines.append(f"```")
            lines.append(self.error)
            lines.append(f"```")
            lines.append("")

        return "\n".join(lines)


class InteractionTracker:
    """
    Tracks AI interactions for debugging and analysis.

    This class automatically logs all AI interactions to files and provides
    utilities for analyzing and exporting the data.

    Example:
        ```python
        tracker = InteractionTracker(log_dir="./interactions")

        llm = LLM(tracker=tracker)
        response = await llm.stream(messages=[...])

        # Automatically saves to:
        # ./interactions/interaction_20240304_123456.json
        ```
    """

    def __init__(
        self,
        log_dir: str = "./interactions",
        auto_save: bool = True,
        save_format: str = "both",  # "json", "markdown", or "both"
    ):
        """
        Initialize interaction tracker.

        Args:
            log_dir: Directory to save interaction logs
            auto_save: Whether to automatically save interactions
            save_format: Format to save in ("json", "markdown", or "both")
        """
        self.log_dir = Path(log_dir)
        self.auto_save = auto_save
        self.save_format = save_format

        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Current interaction
        self._current_interaction: Optional[Interaction] = None
        self._start_time: Optional[datetime] = None

    async def track_start(
        self,
        session_id: str | None,
        provider_id: str,
        model_id: str,
        messages: list[dict],
        tools: list[str],
        temperature: float | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Start tracking a new interaction.

        Args:
            session_id: Optional session ID
            provider_id: Provider ID
            model_id: Model ID
            messages: Conversation messages
            tools: Available tools
            temperature: Sampling temperature
            metadata: Optional metadata
        """
        self._current_interaction = Interaction(
            id=self._generate_id(),
            timestamp=datetime.now().isoformat(),
            input=InteractionInput(
                session_id=session_id,
                provider_id=provider_id,
                model_id=model_id,
                messages=messages,
                tools=tools,
                temperature=temperature,
                metadata=metadata or {},
            ),
        )
        self._start_time = datetime.now()

    async def track_complete(
        self,
        text: str,
        tool_calls: list[dict[str, Any]],
        finish_reason: str,
        usage: dict[str, int] | None,
        reasoning: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Mark interaction as complete.

        Args:
            text: Generated text
            tool_calls: Tool calls made
            finish_reason: Finish reason
            usage: Token usage
            reasoning: Optional reasoning/thought process
            metadata: Optional metadata
        """
        if not self._current_interaction:
            return

        # Calculate duration
        if self._start_time:
            duration = (datetime.now() - self._start_time).total_seconds() * 1000
            self._current_interaction.duration_ms = duration

        # Set output
        self._current_interaction.output = InteractionOutput(
            text=text,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
            reasoning=reasoning,
            metadata=metadata or {},
        )

        # Save if auto-save is enabled
        if self.auto_save:
            await self.save(self._current_interaction)

        # Reset
        self._current_interaction = None
        self._start_time = None

    async def track_error(self, error: str) -> None:
        """
        Mark interaction as errored.

        Args:
            error: Error message
        """
        if not self._current_interaction:
            return

        # Calculate duration
        if self._start_time:
            duration = (datetime.now() - self._start_time).total_seconds() * 1000
            self._current_interaction.duration_ms = duration

        # Set error
        self._current_interaction.error = error

        # Save if auto-save is enabled
        if self.auto_save:
            await self.save(self._current_interaction)

        # Reset
        self._current_interaction = None
        self._start_time = None

    async def save(self, interaction: Interaction) -> None:
        """
        Save interaction to file.

        Args:
            interaction: Interaction to save
        """
        # Generate filename
        timestamp = datetime.fromisoformat(interaction.timestamp).strftime("%Y%m%d_%H%M%S")
        base_name = f"interaction_{timestamp}_{interaction.id[:8]}"

        # Save JSON
        if self.save_format in ("json", "both"):
            json_path = self.log_dir / f"{base_name}.json"
            with open(json_path, "w") as f:
                json.dump(interaction.to_dict(), f, indent=2)

        # Save Markdown
        if self.save_format in ("markdown", "both"):
            md_path = self.log_dir / f"{base_name}.md"
            with open(md_path, "w") as f:
                f.write(interaction.to_markdown())

    def _generate_id(self) -> str:
        """Generate a unique interaction ID."""
        import uuid
        return str(uuid.uuid4())

    async def load(self, interaction_id: str) -> Interaction | None:
        """
        Load an interaction by ID.

        Args:
            interaction_id: Interaction ID

        Returns:
            Interaction object or None if not found
        """
        # Find the file
        for json_file in self.log_dir.glob(f"interaction_*_{interaction_id[:8]}.json"):
            with open(json_file) as f:
                data = json.load(f)
                return self._dict_to_interaction(data)
        return None

    def _dict_to_interaction(self, data: dict) -> Interaction:
        """Convert dictionary to Interaction object."""
        input_data = data["input"]
        output_data = data.get("output")

        return Interaction(
            id=data["id"],
            timestamp=data["timestamp"],
            input=InteractionInput(
                session_id=input_data["session_id"],
                provider_id=input_data["provider_id"],
                model_id=input_data["model_id"],
                messages=input_data["messages"],
                tools=input_data["tools"],
                temperature=input_data.get("temperature"),
                metadata=input_data.get("metadata", {}),
            ),
            output=InteractionOutput(
                text=output_data["text"],
                tool_calls=output_data["tool_calls"],
                finish_reason=output_data["finish_reason"],
                usage=output_data.get("usage"),
                reasoning=output_data.get("reasoning"),
                metadata=output_data.get("metadata", {}),
            ) if output_data else None,
            error=data.get("error"),
            duration_ms=data.get("duration_ms"),
            metadata=data.get("metadata", {}),
        )

    async def list_interactions(self) -> list[Interaction]:
        """
        List all saved interactions.

        Returns:
            List of Interaction objects
        """
        interactions = []

        for json_file in self.log_dir.glob("interaction_*.json"):
            try:
                with open(json_file) as f:
                    data = json.load(f)
                    interactions.append(self._dict_to_interaction(data))
            except (json.JSONDecodeError, KeyError):
                continue

        # Sort by timestamp
        interactions.sort(key=lambda x: x.timestamp, reverse=True)
        return interactions

    async def get_stats(self) -> dict[str, Any]:
        """
        Get statistics about all interactions.

        Returns:
            Dictionary with statistics
        """
        interactions = await self.list_interactions()

        total_tokens = 0
        total_cost = 0
        error_count = 0
        tool_call_count = 0

        for interaction in interactions:
            if interaction.error:
                error_count += 1

            if interaction.output and interaction.output.usage:
                total_tokens += interaction.output.usage.get("total_tokens", 0)

            if interaction.output:
                tool_call_count += len(interaction.output.tool_calls)

        return {
            "total_interactions": len(interactions),
            "total_tokens": total_tokens,
            "error_count": error_count,
            "tool_call_count": tool_call_count,
            "error_rate": error_count / len(interactions) if interactions else 0,
        }
