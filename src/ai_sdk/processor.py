"""
Session processor for AI SDK.

This module manages the complete lifecycle of AI sessions, including context management,
tool execution, and retry logic.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import uuid

from .message import Message, Role
from .tool import Tool, ToolRegistry, ToolCall
from .llm import LLM, StreamChunk


class SessionStatus(Enum):
    """Session status."""
    IDLE = "idle"
    BUSY = "busy"
    RETRY = "retry"
    ERROR = "error"


@dataclass
class Session:
    """Represents an AI conversation session."""
    id: str
    model: str
    provider: str
    system_prompts: list[str] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    tools: dict[str, Tool] = field(default_factory=dict)
    status: SessionStatus = SessionStatus.IDLE
    max_retries: int = 3
    retry_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_message(self, message: Message) -> None:
        """Add a message to the session."""
        self.messages.append(message)

    def add_user_message(self, content: str) -> None:
        """Add a user message to the session."""
        self.add_message(Message.user(content))

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to the session."""
        self.add_message(Message.assistant(content))

    def get_messages(self) -> list[Message]:
        """Get all messages in the session."""
        return self.messages.copy()

    def clear_messages(self) -> None:
        """Clear all messages from the session."""
        self.messages = []

    def set_status(self, status: SessionStatus) -> None:
        """Set the session status."""
        self.status = status


@dataclass
class ProcessResult:
    """Result of processing a user message."""
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessorConfig:
    """Configuration for session processor."""
    max_context_messages: int = 50
    max_retries: int = 3
    retry_delay: float = 1.0
    auto_execute_tools: bool = True
    tool_timeout: float = 30.0


class SessionProcessor:
    """
    Processes AI sessions with context management and tool execution.

    This class handles the complete lifecycle of AI conversations, including:
    - Message history management
    - Tool calling and execution
    - Automatic retry on errors
    - Context window management

    Example:
        ```python
        processor = SessionProcessor()

        session = await processor.create_session(
            model="gpt-4",
            provider="openai",
            system_prompt="You are a helpful assistant"
        )

        result = await processor.process(
            session=session,
            user_message="What's the weather in San Francisco?",
            tools={"get_weather": weather_tool}
        )
        ```
    """

    def __init__(
        self,
        llm: LLM | None = None,
        config: ProcessorConfig | None = None,
    ):
        """
        Initialize session processor.

        Args:
            llm: Optional LLM instance (will create default if not provided)
            config: Optional processor configuration
        """
        self.llm = llm
        self.config = config or ProcessorConfig()
        self._sessions: dict[str, Session] = {}

    async def create_session(
        self,
        model: str,
        provider: str = "openai",
        system_prompt: str | list[str] | None = None,
        tools: dict[str, Tool] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Session:
        """
        Create a new session.

        Args:
            model: Model ID to use
            provider: Provider ID
            system_prompt: Optional system prompt(s)
            tools: Optional tools for the session
            metadata: Optional metadata

        Returns:
            New Session instance
        """
        session_id = str(uuid.uuid4())

        # Normalize system prompts
        system_prompts = []
        if system_prompt:
            if isinstance(system_prompt, str):
                system_prompts = [system_prompt]
            else:
                system_prompts = system_prompt

        # Create session
        session = Session(
            id=session_id,
            model=model,
            provider=provider,
            system_prompts=system_prompts,
            tools=tools or {},
            metadata=metadata or {},
        )

        self._sessions[session_id] = session
        return session

    async def process(
        self,
        session: Session,
        user_message: str,
        tools: dict[str, Tool] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> ProcessResult:
        """
        Process a user message through the session.

        Args:
            session: Session to process
            user_message: User's message
            tools: Optional tools to use for this request
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            ProcessResult with the response
        """
        if session.status == SessionStatus.BUSY:
            raise RuntimeError("Session is busy, please wait for current request to complete")

        session.set_status(SessionStatus.BUSY)

        try:
            # Add user message to session
            session.add_user_message(user_message)

            # Prepare tools
            all_tools = {**session.tools}
            if tools:
                all_tools.update(tools)

            # Generate response
            result = await self._generate_with_retry(
                session=session,
                tools=all_tools,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Handle tool calls if enabled
            if self.config.auto_execute_tools and result.tool_calls:
                result = await self._execute_tools(
                    session=session,
                    tool_calls=result.tool_calls,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

            # Add assistant message to session
            session.add_assistant_message(result.text)

            session.set_status(SessionStatus.IDLE)
            return result

        except Exception as e:
            session.set_status(SessionStatus.ERROR)
            return ProcessResult(
                text="",
                error=str(e),
            )

    async def process_stream(
        self,
        session: Session,
        user_message: str,
        tools: dict[str, Tool] | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        Process a user message with streaming response.

        Args:
            session: Session to process
            user_message: User's message
            tools: Optional tools to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Yields:
            StreamChunk objects with partial results
        """
        if session.status == SessionStatus.BUSY:
            raise RuntimeError("Session is busy")

        session.set_status(SessionStatus.BUSY)

        # Add user message to session
        session.add_user_message(user_message)

        # Prepare tools
        all_tools = {**session.tools}
        if tools:
            all_tools.update(tools)

        try:
            # Create LLM if needed
            llm = self._get_llm_for_session(session)

            # Stream response
            full_text = ""
            async for chunk in llm.stream(
                messages=session.get_messages(),
                tools=all_tools,
                system=session.system_prompts,
                temperature=temperature,
                max_tokens=max_tokens,
                session_id=session.id,
            ):
                if chunk.text:
                    full_text += chunk.text
                yield chunk

            # Add assistant message to session
            session.add_assistant_message(full_text)
            session.set_status(SessionStatus.IDLE)

        except Exception as e:
            session.set_status(SessionStatus.ERROR)
            raise

    async def _generate_with_retry(
        self,
        session: Session,
        tools: dict[str, Tool],
        temperature: float,
        max_tokens: int | None,
    ) -> ProcessResult:
        """Generate response with automatic retry on errors."""
        retry_count = 0
        last_error = None

        while retry_count <= session.max_retries:
            try:
                # Create LLM if needed
                llm = self._get_llm_for_session(session)

                # Generate response
                result = await llm.generate(
                    messages=session.get_messages(),
                    tools=tools,
                    system=session.system_prompts,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    session_id=session.id,
                )

                return ProcessResult(
                    text=result.text,
                    tool_calls=result.tool_calls,
                    finish_reason=result.finish_reason,
                    usage=result.usage,
                )

            except Exception as e:
                last_error = e
                retry_count += 1
                session.retry_count = retry_count

                if retry_count <= session.max_retries:
                    session.set_status(SessionStatus.RETRY)
                    await asyncio.sleep(self.config.retry_delay * retry_count)
                else:
                    raise

        raise last_error if last_error else RuntimeError("Max retries exceeded")

    async def _execute_tools(
        self,
        session: Session,
        tool_calls: list[ToolCall],
        temperature: float,
        max_tokens: int | None,
    ) -> ProcessResult:
        """Execute tool calls and get final response."""
        # Execute all tools
        for tool_call in tool_calls:
            try:
                # Execute with timeout
                result = await asyncio.wait_for(
                    tool_call.execute(),
                    timeout=self.config.tool_timeout,
                )

                # Add tool result to session
                session.add_message(Message.tool_result(
                    tool_id=tool_call.id,
                    name=tool_call.name,
                    result=result.output if result.success else result.error or "",
                ))

            except asyncio.TimeoutError:
                # Add timeout error
                session.add_message(Message.tool_result(
                    tool_id=tool_call.id,
                    name=tool_call.name,
                    result="",
                    error="Tool execution timeout",
                ))

            except Exception as e:
                # Add execution error
                session.add_message(Message.tool_result(
                    tool_id=tool_call.id,
                    name=tool_call.name,
                    result="",
                    error=str(e),
                ))

        # Get final response after tool execution
        return await self._generate_with_retry(
            session=session,
            tools={},  # Don't use tools for the final response
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def _get_llm_for_session(self, session: Session) -> LLM:
        """Get or create LLM instance for session."""
        if self.llm is None:
            return LLM(provider=session.provider, model=session.model)
        return self.llm

    def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session by ID."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_sessions(self) -> list[Session]:
        """List all sessions."""
        return list(self._sessions.values())
