"""
Core Skill management class.

This module provides the main Skill class for managing skill lifecycle and operations.
"""

import os
import re
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass
import glob as glob_module
import logging

from .models import (
    SkillInfo,
    SkillConfig,
    SkillNotFoundError,
    SkillInvalidError,
    SkillMetadata,
)

logger = logging.getLogger(__name__)


# Skill search patterns
EXTERNAL_DIRS = [".claude", ".agents"]
EXTERNAL_SKILL_PATTERN = "skills/**/SKILL.md"
OPENCODE_SKILL_PATTERN = "{skill,skills}/**/SKILL.md"
SKILL_PATTERN = "**/SKILL.md"


@dataclass
class SkillManagerConfig:
    """Configuration for SkillManager."""
    project_dir: str = "."
    worktree_dir: str = "."
    cache_dir: Optional[str] = None
    config: SkillConfig = None

    def __post_init__(self):
        if self.config is None:
            self.config = SkillConfig()
        if self.cache_dir is None:
            self.cache_dir = os.path.expanduser("~/.cache/opencode/skills")


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """
    Parse YAML frontmatter from markdown content.

    Args:
        content: Markdown content with frontmatter

    Returns:
        Tuple of (frontmatter_dict, content_without_frontmatter)

    Raises:
        SkillInvalidError: If frontmatter is invalid
    """
    if not content.startswith("---"):
        return {}, content

    # Find end of frontmatter
    end_match = content.find("\n---", 4)
    if end_match == -1:
        raise SkillInvalidError("file", "Unclosed frontmatter delimiter")

    frontmatter_text = content[3:end_match]
    content_body = content[end_match + 4:]

    # Parse simple YAML-like frontmatter
    frontmatter = {}
    for line in frontmatter_text.strip().split("\n"):
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        # Remove quotes if present
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        frontmatter[key] = value

    return frontmatter, content_body


class SkillManager:
    """
    Main Skill management class.

    This class handles skill discovery, loading, and retrieval.
    Corresponds to the Skill namespace in the original TypeScript implementation.
    """

    def __init__(self, config: Optional[SkillManagerConfig] = None):
        """
        Initialize the Skill manager.

        Args:
            config: Optional SkillManagerConfig instance
        """
        self.config = config or SkillManagerConfig()
        self._state: Optional[Dict[str, SkillInfo]] = None
        self._skill_dirs: Set[str] = set()
        self._loaded = False

    async def _load_state(self) -> Dict[str, SkillInfo]:
        """
        Load and initialize the skill state.

        This builds the complete skill registry by:
        1. Scanning external skill directories
        2. Scanning .opencode/skill/ directories
        3. Scanning additional paths from config
        4. Removing duplicates

        Returns:
            Dictionary mapping skill names to SkillInfo objects
        """
        if self._loaded and self._state is not None:
            return self._state

        skills: Dict[str, SkillInfo] = {}
        dirs: Set[str] = set()

        async def add_skill(match: str):
            """Add a skill from a file path."""
            try:
                with open(match, "r", encoding="utf-8") as f:
                    content = f.read()

                # Parse frontmatter
                frontmatter, body = parse_frontmatter(content)

                # Extract required fields
                name = frontmatter.get("name")
                description = frontmatter.get("description", "")
                if not name:
                    logger.warning(f"Skill missing name in {match}")
                    return

                # Warn on duplicate skill names
                if name in skills:
                    logger.warning(
                        f"Duplicate skill name: {name}, "
                        f"existing: {skills[name].location}, "
                        f"duplicate: {match}"
                    )

                # Add to skill dirs
                skill_dir = str(Path(match).parent)
                dirs.add(skill_dir)

                # Create skill info
                skills[name] = SkillInfo(
                    name=name,
                    description=description,
                    location=match,
                    content=body,
                    metadata=SkillMetadata(
                        name=name,
                        description=description,
                        location=match,
                        directory=skill_dir,
                        mode=frontmatter.get("mode"),
                        model=frontmatter.get("model"),
                    ),
                )

            except Exception as e:
                logger.error(f"Failed to load skill {match}: {e}")

        async def scan_directory(root: str, pattern: str):
            """Scan a directory for skill files."""
            try:
                # Use glob to find matching files
                full_pattern = os.path.join(root, pattern)
                matches = glob_module.glob(full_pattern, recursive=True)

                for match in matches:
                    if os.path.isfile(match):
                        await add_skill(match)

            except Exception as e:
                logger.error(f"Failed to scan {root}: {e}")

        # Scan external skill directories (global level)
        if not self.config.config.disable_external:
            home_dir = os.path.expanduser("~")
            for external_dir in EXTERNAL_DIRS:
                root = os.path.join(home_dir, external_dir)
                if os.path.isdir(root):
                    await scan_directory(root, EXTERNAL_SKILL_PATTERN)

            # Scan project-level external directories
            project_dir = self.config.project_dir
            current_dir = os.path.abspath(project_dir)

            for external_dir in EXTERNAL_DIRS:
                root = os.path.join(current_dir, external_dir)
                if os.path.isdir(root):
                    await scan_directory(root, EXTERNAL_SKILL_PATTERN)

        # Scan .opencode/skill/ directories
        opencode_skill_dir = os.path.join(current_dir, ".opencode")
        if os.path.isdir(opencode_skill_dir):
            # Scan for skill/skills directories
            for skill_dir_name in ["skill", "skills"]:
                skill_root = os.path.join(opencode_skill_dir, skill_dir_name)
                if os.path.isdir(skill_root):
                    await scan_directory(skill_root, "**/SKILL.md")

        # Scan additional skill paths from config
        for skill_path in self.config.config.paths:
            # Expand ~
            expanded = skill_path
            if skill_path.startswith("~/"):
                expanded = os.path.join(home_dir, skill_path[2:])

            # Resolve relative paths
            if not os.path.isabs(expanded):
                expanded = os.path.join(current_dir, expanded)

            if os.path.isdir(expanded):
                await scan_directory(expanded, SKILL_PATTERN)
            else:
                logger.warning(f"Skill path not found: {expanded}")

        self._state = skills
        self._skill_dirs = dirs
        self._loaded = True

        return skills

    async def get(self, skill_name: str) -> Optional[SkillInfo]:
        """
        Get a skill by name.

        Args:
            skill_name: Name of the skill to retrieve

        Returns:
            SkillInfo if found, None otherwise
        """
        state = await self._load_state()
        return state.get(skill_name)

    async def all(self) -> Dict[str, SkillInfo]:
        """
        Get all skills.

        Returns:
            Dictionary mapping skill names to SkillInfo objects
        """
        return await self._load_state()

    async def list(self) -> List[SkillInfo]:
        """
        List all skills.

        Returns:
            List of SkillInfo objects
        """
        state = await self._load_state()
        return list(state.values())

    async def dirs(self) -> List[str]:
        """
        Get all skill directories.

        Returns:
            List of skill directory paths
        """
        await self._load_state()
        return list(self._skill_dirs)

    def reset_state(self):
        """
        Reset the cached skill state.

        This forces a reload of the skill configuration on next access.
        Useful for testing or when skills are added/removed.
        """
        self._state = None
        self._skill_dirs = set()
        self._loaded = False

    async def filter_by_permissions(
        self,
        skills: List[SkillInfo],
        permission_evaluator,
    ) -> List[SkillInfo]:
        """
        Filter skills by permission evaluation.

        Args:
            skills: List of skills to filter
            permission_evaluator: Function to evaluate permissions

        Returns:
            Filtered list of skills
        """
        if not permission_evaluator:
            return skills

        result = []
        for skill in skills:
            try:
                # Check if skill access is allowed
                action = permission_evaluator("skill", skill.name)
                if action != "deny":
                    result.append(skill)
            except Exception:
                # If permission check fails, include the skill
                result.append(skill)

        return result

    async def search(
        self,
        query: str,
        fields: Optional[List[str]] = None,
    ) -> List[SkillInfo]:
        """
        Search for skills by query string.

        Args:
            query: Search query
            fields: Fields to search in (default: name, description)

        Returns:
            List of matching skills
        """
        if fields is None:
            fields = ["name", "description"]

        skills = await self.list()
        query_lower = query.lower()

        results = []
        for skill in skills:
            for field in fields:
                value = getattr(skill, field, "")
                if isinstance(value, str) and query_lower in value.lower():
                    results.append(skill)
                    break

        return results


# Convenience functions for backward compatibility
async def get_skill(
    skill_name: str,
    config: Optional[SkillManagerConfig] = None,
) -> Optional[SkillInfo]:
    """
    Get a skill by name.

    Convenience function that creates a SkillManager and retrieves the skill.
    """
    manager = SkillManager(config)
    return await manager.get(skill_name)


async def list_skills(
    config: Optional[SkillManagerConfig] = None,
) -> List[SkillInfo]:
    """
    List all skills.

    Convenience function that creates a SkillManager and lists skills.
    """
    manager = SkillManager(config)
    return await manager.list()


async def get_skill_dirs(
    config: Optional[SkillManagerConfig] = None,
) -> List[str]:
    """
    Get all skill directories.

    Convenience function that creates a SkillManager and gets directories.
    """
    manager = SkillManager(config)
    return await manager.dirs()


# Singleton instance for global access
_global_manager: Optional[SkillManager] = None


def get_global_manager() -> SkillManager:
    """
    Get the global skill manager instance.

    Returns:
        Global SkillManager instance
    """
    global _global_manager
    if _global_manager is None:
        _global_manager = SkillManager()
    return _global_manager


def set_global_manager(manager: SkillManager):
    """
    Set the global skill manager instance.

    Args:
        manager: SkillManager instance to use as global
    """
    global _global_manager
    _global_manager = manager
