"""
SkillTool implementation.

This module provides the SkillTool for loading and executing skills.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tool.base import ToolDefinition, ToolContext, ToolResult
from tool.models import ToolMetadata
from skill.skill import SkillManager
from skill.models import SkillNotFoundError


class SkillTool(ToolDefinition):
    """
    Tool for loading and using skills.

    This tool allows agents to load specialized skills that provide
    domain-specific instructions and workflows.

    Corresponds to the SkillTool in the TypeScript implementation.
    """

    def __init__(self, skill_manager: Optional[SkillManager] = None):
        """
        Initialize the skill tool.

        Args:
            skill_manager: Optional SkillManager instance
        """
        super().__init__("skill")
        self.skill_manager = skill_manager or SkillManager()
        self._description = None
        self._parameters_schema = None

    async def initialize(self) -> None:
        """Initialize the skill tool."""
        # Get all skills
        skills = await self.skill_manager.list()

        if not skills:
            self._description = (
                "Load a specialized skill that provides domain-specific instructions and workflows. "
                "No skills are currently available."
            )
        else:
            skill_list = "\n".join([
                f"  - {skill.name}: {skill.description}"
                for skill in skills
            ])
            self._description = (
                "Load a specialized skill that provides domain-specific instructions and workflows.\n\n"
                "When you recognize that a task matches one of the available skills, "
                "use this tool to load the full skill instructions.\n\n"
                "The skill will inject detailed instructions, workflows, and access to bundled "
                "resources (scripts, references, templates) into the conversation context.\n\n"
                "Available skills:\n"
                f"{skill_list}"
            )

        # Get skill names for examples
        skill_names = [skill.name for skill in skills[:3]]
        examples = ", ".join([f"'{name}'" for name in skill_names])
        hint = f" (e.g., {examples}, ...)" if skill_names else ""

        self._parameters_schema = {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": f"The name of the skill{hint}",
                },
            },
            "required": ["name"],
        }

    async def execute(self, args: Dict[str, Any], ctx: ToolContext) -> ToolResult:
        """
        Execute the skill tool.

        Args:
            args: Tool arguments (should contain 'name')
            ctx: Execution context

        Returns:
            ToolResult with skill content

        Raises:
            SkillNotFoundError: If skill is not found
        """
        skill_name = args["name"]

        # Get the skill
        skill = await self.skill_manager.get(skill_name)

        if not skill:
            # Get list of available skills for error message
            all_skills = await self.skill_manager.list()
            available = ", ".join([s.name for s in all_skills])
            raise SkillNotFoundError(
                skill_name,
                [s.name for s in all_skills]
            )

        # Request permission
        await ctx.ask_permission(
            permission="skill",
            patterns=[skill_name],
            always=[skill_name],
            metadata={
                "skill": skill_name,
                "location": skill.location,
            },
        )

        # Check for abort
        if ctx.is_aborted():
            raise RuntimeError("Skill loading aborted")

        # Get skill directory
        skill_dir = skill.metadata.directory or os.path.dirname(skill.location)
        base_url = Path(skill_dir).as_uri()

        # List related files (limit to 10)
        files = await self._list_skill_files(skill_dir, limit=10)

        # Format output
        output_lines = [
            f"<skill_content name=\"{skill.name}\">",
            f"# Skill: {skill.name}",
            "",
            skill.content.strip(),
            "",
            f"Base directory for this skill: {base_url}",
            "Relative paths in this skill (e.g., scripts/, reference/) are relative to this base directory.",
            "Note: file list is sampled.",
            "",
            "<skill_files>",
            files,
            "</skill_files>",
            "</skill_content>",
        ]

        return ToolResult(
            title=f"Loaded skill: {skill.name}",
            output="\n".join(output_lines),
            metadata=ToolMetadata(
                extra={
                    "name": skill.name,
                    "dir": skill_dir,
                },
            ),
        )

    async def _list_skill_files(self, skill_dir: str, limit: int = 10) -> str:
        """
        List files in the skill directory.

        Args:
            skill_dir: Path to skill directory
            limit: Maximum number of files to list

        Returns:
            Formatted file list
        """
        files = []

        try:
            # Walk through directory
            for root, dirnames, filenames in os.walk(skill_dir):
                for filename in filenames:
                    # Skip SKILL.md
                    if filename == "SKILL.md":
                        continue

                    filepath = os.path.join(root, filename)
                    rel_path = os.path.relpath(filepath, skill_dir)

                    # Convert to file URL format
                    files.append(f"<file>{filepath}</file>")

                    if len(files) >= limit:
                        break

                if len(files) >= limit:
                    break

        except Exception as e:
            # If listing fails, return empty
            logger = __import__("logging").getLogger(__name__)
            logger.warning(f"Failed to list files in {skill_dir}: {e}")
            return ""

        return "\n".join(files)

    async def get_accessible_skills(
        self,
        permission_evaluator: Optional[Any] = None,
    ) -> List[Dict[str, str]]:
        """
        Get list of accessible skills.

        Args:
            permission_evaluator: Optional function to evaluate permissions

        Returns:
            List of accessible skill info dictionaries
        """
        all_skills = await self.skill_manager.list()

        if permission_evaluator is None:
            return [
                {
                    "name": skill.name,
                    "description": skill.description,
                    "location": skill.location,
                }
                for skill in all_skills
            ]

        # Filter by permissions
        accessible = await self.skill_manager.filter_by_permissions(
            all_skills,
            permission_evaluator,
        )

        return [
            {
                "name": skill.name,
                "description": skill.description,
                "location": skill.location,
            }
            for skill in accessible
        ]


def create_skill_tool(
    skill_manager: Optional[SkillManager] = None,
) -> SkillTool:
    """
    Create a SkillTool instance.

    Convenience function for creating a skill tool.

    Args:
        skill_manager: Optional SkillManager instance

    Returns:
        Initialized SkillTool
    """
    tool = SkillTool(skill_manager)
    # Note: The caller should call await tool.initialize()
    return tool
