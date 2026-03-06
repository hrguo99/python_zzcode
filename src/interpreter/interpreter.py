"""
OpenCode 解释器

整合所有模块的高级解释器接口。
"""

import asyncio
import logging
from typing import Optional

from ai_sdk.llm import LLM
from session_management import AgentInfo, ModelInfo
from session_management import InteractionTracker

from .config import InterpreterConfig
from .session import InterpreterSession

logger = logging.getLogger(__name__)


class OpenCodeInterpreter:
    """
    OpenCode 解释器

    职责：
    - 整合 AI SDK、Session Management 和 Processor
    - 提供易用的高级接口
    - 管理解释器生命周期
    """

    def __init__(
        self,
        config: InterpreterConfig,
        tracker: Optional[InteractionTracker] = None,
    ):
        self.config = config
        self.tracker = tracker
        self._llm: Optional["LLM"] = None

    async def __aenter__(self):
        from ai_sdk.llm import LLM

        self._llm = LLM(
            provider=self.config.provider,
            model=self.config.model,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # LLM 不需要清理
        pass

    def session(
        self,
        session_id: str,
        agent: Optional[AgentInfo] = None,
        model: Optional[ModelInfo] = None,
    ) -> "InterpreterSession":
        """
        创建解释器会话
        """
        if agent is None:
            agent = AgentInfo(
                name="default",
                mode="chat",
                prompt=None,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
            )

        if model is None:
            model = ModelInfo(
                provider_id=self.config.provider,
                model_id=self.config.model,
            )

        return InterpreterSession(
            interpreter=self,
            session_id=session_id,
            agent=agent,
            model=model,
        )


__all__ = ["OpenCodeInterpreter"]
