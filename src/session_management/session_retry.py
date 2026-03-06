"""
会话重试逻辑模块

处理API调用失败时的重试策略，包括指数退避和基于Retry-After头的延迟。
"""

import asyncio
import logging
from typing import Optional, Dict, Any, Union
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

from .message_types import (
    APIError,
    ContextOverflowError,
    is_context_overflow_error,
    is_api_error,
)

logger = logging.getLogger(__name__)


class SessionRetry:
    """
    会话重试处理器

    提供智能的重试策略，包括：
    - 指数退避（Exponential Backoff）
    - 基于Retry-After头的延迟
    - 可重试错误的识别
    - 上下文溢出错误不重试

    常量：
        RETRY_INITIAL_DELAY: 初始重试延迟（毫秒）
        RETRY_BACKOFF_FACTOR: 退避因子
        RETRY_MAX_DELAY_NO_HEADERS: 无头部时的最大延迟
        RETRY_MAX_DELAY: 最大延迟（毫秒，32位有符号整数最大值）

    示例：
        ```python
        retry = SessionRetry()

        # 检查错误是否可重试
        error_message = retry.is_retryable(error_dict)
        if error_message:
            # 计算延迟
            delay = retry.calculate_delay(attempt=2, error=error_dict)

            # 等待并重试
            await retry.sleep(delay, abort_signal)

            # 执行重试...
        ```
    """

    RETRY_INITIAL_DELAY = 2000  # 2秒
    RETRY_BACKOFF_FACTOR = 2
    RETRY_MAX_DELAY_NO_HEADERS = 30000  # 30秒
    RETRY_MAX_DELAY = 2147483647  # 32位有符号整数最大值（约24.8天）

    @staticmethod
    async def sleep(ms: int, signal: 'AbortSignal') -> None:
        """
        可中断的异步睡眠

        Args:
            ms: 睡眠时长（毫秒）
            signal: 中止信号对象

        Raises:
            AbortError: 如果信号被触发
        """
        delay_seconds = min(ms, SessionRetry.RETRY_MAX_DELAY) / 1000

        try:
            await asyncio.wait_for(
                signal.wait_until_abort(),
                timeout=delay_seconds
            )
            # 如果wait_until_abort完成了，说明被中止了
            raise AbortError("Operation aborted")
        except asyncio.TimeoutError:
            # 超时是正常的，表示睡眠完成
            pass

    @staticmethod
    def calculate_delay(
        attempt: int,
        error: Optional[Any] = None
    ) -> int:
        """
        计算重试延迟

        优先使用错误响应头中的Retry-After信息，
        否则使用指数退避算法。

        Args:
            attempt: 重试次数（从1开始）
            error: 错误对象（可选，可以是Exception或Dict）

        Returns:
            延迟时间（毫秒）
        """
        # Handle exception objects
        if error and isinstance(error, Exception):
            # For exceptions, use default exponential backoff
            pass
        elif error and is_api_error(error):
            headers = error.get("data", {}).get("response_headers")
            if headers:
                # 尝试从Retry-After-ms获取延迟
                retry_after_ms = headers.get("retry-after-ms")
                if retry_after_ms:
                    try:
                        parsed_ms = float(retry_after_ms)
                        if not parsed_ms != parsed_ms:  # NaN检查
                            return int(parsed_ms)
                    except (ValueError, TypeError):
                        pass

                # 尝试从Retry-After获取延迟
                retry_after = headers.get("retry-after")
                if retry_after:
                    # 1. 尝试解析为秒数
                    try:
                        parsed_seconds = float(retry_after)
                        if not parsed_seconds != parsed_seconds:
                            return int(parsed_seconds * 1000)
                    except (ValueError, TypeError):
                        pass

                    # 2. 尝试解析为HTTP日期格式
                    try:
                        retry_date = parsedate_to_datetime(retry_after)
                        if retry_date:
                            delay_ms = int((retry_date - datetime.now()).total_seconds() * 1000)
                            if delay_ms > 0:
                                return delay_ms
                    except Exception:
                        pass

                # 使用指数退避
                return int(
                    SessionRetry.RETRY_INITIAL_DELAY *
                    (SessionRetry.RETRY_BACKOFF_FACTOR ** (attempt - 1))
                )

        # 默认使用指数退避，有上限
        delay = int(
            SessionRetry.RETRY_INITIAL_DELAY *
            (SessionRetry.RETRY_BACKOFF_FACTOR ** (attempt - 1))
        )
        return min(delay, SessionRetry.RETRY_MAX_DELAY_NO_HEADERS)

    @staticmethod
    def is_retryable(error: Any) -> Optional[str]:
        """
        检查错误是否可重试

        上下文溢出错误不应重试。
        其他错误根据类型和内容判断是否可重试。

        Args:
            error: 错误对象（可以是Exception或Dict）

        Returns:
            如果可重试，返回用户友好的错误消息；否则返回None
        """
        # Handle exception objects
        if isinstance(error, Exception):
            # For ImportError and other exceptions, don't retry
            if isinstance(error, ImportError):
                return None
            # For other exceptions, return None to not retry
            return None

        # 上下文溢出错误不应重试
        if is_context_overflow_error(error):
            return None

        # API错误
        if is_api_error(error):
            data = error.get("data", {})
            if not data.get("is_retryable", False):
                return None

            # 检查是否为免费额度超出
            response_body = data.get("response_body", "")
            if response_body and "FreeUsageLimitError" in response_body:
                return "Free usage exceeded, add credits https://opencode.ai/zen"

            # 检查是否为过载错误
            message = data.get("message", "")
            if "Overloaded" in message:
                return "Provider is overloaded"

            return message

        # 尝试解析JSON格式的错误消息
        json_data = SessionRetry._parse_error_json(error)
        if json_data:
            return SessionRetry._check_json_error_retryable(json_data)

        return None

    @staticmethod
    def _parse_error_json(error: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """尝试解析JSON格式的错误"""
        try:
            data = error.get("data", {})
            message = data.get("message")

            if isinstance(message, str):
                try:
                    return json.loads(message)
                except (json.JSONDecodeError, TypeError):
                    pass

            if isinstance(data, dict):
                return data

            return None
        except Exception:
            return None

    @staticmethod
    def _check_json_error_retryable(json_data: Dict[str, Any]) -> Optional[str]:
        """检查JSON错误是否可重试"""
        if not isinstance(json_data, dict):
            return None

        # 检查错误类型
        error_type = json_data.get("type")
        error_info = json_data.get("error", {})

        # too_many_requests错误
        if error_type == "error" and isinstance(error_info, dict):
            if error_info.get("type") == "too_many_requests":
                return "Too Many Requests"

            error_code = error_info.get("code", "")
            if isinstance(error_code, str) and "rate_limit" in error_code:
                return "Rate Limited"

        # 检查代码
        code = json_data.get("code", "")
        if isinstance(code, str):
            if "exhausted" in code or "unavailable" in code:
                return "Provider is overloaded"

        # 返回JSON字符串作为最后的尝试
        try:
            return json.dumps(json_data)
        except Exception:
            return None


class AbortError(Exception):
    """操作被中止错误"""
    pass


class AbortSignal:
    """
    中止信号

    用于在异步操作中检查和传播中止请求。

    示例：
        ```python
        signal = AbortSignal()

        # 在另一个线程/任务中中止
        signal.abort()

        # 在异步操作中检查
        if signal.aborted:
            raise AbortError("Operation aborted")

        # 或使用wait_until_abort
        try:
            await signal.wait_until_abort()
        except AbortError:
            # 处理中止
            pass
        ```
    """

    def __init__(self):
        self._aborted = False
        self._event = asyncio.Event()

    @property
    def aborted(self) -> bool:
        """是否已中止"""
        return self._aborted

    def abort(self) -> None:
        """中止操作"""
        if not self._aborted:
            self._aborted = True
            self._event.set()

    def throw_if_aborted(self) -> None:
        """如果已中止则抛出异常"""
        if self._aborted:
            raise AbortError("Operation aborted")

    async def wait_until_abort(self) -> None:
        """等待中止信号"""
        await self._event.wait()
        raise AbortError("Operation aborted")

    def __bool__(self) -> bool:
        """布尔值转换"""
        return not self._aborted


import json


# 便捷函数
async def sleep_with_abort(ms: int, signal: AbortSignal) -> None:
    """可中断的睡眠（便捷函数）"""
    await SessionRetry.sleep(ms, signal)


def calculate_retry_delay(attempt: int, error: Optional[Dict[str, Any]] = None) -> int:
    """计算重试延迟（便捷函数）"""
    return SessionRetry.calculate_delay(attempt, error)


def is_error_retryable(error: Dict[str, Any]) -> Optional[str]:
    """检查错误是否可重试（便捷函数）"""
    return SessionRetry.is_retryable(error)
