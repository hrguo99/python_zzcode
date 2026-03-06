"""
Session Management 模块

会话管理模块，负责：
- 消息和部分类型定义
- 交互追踪和记录
- 重试逻辑
- 会话压缩
- 消息持久化接口

本模块专注于会话的存储和管理，不涉及 LLM 调用和主循环处理。
"""

from .message_types import (
    # 消息类型
    Message,
    UserMessage,
    AssistantMessage,
    MessageWithParts,
    # 部分类型
    Part,
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
    # 工具状态
    ToolState,
    ToolStatePending,
    ToolStateRunning,
    ToolStateCompleted,
    ToolStateError,
    ToolStatus,
    # 其他类型
    ModelInfo,
    PathInfo,
    TimeInfo,
    TokenUsage,
    SummaryInfo,
    AgentInfo,
    StreamInput,
    ModelMessage,
    # 错误类型
    MessageError,
    OutputLengthError,
    AbortedError,
    AuthError,
    APIError,
    ContextOverflowError,
    StructuredOutputError,
    # 枚举
    PartType,
    MessageRole,
    # 工具函数
    create_message_from_dict,
    create_part_from_dict,
    is_context_overflow_error,
    is_api_error,
)

from .interaction_tracker import (
    InteractionTracker,
    InteractionModel,
    InteractionAgent,
    InteractionInput,
    InteractionOutput,
    Interaction,
    ToolCallRecord,
    TokenUsageRecord,
    get_tracker,
)

from .session_retry import (
    SessionRetry,
    AbortSignal,
    AbortError,
    sleep_with_abort,
    calculate_retry_delay,
    is_error_retryable,
)

from .session_compaction import (
    SessionCompaction,
    CompactionResult,
    CompactionConfig,
    ModelLimits,
    check_overflow,
    prune_session,
)

__all__ = [
    # 消息类型
    "Message",
    "UserMessage",
    "AssistantMessage",
    "MessageWithParts",
    # 部分类型
    "Part",
    "TextPart",
    "ReasoningPart",
    "ToolPart",
    "FilePart",
    "AgentPart",
    "SnapshotPart",
    "PatchPart",
    "StepStartPart",
    "StepFinishPart",
    "SubtaskPart",
    "CompactionPart",
    "RetryPart",
    # 工具状态
    "ToolState",
    "ToolStatePending",
    "ToolStateRunning",
    "ToolStateCompleted",
    "ToolStateError",
    "ToolStatus",
    # 其他类型
    "ModelInfo",
    "PathInfo",
    "TimeInfo",
    "TokenUsage",
    "SummaryInfo",
    "AgentInfo",
    "StreamInput",
    "ModelMessage",
    # 错误类型
    "MessageError",
    "OutputLengthError",
    "AbortedError",
    "AuthError",
    "APIError",
    "ContextOverflowError",
    "StructuredOutputError",
    # 枚举
    "PartType",
    "MessageRole",
    # 工具函数
    "create_message_from_dict",
    "create_part_from_dict",
    "is_context_overflow_error",
    "is_api_error",
    # 交互追踪
    "InteractionTracker",
    "InteractionModel",
    "InteractionAgent",
    "InteractionInput",
    "InteractionOutput",
    "Interaction",
    "ToolCallRecord",
    "TokenUsageRecord",
    "get_tracker",
    # 重试逻辑
    "SessionRetry",
    "AbortSignal",
    "AbortError",
    "sleep_with_abort",
    "calculate_retry_delay",
    "is_error_retryable",
    # 会话压缩
    "SessionCompaction",
    "CompactionResult",
    "CompactionConfig",
    "ModelLimits",
    "check_overflow",
    "prune_session",
]
