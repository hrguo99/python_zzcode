"""
Data models for the Skill system.

This module defines the core data structures used throughout the skill system.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum


class SkillStatus(str, Enum):
    """Skill loading status."""
    LOADED = "loaded"
    ERROR = "error"
    NOT_FOUND = "not_found"
    PERMISSION_DENIED = "permission_denied"


@dataclass
class SkillMetadata:
    """
    Metadata for a skill.

    Attributes:
        name: Skill name
        description: Human-readable description
        location: Path to SKILL.md file
        mode: Agent mode (primary, subagent, all)
        model: Optional model specification
        files: List of related files
        directory: Base directory for the skill
    """
    name: str
    description: str
    location: str
    mode: Optional[str] = None
    model: Optional[str] = None
    files: List[str] = field(default_factory=list)
    directory: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "location": self.location,
            "mode": self.mode,
            "model": self.model,
            "files": self.files,
            "directory": self.directory,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillMetadata":
        """Create from dictionary representation."""
        return cls(
            name=data["name"],
            description=data["description"],
            location=data["location"],
            mode=data.get("mode"),
            model=data.get("model"),
            files=data.get("files", []),
            directory=data.get("directory"),
        )


@dataclass
class SkillInfo:
    """
    Complete skill information.

    This corresponds to the Skill.Info schema in the TypeScript implementation.

    Attributes:
        name: Unique skill identifier
        description: Human-readable description
        location: Path to SKILL.md file
        content: Markdown content of the skill
        metadata: Additional metadata
    """
    name: str
    description: str
    location: str
    content: str
    metadata: SkillMetadata = field(default_factory=SkillMetadata)

    def __post_init__(self):
        """Initialize metadata after dataclass creation."""
        if self.metadata.name != self.name:
            self.metadata = SkillMetadata(
                name=self.name,
                description=self.description,
                location=self.location,
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "location": self.location,
            "content": self.content,
            "metadata": self.metadata.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillInfo":
        """Create from dictionary representation."""
        metadata_data = data.get("metadata", {})
        metadata = SkillMetadata.from_dict(metadata_data) if metadata_data else None

        return cls(
            name=data["name"],
            description=data["description"],
            location=data["location"],
            content=data["content"],
            metadata=metadata or SkillMetadata(
                name=data["name"],
                description=data["description"],
                location=data["location"],
            ),
        )


@dataclass
class SkillConfig:
    """
    Configuration for skill loading.

    Attributes:
        paths: Additional skill directory paths
        urls: Remote skill URLs
        disable_external: Disable external skill loading
    """
    paths: List[str] = field(default_factory=list)
    urls: List[str] = field(default_factory=list)
    disable_external: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "paths": self.paths,
            "urls": self.urls,
            "disable_external": self.disable_external,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillConfig":
        """Create from dictionary representation."""
        return cls(
            paths=data.get("paths", []),
            urls=data.get("urls", []),
            disable_external=data.get("disable_external", False),
        )


class SkillError(Exception):
    """Base exception for skill-related errors."""

    def __init__(self, message: str, skill_name: Optional[str] = None):
        """
        Initialize a skill error.

        Args:
            message: Error message
            skill_name: Optional skill name
        """
        self.message = message
        self.skill_name = skill_name
        super().__init__(message)


class SkillNotFoundError(SkillError):
    """Raised when a skill is not found."""

    def __init__(self, skill_name: str, available_skills: Optional[List[str]] = None):
        """
        Initialize not found error.

        Args:
            skill_name: Name of the skill that wasn't found
            available_skills: List of available skill names
        """
        self.available_skills = available_skills or []
        message = f"Skill '{skill_name}' not found"
        if available_skills:
            message += f". Available skills: {', '.join(available_skills)}"
        super().__init__(message, skill_name)


class SkillInvalidError(SkillError):
    """Raised when a skill file is invalid."""

    def __init__(self, path: str, reason: str, issues: Optional[List[str]] = None):
        """
        Initialize invalid error.

        Args:
            path: Path to the invalid skill file
            reason: Reason why it's invalid
            issues: Optional list of specific issues
        """
        self.path = path
        self.reason = reason
        self.issues = issues or []
        message = f"Invalid skill file '{path}': {reason}"
        if issues:
            message += f"\nIssues: {', '.join(issues)}"
        super().__init__(message)


class SkillPermissionError(SkillError):
    """Raised when skill access is denied."""

    def __init__(self, skill_name: str, reason: str = "Permission denied"):
        """
        Initialize permission error.

        Args:
            skill_name: Name of the skill
            reason: Reason for denial
        """
        self.reason = reason
        super().__init__(f"{reason}: {skill_name}", skill_name)
