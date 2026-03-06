"""
Message format definitions for AI SDK.

This module provides unified message types compatible with multiple AI providers.
Inspired by OpenCode's MessageV2 format.
"""

from __future__ import annotations

from typing import Any, Literal, Union
from dataclasses import dataclass, field
from enum import Enum
import json


class Role(Enum):
    """Message role types."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class PartType(Enum):
    """Message part types."""
    TEXT = "text"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    REASONING = "reasoning"
    FILE = "file"
    STEP_START = "step_start"
    STEP_FINISH = "step_finish"


@dataclass
class TextPart:
    """Text content part."""
    type: Literal[PartType.TEXT] = field(default=PartType.TEXT, init=False)
    content: str

    def to_dict(self) -> dict:
        return {"type": "text", "text": self.content}


@dataclass
class ToolCallPart:
    """Tool call part."""
    type: Literal[PartType.TOOL_CALL] = field(default=PartType.TOOL_CALL, init=False)
    id: str
    name: str
    input: dict[str, Any]

    def to_dict(self) -> dict:
        return {
            "type": "tool_call",
            "tool_call_id": self.id,
            "tool_name": self.name,
            "tool_input": self.input
        }


@dataclass
class ToolResultPart:
    """Tool result part."""
    type: Literal[PartType.TOOL_RESULT] = field(default=PartType.TOOL_RESULT, init=False)
    id: str
    name: str
    result: str | dict[str, Any]
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "type": "tool_result",
            "tool_call_id": self.id,
            "tool_name": self.name,
            "result": self.result,
            "error": self.error
        }


@dataclass
class ReasoningPart:
    """Reasoning/thought process part."""
    type: Literal[PartType.REASONING] = field(default=PartType.REASONING, init=False)
    content: str

    def to_dict(self) -> dict:
        return {"type": "reasoning", "reasoning": self.content}


@dataclass
class FilePart:
    """File attachment part."""
    type: Literal[PartType.FILE] = field(default=PartType.FILE, init=False)
    mime_type: str
    data: bytes | str
    name: str | None = None
    url: str | None = None

    def to_dict(self) -> dict:
        return {
            "type": "file",
            "mime_type": self.mime_type,
            "data": self.data,
            "name": self.name,
            "url": self.url
        }


@dataclass
class StepStartPart:
    """Step start marker for chain-of-thought."""
    type: Literal[PartType.STEP_START] = field(default=PartType.STEP_START, init=False)
    step_id: str
    name: str

    def to_dict(self) -> dict:
        return {
            "type": "step_start",
            "step_id": self.step_id,
            "name": self.name
        }


@dataclass
class StepFinishPart:
    """Step finish marker."""
    type: Literal[PartType.STEP_FINISH] = field(default=PartType.STEP_FINISH, init=False)
    step_id: str
    name: str

    def to_dict(self) -> dict:
        return {
            "type": "step_finish",
            "step_id": self.step_id,
            "name": self.name
        }


Part = Union[
    TextPart,
    ToolCallPart,
    ToolResultPart,
    ReasoningPart,
    FilePart,
    StepStartPart,
    StepFinishPart
]


@dataclass
class Message:
    """Unified message format compatible with multiple providers."""
    role: Role
    parts: list[Part]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def user(cls, content: str | list[Part]) -> Message:
        """Create a user message."""
        if isinstance(content, str):
            parts = [TextPart(content=content)]
        else:
            parts = content
        return cls(role=Role.USER, parts=parts)

    @classmethod
    def assistant(cls, content: str | list[Part]) -> Message:
        """Create an assistant message."""
        if isinstance(content, str):
            parts = [TextPart(content=content)]
        else:
            parts = content
        return cls(role=Role.ASSISTANT, parts=parts)

    @classmethod
    def system(cls, content: str) -> Message:
        """Create a system message."""
        return cls(role=Role.SYSTEM, parts=[TextPart(content=content)])

    @classmethod
    def tool_result(cls, tool_id: str, name: str, result: str | dict, error: str | None = None) -> Message:
        """Create a tool result message."""
        return cls(
            role=Role.TOOL,
            parts=[ToolResultPart(id=tool_id, name=name, result=result, error=error)]
        )

    def to_dict(self) -> dict:
        """Convert message to dictionary format."""
        return {
            "role": self.role.value,
            "parts": [part.to_dict() for part in self.parts],
            "metadata": self.metadata
        }

    @property
    def text_content(self) -> str:
        """Get concatenated text content from all text parts."""
        return "".join(
            part.content for part in self.parts
            if isinstance(part, TextPart)
        )

    @property
    def tool_calls(self) -> list[ToolCallPart]:
        """Get all tool calls in this message."""
        return [part for part in self.parts if isinstance(part, ToolCallPart)]

    @property
    def tool_results(self) -> list[ToolResultPart]:
        """Get all tool results in this message."""
        return [part for part in self.parts if isinstance(part, ToolResultPart)]

    @property
    def files(self) -> list[FilePart]:
        """Get all file attachments in this message."""
        return [part for part in self.parts if isinstance(part, FilePart)]

    def has_tool_calls(self) -> bool:
        """Check if message contains tool calls."""
        return len(self.tool_calls) > 0

    def has_reasoning(self) -> bool:
        """Check if message contains reasoning."""
        return any(isinstance(part, ReasoningPart) for part in self.parts)

    def get_tool_call(self, tool_id: str) -> ToolCallPart | None:
        """Get a specific tool call by ID."""
        for call in self.tool_calls:
            if call.id == tool_id:
                return call
        return None


@dataclass
class ModelMessage:
    """Provider-specific message format."""
    role: str
    content: str | list[dict]
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result = {
            "role": self.role,
            "content": self.content
        }
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        return result


def to_model_messages(messages: list[Message], provider_capabilities: dict) -> list[ModelMessage]:
    """
    Convert internal messages to provider-specific format.

    Args:
        messages: Internal message list
        provider_capabilities: Provider capability flags (supports files, interleaved, etc.)

    Returns:
        List of provider-compatible messages
    """
    model_messages = []

    for msg in messages:
        # Handle system messages
        if msg.role == Role.SYSTEM:
            model_messages.append(ModelMessage(
                role="system",
                content=msg.text_content
            ))
            continue

        # Handle user/assistant messages with various parts
        content_parts = []
        tool_calls = []

        for part in msg.parts:
            if isinstance(part, TextPart):
                content_parts.append({
                    "type": "text",
                    "text": part.content
                })

            elif isinstance(part, FilePart):
                if provider_capabilities.get("supports_files", False):
                    content_parts.append({
                        "type": "image_url" if part.mime_type.startswith("image/") else "file",
                        "image_url" if part.mime_type.startswith("image/") else "file": {
                            "url": part.url if part.url else f"data:{part.mime_type};base64,{part.data}"
                        }
                    })

            elif isinstance(part, ToolCallPart):
                tool_calls.append({
                    "id": part.id,
                    "type": "function",
                    "function": {
                        "name": part.name,
                        "arguments": json.dumps(part.input)
                    }
                })

            elif isinstance(part, ToolResultPart):
                # Tool result messages are separate
                model_messages.append(ModelMessage(
                    role="tool",
                    content=part.result if isinstance(part.result, str) else json.dumps(part.result),
                    tool_call_id=part.id
                ))

        # Create the message
        if msg.role == Role.USER:
            # For user messages, content can be string or list
            if len(content_parts) == 1 and content_parts[0]["type"] == "text":
                content = content_parts[0]["text"]
            else:
                content = content_parts

            model_messages.append(ModelMessage(role="user", content=content))

        elif msg.role == Role.ASSISTANT:
            # Assistant messages can have tool calls
            if tool_calls:
                model_messages.append(ModelMessage(
                    role="assistant",
                    content=msg.text_content or "",
                    tool_calls=tool_calls
                ))
            else:
                model_messages.append(ModelMessage(
                    role="assistant",
                    content=msg.text_content
                ))

    return model_messages


def format_tool_results(messages: list[Message]) -> list[dict]:
    """
    Format tool results for providers that need special handling.

    Args:
        messages: List of messages with tool results

    Returns:
        Formatted tool result dictionaries
    """
    results = []

    for msg in messages:
        for result_part in msg.tool_results:
            results.append({
                "tool_call_id": result_part.id,
                "role": "tool",
                "content": result_part.result if isinstance(result_part.result, str) else json.dumps(result_part.result)
            })

    return results
