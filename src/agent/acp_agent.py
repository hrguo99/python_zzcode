"""
ACP (Agent Client Protocol) Agent implementation.

This module provides the ACP-compliant agent implementation for session management,
tool execution, and protocol communication.

Corresponds to the ACP.Agent class in acp/agent.ts.
"""

import asyncio
from typing import Dict, Optional, List, Any
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

from .models import AgentInfo, ModelInfo, PermissionAction
from .agent import Agent


class ToolKind(str, Enum):
    """Tool kinds for ACP protocol."""
    EXECUTE = "execute"
    FETCH = "fetch"
    EDIT = "edit"
    SEARCH = "search"
    READ = "read"
    OTHER = "other"


class ToolStatus(str, Enum):
    """Tool execution status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ToolCall:
    """A tool call representation."""
    call_id: str
    tool: str
    status: ToolStatus
    title: Optional[str] = None
    input: Dict[str, Any] = field(default_factory=dict)
    output: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionInfo:
    """Session information."""
    id: str
    cwd: str
    mode_id: Optional[str] = None
    model: Optional[ModelInfo] = None
    variant: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)


class ACPAgent:
    """
    ACP-compliant Agent implementation.

    This class handles:
    - Session lifecycle (create, load, fork, resume)
    - Tool execution and monitoring
    - Permission requests
    - Model and mode management
    - Event streaming

    Corresponds to the ACP.Agent class in the original TypeScript implementation.
    """

    def __init__(
        self,
        agent_manager: Agent,
        connection: Optional["ACPSessionConnection"] = None,
    ):
        """
        Initialize the ACP Agent.

        Args:
            agent_manager: Agent instance for managing agents
            connection: Optional ACP connection for protocol communication
        """
        self.agent_manager = agent_manager
        self.connection = connection
        self.sessions: Dict[str, SessionInfo] = {}
        self.tool_calls: Dict[str, ToolCall] = {}
        self.permission_options = [
            {"optionId": "once", "kind": "allow_once", "name": "Allow once"},
            {"optionId": "always", "kind": "allow_always", "name": "Always allow"},
            {"optionId": "reject", "kind": "reject_once", "name": "Reject"},
        ]

    async def initialize(self, protocol_version: int) -> Dict[str, Any]:
        """
        Initialize the ACP protocol connection.

        Args:
            protocol_version: Protocol version from client

        Returns:
            Initialization response with capabilities and info
        """
        return {
            "protocolVersion": 1,
            "agentCapabilities": {
                "loadSession": True,
                "mcpCapabilities": {
                    "http": True,
                    "sse": True,
                },
                "promptCapabilities": {
                    "embeddedContext": True,
                    "image": True,
                },
                "sessionCapabilities": {
                    "fork": {},
                    "list": {},
                    "resume": {},
                },
            },
            "authMethods": [
                {
                    "id": "opencode-login",
                    "name": "Login with OpenCode",
                    "description": "Run `opencode auth login` in the terminal",
                }
            ],
            "agentInfo": {
                "name": "OpenCode",
                "version": "0.1.0",
            },
        }

    async def authenticate(self, auth_method: str, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Authenticate a client connection.

        Args:
            auth_method: Authentication method identifier
            credentials: Authentication credentials

        Returns:
            Authentication result

        Raises:
            NotImplementedError: If authentication is not implemented
        """
        raise NotImplementedError("Authentication not implemented")

    async def new_session(
        self,
        cwd: str,
        mcp_servers: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new session.

        Args:
            cwd: Working directory for the session
            mcp_servers: Optional list of MCP server configurations

        Returns:
            Session creation response with sessionId, models, and modes
        """
        # Generate session ID (in real implementation, this would be a UUID)
        session_id = f"session_{len(self.sessions) + 1}_{int(asyncio.get_event_loop().time())}"

        # Get default model and agent
        default_agent_name = await self.agent_manager.default_agent()
        default_agent = await self.agent_manager.get(default_agent_name)

        # Create session info
        session = SessionInfo(
            id=session_id,
            cwd=cwd,
            mode_id=default_agent_name,
            model=default_agent.model if default_agent else None,
        )

        self.sessions[session_id] = session

        # Build response
        response = {
            "sessionId": session_id,
            "models": await self._load_models(cwd),
            "modes": await self._load_modes(cwd),
        }

        return response

    async def load_session(
        self,
        session_id: str,
        cwd: str,
        mcp_servers: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Load an existing session.

        Args:
            session_id: ID of session to load
            cwd: Working directory for the session
            mcp_servers: Optional list of MCP server configurations

        Returns:
            Session loading response with models, modes, and history
        """
        # In a real implementation, this would load session from storage
        # For now, create a new session-like structure
        session = SessionInfo(
            id=session_id,
            cwd=cwd,
        )

        self.sessions[session_id] = session

        # Build response
        response = {
            "sessionId": session_id,
            "models": await self._load_models(cwd),
            "modes": await self._load_modes(cwd),
        }

        return response

    async def list_sessions(
        self,
        cwd: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        List available sessions.

        Args:
            cwd: Optional working directory filter
            cursor: Optional cursor for pagination
            limit: Maximum number of sessions to return

        Returns:
            List of sessions with optional next cursor
        """
        # In a real implementation, this would query session storage
        sessions = list(self.sessions.values())

        # Sort by update time (newest first)
        sessions.sort(key=lambda s: s.created_at, reverse=True)

        # Apply cursor pagination
        if cursor:
            cursor_time = float(cursor)
            sessions = [s for s in sessions if s.created_at.timestamp() < cursor_time]

        # Apply limit
        page = sessions[:limit]

        # Build response
        entries = [
            {
                "sessionId": s.id,
                "cwd": s.cwd,
                "updatedAt": s.created_at.isoformat(),
            }
            for s in page
        ]

        response: Dict[str, Any] = {"sessions": entries}

        # Add next cursor if there are more results
        if len(sessions) > limit:
            last = page[-1]
            response["nextCursor"] = str(last.created_at.timestamp())

        return response

    async def fork_session(
        self,
        session_id: str,
        cwd: str,
        mcp_servers: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Fork an existing session.

        Args:
            session_id: ID of session to fork
            cwd: Working directory for the new session
            mcp_servers: Optional list of MCP server configurations

        Returns:
            Fork session response with new session info
        """
        # In a real implementation, this would copy the session state
        original = self.sessions.get(session_id)
        if not original:
            raise ValueError(f"Session {session_id} not found")

        # Create new session from original
        new_session_id = f"fork_{session_id}_{int(asyncio.get_event_loop().time())}"
        new_session = SessionInfo(
            id=new_session_id,
            cwd=cwd,
            mode_id=original.mode_id,
            model=original.model,
        )

        self.sessions[new_session_id] = new_session

        return {
            "sessionId": new_session_id,
            "models": await self._load_models(cwd),
            "modes": await self._load_modes(cwd),
        }

    async def resume_session(
        self,
        session_id: str,
        cwd: str,
        mcp_servers: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Resume an existing session.

        Args:
            session_id: ID of session to resume
            cwd: Working directory for the session
            mcp_servers: Optional list of MCP server configurations

        Returns:
            Resume session response
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        return {
            "sessionId": session_id,
            "models": await self._load_models(cwd),
            "modes": await self._load_modes(cwd),
        }

    async def set_session_model(
        self,
        session_id: str,
        model_id: str,
    ) -> Dict[str, Any]:
        """
        Set the model for a session.

        Args:
            session_id: ID of session
            model_id: Model identifier (e.g., "openai/gpt-4")

        Returns:
            Model update response
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Parse model_id
        if "/" in model_id:
            provider_id, model_name = model_id.split("/", 1)
            session.model = ModelInfo(
                provider_id=provider_id,
                model_id=model_name,
            )
        else:
            raise ValueError(f"Invalid model_id format: {model_id}")

        return {"_meta": {}}

    async def set_session_mode(
        self,
        session_id: str,
        mode_id: str,
    ) -> Dict[str, Any]:
        """
        Set the mode (agent) for a session.

        Args:
            session_id: ID of session
            mode_id: Agent/mode identifier

        Returns:
            Mode update response

        Raises:
            ValueError: If mode_id not found
        """
        # Verify agent exists
        agent = await self.agent_manager.get(mode_id)
        if not agent:
            raise ValueError(f"Agent not found: {mode_id}")

        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.mode_id = mode_id

        return {}

    async def prompt(
        self,
        session_id: str,
        prompt_parts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Send a prompt to the session.

        Args:
            session_id: ID of session
            prompt_parts: List of prompt content parts

        Returns:
            Prompt response with stop_reason and usage
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # In a real implementation, this would:
        # 1. Parse prompt parts (text, images, resources, etc.)
        # 2. Call the LLM with the session context
        # 3. Stream updates via connection
        # 4. Return final result with usage info

        return {
            "stopReason": "end_turn",
            "usage": {
                "totalTokens": 0,
                "inputTokens": 0,
                "outputTokens": 0,
            },
            "_meta": {},
        }

    async def cancel(self, session_id: str):
        """
        Cancel an ongoing prompt in a session.

        Args:
            session_id: ID of session to cancel
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # In a real implementation, this would abort the ongoing generation

    async def _load_models(self, cwd: str) -> Dict[str, Any]:
        """Load available models for a directory."""
        # In a real implementation, this would query the provider system
        return {
            "currentModelId": "opencode/claude-sonnet-4",
            "availableModels": [
                {
                    "modelId": "opencode/claude-sonnet-4",
                    "name": "OpenCode/Claude Sonnet 4",
                },
            ],
        }

    async def _load_modes(self, cwd: str) -> Dict[str, Any]:
        """Load available agents/modes for a directory."""
        agents = await self.agent_manager.list()

        # Filter to primary, visible agents
        available_modes = [
            {
                "id": agent.name,
                "name": agent.name,
                "description": agent.description,
            }
            for agent in agents
            if agent.is_primary() and agent.is_visible()
        ]

        default_agent_name = await self.agent_manager.default_agent()

        return {
            "availableModes": available_modes,
            "currentModeId": default_agent_name,
        }

    def _tool_kind(self, tool_name: str) -> ToolKind:
        """Convert tool name to ACP ToolKind."""
        tool = tool_name.lower()
        if tool == "bash":
            return ToolKind.EXECUTE
        if tool == "webfetch":
            return ToolKind.FETCH
        if tool in ("edit", "patch", "write"):
            return ToolKind.EDIT
        if tool in ("grep", "glob", "codesearch"):
            return ToolKind.SEARCH
        if tool in ("read", "list"):
            return ToolKind.READ
        return ToolKind.OTHER

    def _tool_locations(
        self,
        tool_name: str,
        input_data: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """Extract file locations from tool input."""
        tool = tool_name.lower()
        if tool in ("read", "edit", "write"):
            if "filePath" in input_data:
                return [{"path": input_data["filePath"]}]
        if tool in ("glob", "grep"):
            if "path" in input_data:
                return [{"path": input_data["path"]}]
        if tool == "list" and "path" in input_data:
            return [{"path": input_data["path"]}]
        return []


class ACPSessionConnection:
    """
    Abstract base class for ACP session connections.

    In a real implementation, this would handle the actual protocol communication.
    """

    async def request_permission(
        self,
        session_id: str,
        tool_call: Dict[str, Any],
        options: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Request permission for a tool call."""
        raise NotImplementedError

    async def session_update(self, session_id: str, update: Dict[str, Any]):
        """Send a session update."""
        raise NotImplementedError

    async def write_text_file(self, session_id: str, path: str, content: str):
        """Write a text file preview."""
        raise NotImplementedError
