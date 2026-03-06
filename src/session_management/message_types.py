"""
消息类型定义模块

定义了OpenCode会话系统中使用的所有消息和部分的类型。
"""

from typing import Literal, Optional, Union, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import json


class PartType(str, Enum):
    """消息部分类型"""
    TEXT = "text"
    REASONING = "reasoning"
    TOOL = "tool"
    FILE = "file"
    AGENT = "agent"
    SNAPSHOT = "snapshot"
    PATCH = "patch"
    STEP_START = "step-start"
    STEP_FINISH = "step-finish"
    SUBTASK = "subtask"
    COMPACTION = "compaction"
    RETRY = "retry"


class MessageRole(str, Enum):
    """消息角色"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ToolStatus(str, Enum):
    """工具执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class ToolState:
    """工具状态基类"""
    status: ToolStatus
    input: Dict[str, Any] = field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ToolStatePending(ToolState):
    """工具待执行状态"""
    raw: str = ""
    status: Literal[ToolStatus.PENDING] = ToolStatus.PENDING
    input: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolStateRunning(ToolState):
    """工具运行状态"""
    time_start: int = 0
    title: Optional[str] = None
    status: Literal[ToolStatus.RUNNING] = ToolStatus.RUNNING
    input: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolStateCompleted(ToolState):
    """工具完成状态"""
    output: str = ""
    title: str = ""
    time_start: int = 0
    time_end: int = 0
    time_compacted: Optional[int] = None
    attachments: Optional[List['FilePart']] = None
    status: Literal[ToolStatus.COMPLETED] = ToolStatus.COMPLETED
    input: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolStateError(ToolState):
    """工具错误状态"""
    error: str = ""
    time_start: int = 0
    time_end: int = 0
    status: Literal[ToolStatus.ERROR] = ToolStatus.ERROR
    input: Dict[str, Any] = field(default_factory=dict)


# 工具状态联合类型
ToolStateUnion = Union[ToolStatePending, ToolStateRunning, ToolStateCompleted, ToolStateError]


@dataclass
class FileSourceText:
    """文件来源文本基础"""
    value: str
    start: int
    end: int


@dataclass
class FileSource:
    """文件来源"""
    type: Literal["file"] = "file"
    path: str = ""


@dataclass
class SymbolSource:
    """符号来源"""
    type: Literal["symbol"] = "symbol"
    path: str = ""
    range: Dict[str, Any] = field(default_factory=dict)
    name: str = ""
    kind: int = 0


@dataclass
class ResourceSource:
    """资源来源"""
    type: Literal["resource"] = "resource"
    client_name: str = ""
    uri: str = ""


FileSourceUnion = Union[FileSourceText, FileSource, SymbolSource, ResourceSource]


@dataclass
class TimeInfo:
    """时间信息"""
    created: int = 0
    completed: Optional[int] = None
    start: Optional[int] = None
    end: Optional[int] = None
    compacted: Optional[int] = None


@dataclass
class TokenUsage:
    """Token使用统计"""
    input: int
    output: int
    reasoning: int = 0
    total: Optional[int] = None
    cache_read: int = 0
    cache_write: int = 0


@dataclass
class BasePart:
    """消息部分基类"""
    id: str = ""
    session_id: str = ""
    message_id: str = ""


@dataclass
class TextPart(BasePart):
    """文本部分"""
    type: Literal[PartType.TEXT] = PartType.TEXT
    text: str = ""
    synthetic: bool = False
    ignored: bool = False
    time: Optional[TimeInfo] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ReasoningPart(BasePart):
    """推理部分"""
    type: Literal[PartType.REASONING] = PartType.REASONING
    text: str = ""
    time: Optional[TimeInfo] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ToolPart(BasePart):
    """工具部分"""
    type: Literal[PartType.TOOL] = PartType.TOOL
    call_id: str = ""
    tool: str = ""
    state: ToolStateUnion = field(default_factory=ToolStatePending)
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class FilePart(BasePart):
    """文件部分"""
    type: Literal[PartType.FILE] = PartType.FILE
    mime: str = ""
    url: str = ""
    filename: Optional[str] = None
    source: Optional[FileSourceUnion] = None


@dataclass
class AgentPart(BasePart):
    """代理部分"""
    type: Literal[PartType.AGENT] = PartType.AGENT
    name: str = ""
    source: Optional[FileSourceText] = None


@dataclass
class SnapshotPart(BasePart):
    """快照部分"""
    type: Literal[PartType.SNAPSHOT] = PartType.SNAPSHOT
    snapshot: str = ""


@dataclass
class PatchPart(BasePart):
    """补丁部分"""
    type: Literal[PartType.PATCH] = PartType.PATCH
    hash: str = ""
    files: List[str] = field(default_factory=list)


@dataclass
class StepStartPart(BasePart):
    """步骤开始部分"""
    type: Literal[PartType.STEP_START] = PartType.STEP_START
    snapshot: Optional[str] = None


@dataclass
class StepFinishPart(BasePart):
    """步骤完成部分"""
    type: Literal[PartType.STEP_FINISH] = PartType.STEP_FINISH
    reason: str = ""
    snapshot: Optional[str] = None
    cost: float = 0.0
    tokens: TokenUsage = field(default_factory=lambda: TokenUsage(input=0, output=0))


@dataclass
class SubtaskPart(BasePart):
    """子任务部分"""
    type: Literal[PartType.SUBTASK] = PartType.SUBTASK
    prompt: str = ""
    description: str = ""
    agent: str = ""
    model: Optional[Dict[str, str]] = None
    command: Optional[str] = None


@dataclass
class CompactionPart(BasePart):
    """压缩部分"""
    type: Literal[PartType.COMPACTION] = PartType.COMPACTION
    auto: bool = True


@dataclass
class RetryPart(BasePart):
    """重试部分"""
    type: Literal[PartType.RETRY] = PartType.RETRY
    attempt: int = 0
    error: Optional[Dict[str, Any]] = None
    time: Optional[TimeInfo] = None


# 消息部分联合类型
Part = Union[
    TextPart,
    ReasoningPart,
    ToolPart,
    FilePart,
    AgentPart,
    SnapshotPart,
    PatchPart,
    StepStartPart,
    StepFinishPart,
    SubtaskPart,
    CompactionPart,
    RetryPart,
]


@dataclass
class ModelInfo:
    """模型信息"""
    provider_id: str = ""
    model_id: str = ""


@dataclass
class PathInfo:
    """路径信息"""
    cwd: str = ""
    root: str = ""


@dataclass
class SummaryInfo:
    """摘要信息"""
    title: Optional[str] = None
    body: Optional[str] = None
    diffs: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class BaseMessage:
    """消息基类"""
    id: str = ""
    session_id: str = ""
    role: MessageRole = MessageRole.USER
    time: TimeInfo = field(default_factory=TimeInfo)


@dataclass
class UserMessage(BaseMessage):
    """用户消息"""
    role: Literal[MessageRole.USER] = MessageRole.USER
    agent: str = ""
    model: ModelInfo = field(default_factory=ModelInfo)
    system: Optional[str] = None
    tools: Optional[Dict[str, bool]] = None
    variant: Optional[str] = None
    format: Optional[Dict[str, Any]] = None
    summary: Optional[SummaryInfo] = None


@dataclass
class AssistantMessage(BaseMessage):
    """助手消息"""
    role: Literal[MessageRole.ASSISTANT] = MessageRole.ASSISTANT
    parent_id: str = ""
    model_id: str = ""
    provider_id: str = ""
    mode: str = ""
    agent: str = ""
    path: PathInfo = field(default_factory=PathInfo)
    summary: bool = False
    cost: float = 0.0
    tokens: TokenUsage = field(default_factory=lambda: TokenUsage(input=0, output=0))
    variant: Optional[str] = None
    finish: Optional[str] = None
    structured: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


# 消息联合类型
Message = Union[UserMessage, AssistantMessage]


@dataclass
class MessageWithParts:
    """包含部分的消息"""
    info: Message = field(default_factory=UserMessage)
    parts: List[Part] = field(default_factory=list)


@dataclass
class StreamInput:
    """流式输入"""
    user: UserMessage = field(default_factory=UserMessage)
    session_id: str = ""
    model: ModelInfo = field(default_factory=ModelInfo)
    agent: 'AgentInfo' = field(default_factory=lambda: AgentInfo(name="", mode=""))
    system: List[str] = field(default_factory=list)
    abort: 'AbortSignal' = field(default_factory=lambda: None)
    messages: List['ModelMessage'] = field(default_factory=list)
    small: bool = False
    tools: Dict[str, Any] = field(default_factory=dict)
    retries: int = 0
    tool_choice: Literal["auto", "required", "none"] = "auto"


@dataclass
class AgentInfo:
    """代理信息"""
    name: str = ""
    mode: str = ""
    prompt: Optional[str] = None
    options: Dict[str, Any] = field(default_factory=dict)
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    permission: List[str] = field(default_factory=list)


@dataclass
class ModelMessage:
    """模型消息"""
    role: Literal["user", "assistant", "system"] = "user"
    content: Union[str, List[Dict[str, Any]]] = ""


@dataclass
class FinishReason:
    """完成原因"""
    reason: str
    usage: Optional[Dict[str, Any]] = None
    provider_metadata: Optional[Dict[str, Any]] = None


# 错误类型
class MessageError(Exception):
    """消息错误基类"""
    def __init__(self, message: str, data: Optional[Dict[str, Any]] = None):
        self.message = message
        self.data = data or {}
        self.name = self.__class__.__name__
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "message": self.message,
            "data": self.data
        }


class OutputLengthError(MessageError):
    """输出长度错误"""
    pass


class AbortedError(MessageError):
    """中止错误"""
    pass


class AuthError(MessageError):
    """认证错误"""
    def __init__(self, message: str, provider_id: str):
        super().__init__(message, {"provider_id": provider_id})


class APIError(MessageError):
    """API错误"""
    def __init__(
        self,
        message: str,
        is_retryable: bool = False,
        status_code: Optional[int] = None,
        response_headers: Optional[Dict[str, str]] = None,
        response_body: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        data = {
            "is_retryable": is_retryable,
            "status_code": status_code,
            "response_headers": response_headers,
            "response_body": response_body,
            "metadata": metadata,
        }
        super().__init__(message, {k: v for k, v in data.items() if v is not None})


class ContextOverflowError(MessageError):
    """上下文溢出错误"""
    def __init__(self, message: str, response_body: Optional[str] = None):
        super().__init__(message, {"response_body": response_body})


class StructuredOutputError(MessageError):
    """结构化输出错误"""
    def __init__(self, message: str, retries: int = 0):
        super().__init__(message, {"retries": retries})


def create_message_from_dict(data: Dict[str, Any]) -> Message:
    """从字典创建消息对象"""
    role = data.get("role")
    if role == MessageRole.USER:
        return UserMessage(
            id=data["id"],
            session_id=data["session_id"],
            role=MessageRole.USER,
            time=TimeInfo(**data["time"]),
            agent=data.get("agent", ""),
            model=ModelInfo(**data.get("model", {})),
            system=data.get("system"),
            tools=data.get("tools"),
            variant=data.get("variant"),
        )
    elif role == MessageRole.ASSISTANT:
        return AssistantMessage(
            id=data["id"],
            session_id=data["session_id"],
            role=MessageRole.ASSISTANT,
            time=TimeInfo(**data["time"]),
            parent_id=data.get("parent_id", ""),
            model_id=data.get("model_id", ""),
            provider_id=data.get("provider_id", ""),
            mode=data.get("mode", ""),
            agent=data.get("agent", ""),
            path=PathInfo(**data.get("path", {})),
            summary=data.get("summary", False),
            cost=data.get("cost", 0.0),
            tokens=TokenUsage(**data.get("tokens", {})),
            variant=data.get("variant"),
            finish=data.get("finish"),
            error=data.get("error"),
        )
    raise ValueError(f"Unknown message role: {role}")


def create_part_from_dict(data: Dict[str, Any]) -> Part:
    """从字典创建部分对象"""
    part_type = data.get("type")
    base_data = {
        "id": data["id"],
        "session_id": data["session_id"],
        "message_id": data["message_id"],
    }

    if part_type == PartType.TEXT:
        return TextPart(
            **base_data,
            text=data.get("text", ""),
            synthetic=data.get("synthetic", False),
            ignored=data.get("ignored", False),
            time=TimeInfo(**data["time"]) if data.get("time") else None,
            metadata=data.get("metadata"),
        )
    elif part_type == PartType.TOOL:
        state_data = data["state"]
        status = state_data["status"]

        if status == ToolStatus.PENDING:
            state = ToolStatePending(
                status=ToolStatus.PENDING,
                input=state_data["input"],
                raw=state_data.get("raw", ""),
            )
        elif status == ToolStatus.RUNNING:
            state = ToolStateRunning(
                status=ToolStatus.RUNNING,
                input=state_data["input"],
                time_start=state_data["time"]["start"],
                title=state_data.get("title"),
                metadata=state_data.get("metadata"),
            )
        elif status == ToolStatus.COMPLETED:
            state = ToolStateCompleted(
                status=ToolStatus.COMPLETED,
                input=state_data["input"],
                output=state_data["output"],
                title=state_data["title"],
                time_start=state_data["time"]["start"],
                time_end=state_data["time"]["end"],
                time_compacted=state_data["time"].get("compacted"),
                metadata=state_data.get("metadata"),
            )
        elif status == ToolStatus.ERROR:
            state = ToolStateError(
                status=ToolStatus.ERROR,
                input=state_data["input"],
                error=state_data["error"],
                time_start=state_data["time"]["start"],
                time_end=state_data["time"]["end"],
                metadata=state_data.get("metadata"),
            )
        else:
            raise ValueError(f"Unknown tool status: {status}")

        return ToolPart(
            **base_data,
            call_id=data["call_id"],
            tool=data["tool"],
            state=state,
            metadata=data.get("metadata"),
        )
    elif part_type == PartType.FILE:
        return FilePart(
            **base_data,
            mime=data["mime"],
            url=data["url"],
            filename=data.get("filename"),
            source=data.get("source"),
        )
    elif part_type == PartType.REASONING:
        return ReasoningPart(
            **base_data,
            text=data.get("text", ""),
            time=TimeInfo(**data["time"]) if data.get("time") else None,
            metadata=data.get("metadata"),
        )
    elif part_type == PartType.STEP_START:
        return StepStartPart(
            **base_data,
            snapshot=data.get("snapshot"),
        )
    elif part_type == PartType.STEP_FINISH:
        return StepFinishPart(
            **base_data,
            reason=data.get("reason", ""),
            snapshot=data.get("snapshot"),
            cost=data.get("cost", 0.0),
            tokens=TokenUsage(**data.get("tokens", {})),
        )
    elif part_type == PartType.COMPACTION:
        return CompactionPart(
            **base_data,
            auto=data.get("auto", True),
        )
    elif part_type == PartType.PATCH:
        return PatchPart(
            **base_data,
            hash=data.get("hash", ""),
            files=data.get("files", []),
        )
    elif part_type == PartType.SUBTASK:
        return SubtaskPart(
            **base_data,
            prompt=data.get("prompt", ""),
            description=data.get("description", ""),
            agent=data.get("agent", ""),
            model=data.get("model"),
            command=data.get("command"),
        )
    elif part_type == PartType.AGENT:
        return AgentPart(
            **base_data,
            name=data.get("name", ""),
            source=data.get("source"),
        )
    elif part_type == PartType.SNAPSHOT:
        return SnapshotPart(
            **base_data,
            snapshot=data.get("snapshot", ""),
        )
    elif part_type == PartType.RETRY:
        return RetryPart(
            **base_data,
            attempt=data.get("attempt", 0),
            error=data.get("error"),
            time=TimeInfo(**data["time"]) if data.get("time") else None,
        )

    raise ValueError(f"Unknown part type: {part_type}")


def is_context_overflow_error(error: Dict[str, Any]) -> bool:
    """检查是否为上下文溢出错误"""
    return error.get("name") == ContextOverflowError.__name__


def is_api_error(error: Dict[str, Any]) -> bool:
    """检查是否为API错误"""
    return error.get("name") == APIError.__name__
