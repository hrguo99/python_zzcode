"""
命令处理器

处理以 / 开头的命令输入。
"""

from typing import Dict, Callable, Any, Awaitable


class CommandHandler:
    """
    命令处理器

    职责：解析命令、查询命令表、执行对应逻辑
    """

    def __init__(self):
        self._commands: Dict[str, Callable[..., Awaitable[str]]] = {}

    def register(self, name: str, handler: Callable[..., Awaitable[str]]) -> None:
        """注册命令"""
        self._commands[name] = handler

    async def execute(self, command_input: str) -> str:
        """
        执行命令

        Args:
            command_input: 命令内容（不含 / 前缀）

        Returns:
            执行结果
        """
        parts = command_input.split(maxsplit=1)
        command_name = parts[0] if parts else ""
        args = parts[1] if len(parts) > 1 else ""

        handler = self._commands.get(command_name)
        if not handler:
            return f"未知命令: /{command_name}"

        return await handler(args)


__all__ = ["CommandHandler"]
