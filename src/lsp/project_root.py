"""
Project root detection utilities for LSP.

This module provides utilities for finding project root directories
based on marker files.
"""

import os
from pathlib import Path
from typing import Optional, List


def find_nearest_root(
    filepath: str,
    include_patterns: List[str],
    exclude_patterns: Optional[List[str]] = None,
    stop_at: Optional[str] = None,
) -> Optional[str]:
    """
    Find the nearest directory containing any of the include patterns.

    This function searches upward from the file's directory until it finds
    a directory containing one of the marker files/patterns.

    Args:
        filepath: Path to the file
        include_patterns: List of file/directory patterns to find
        exclude_patterns: Optional patterns that exclude a directory
        stop_at: Directory to stop searching at (default: current directory)

    Returns:
        Path to the root directory, or None if not found
    """
    filepath = os.path.abspath(filepath)
    start_dir = os.path.dirname(filepath)

    # Default stop directory
    if stop_at is None:
        stop_at = os.getcwd()

    stop_at = os.path.abspath(stop_at)

    # Check if we should exclude this path
    if exclude_patterns:
        excluded = _find_nearest_pattern(
            start_dir,
            exclude_patterns,
            stop_at,
        )
        if excluded:
            return None

    # Find include pattern
    result = _find_nearest_pattern(
        start_dir,
        include_patterns,
        stop_at,
    )

    if result:
        return os.path.dirname(result)

    # Return stop_at as fallback
    return stop_at if os.path.exists(stop_at) else None


def _find_nearest_pattern(
    start_dir: str,
    patterns: List[str],
    stop_at: str,
) -> Optional[str]:
    """
    Find the nearest matching pattern by searching upward.

    Args:
        start_dir: Directory to start searching from
        patterns: List of file/directory patterns to match
        stop_at: Directory to stop searching at

    Returns:
        Path to the matched file, or None if not found
    """
    current_dir = start_dir

    while True:
        # Check each pattern
        for pattern in patterns:
            # Support both simple filenames and glob patterns
            if "*" in pattern or "?" in pattern:
                # Use glob for wildcard patterns
                import glob as glob_module
                matches = glob_module.glob(os.path.join(current_dir, pattern))
                if matches:
                    return matches[0]
            else:
                # Simple file/directory check
                target = os.path.join(current_dir, pattern)
                if os.path.exists(target):
                    return target

        # Move up to parent directory
        parent_dir = os.path.dirname(current_dir)

        # Stop if we've reached the stop directory or filesystem root
        if parent_dir == current_dir or current_dir == stop_at:
            break

        current_dir = parent_dir

        # Safety check: don't go above stop directory
        if stop_at and not os.path.abspath(current_dir).startswith(os.path.abspath(stop_at)):
            break

    return None


def find_git_root(filepath: str, stop_at: Optional[str] = None) -> Optional[str]:
    """
    Find the git repository root for a file.

    Args:
        filepath: Path to the file
        stop_at: Directory to stop searching at

    Returns:
        Path to the git root, or None if not in a git repo
    """
    return find_nearest_root(filepath, [".git"], stop_at=stop_at)


def find_package_json_root(filepath: str, stop_at: Optional[str] = None) -> Optional[str]:
    """
    Find the nearest package.json directory.

    Args:
        filepath: Path to the file
        stop_at: Directory to stop searching at

    Returns:
        Path to the directory containing package.json
    """
    return find_nearest_root(filepath, ["package.json"], stop_at=stop_at)


def find_python_root(filepath: str, stop_at: Optional[str] = None) -> Optional[str]:
    """
    Find the Python project root.

    Looks for common Python project markers.

    Args:
        filepath: Path to the file
        stop_at: Directory to stop searching at

    Returns:
        Path to the Python project root
    """
    markers = [
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "requirements.txt",
        "Pipfile",
        "pyproject.toml",
        "pyrightconfig.json",
        ".python-version",
    ]
    return find_nearest_root(filepath, markers, stop_at=stop_at)


def find_cargo_root(filepath: str, stop_at: Optional[str] = None) -> Optional[str]:
    """
    Find the Cargo (Rust) project root.

    Args:
        filepath: Path to the file
        stop_at: Directory to stop searching at

    Returns:
        Path to the Cargo.toml directory
    """
    return find_nearest_root(filepath, ["Cargo.toml", "Cargo.lock"], stop_at=stop_at)


def find_go_mod_root(filepath: str, stop_at: Optional[str] = None) -> Optional[str]:
    """
    Find the Go module root.

    Args:
        filepath: Path to the file
        stop_at: Directory to stop searching at

    Returns:
        Path to the go.mod directory
    """
    return find_nearest_root(filepath, ["go.mod", "go.sum"], stop_at=stop_at)


def find_java_root(filepath: str, stop_at: Optional[str] = None) -> Optional[str]:
    """
    Find the Java project root.

    Args:
        filepath: Path to the file
        stop_at: Directory to stop searching at

    Returns:
        Path to the Java project root
    """
    markers = [
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        ".project",
        ".classpath",
    ]
    return find_nearest_root(filepath, markers, stop_at=stop_at)


def find_csharp_root(filepath: str, stop_at: Optional[str] = None) -> Optional[str]:
    """
    Find the C# project root.

    Args:
        filepath: Path to the file
        stop_at: Directory to stop searching at

    Returns:
        Path to the C# project root
    """
    markers = [
        ".slnx",
        ".sln",
        ".csproj",
        "global.json",
    ]
    return find_nearest_root(filepath, markers, stop_at=stop_at)


def find_ruby_root(filepath: str, stop_at: Optional[str] = None) -> Optional[str]:
    """
    Find the Ruby project root.

    Args:
        filepath: Path to the file
        stop_at: Directory to stop searching at

    Returns:
        Path to the Gemfile directory
    """
    return find_nearest_root(filepath, ["Gemfile"], stop_at=stop_at)
