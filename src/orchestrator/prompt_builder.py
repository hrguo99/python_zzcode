"""动态系统提示词构建器"""

import os
import subprocess
from pathlib import Path
from typing import List, Optional
from datetime import datetime


class PromptBuilder:
    """构建动态系统提示词"""

    def __init__(self, project_dir: str = "."):
        self.project_dir = Path(project_dir).resolve()

    async def build(self, model_id: str = "", agent_name: str = "") -> List[str]:
        """构建完整的系统提示词"""
        parts = []

        # 1. 基础提示词（模型特定）
        parts.append(self._load_base_prompt(model_id))

        # 2. 环境信息
        parts.append(self._build_environment_info(model_id))

        # 3. 指令系统
        parts.extend(self._load_instruction_files())

        return [p for p in parts if p]

    def _load_base_prompt(self, model_id: str) -> str:
        """加载模型特定的基础提示词"""
        prompt_dir = Path(__file__).parent.parent.parent / "prompt"

        if "claude" in model_id.lower():
            prompt_file = prompt_dir / "anthropic.txt"
        else:
            prompt_file = prompt_dir / "base.txt"

        if prompt_file.exists():
            return prompt_file.read_text(encoding="utf-8")
        return ""

    def _build_environment_info(self, model_id: str) -> str:
        """构建环境信息"""
        info = ["<env>"]

        # 工作目录
        info.append(f"Working directory: {self.project_dir}")

        # Git 状态
        git_info = self._get_git_info()
        if git_info:
            info.append(f"Is directory a git repo: Yes")
            info.append(f"Git branch: {git_info.get('branch', 'unknown')}")
        else:
            info.append(f"Is directory a git repo: No")

        # 操作系统
        info.append(f"Platform: {os.name}")

        # 日期
        info.append(f"Today's date: {datetime.now().strftime('%Y-%m-%d')}")

        info.append("</env>")
        return "\n".join(info)

    def _get_git_info(self) -> Optional[dict]:
        """获取 Git 仓库信息"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                return {"branch": result.stdout.strip()}
        except Exception:
            pass
        return None

    def _load_instruction_files(self) -> List[str]:
        """加载指令文件（AGENTS.md、CLAUDE.md 等）"""
        instructions = []

        # 项目级 AGENTS.md
        agents_file = self.project_dir / "AGENTS.md"
        if agents_file.exists():
            instructions.append(agents_file.read_text(encoding="utf-8"))

        # 全局 CLAUDE.md
        global_claude = Path.home() / ".config" / "opencode" / "CLAUDE.md"
        if global_claude.exists():
            instructions.append(global_claude.read_text(encoding="utf-8"))

        return instructions
