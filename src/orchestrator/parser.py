"""
输入解析器

检测用户输入的前缀并分类处理。
"""

from enum import Enum
from typing import Tuple


class InputType(Enum):
    """输入类型"""
    COMMAND = "command"  # / 开头
    AGENT_SWITCH = "agent_switch"  # @ 开头
    NORMAL = "normal"  # 普通消息


class InputParser:
    """
    输入解析器

    职责：检测输入前缀并分类
    """

    @staticmethod
    def parse(user_input: str) -> Tuple[InputType, str]:
        """
        解析用户输入

        Args:
            user_input: 用户输入字符串

        Returns:
            (输入类型, 处理后的内容)
        """
        if not user_input:
            return InputType.NORMAL, user_input

        if user_input.startswith("/"):
            return InputType.COMMAND, user_input[1:].strip()
        elif user_input.startswith("@"):
            return InputType.AGENT_SWITCH, user_input[1:].strip()
        else:
            return InputType.NORMAL, user_input


__all__ = ["InputParser", "InputType"]
