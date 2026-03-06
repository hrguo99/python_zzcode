"""
Skill discovery and remote loading module.

This module handles discovering and downloading skills from remote sources.
"""

import os
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
import json
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


class SkillDiscovery:
    """
    Handle skill discovery and remote loading.

    This class provides methods to discover and download skills from remote URLs.
    Corresponds to the Discovery namespace in the TypeScript implementation.
    """

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize the skill discovery.

        Args:
            cache_dir: Directory to cache downloaded skills
        """
        if cache_dir is None:
            cache_dir = os.path.expanduser("~/.cache/opencode/skills")
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    def get_cache_dir(self) -> str:
        """
        Get the cache directory.

        Returns:
            Path to the cache directory
        """
        return self.cache_dir

    async def _download_file(self, url: str, dest: str) -> bool:
        """
        Download a file from URL to destination.

        Args:
            url: URL to download from
            dest: Destination file path

        Returns:
            True if successful, False otherwise
        """
        if os.path.exists(dest):
            return True

        try:
            logger.info(f"Downloading {url} to {dest}")
            with urllib.request.urlopen(url) as response:
                if response.status != 200:
                    logger.error(f"Failed to download {url}: status {response.status}")
                    return False

                # Create destination directory
                os.makedirs(os.path.dirname(dest), exist_ok=True)

                # Write file
                with open(dest, "wb") as f:
                    f.write(response.read())

            return True

        except urllib.error.URLError as e:
            logger.error(f"Failed to download {url}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
            return False

    async def pull(self, url: str) -> List[str]:
        """
        Pull skills from a remote URL.

        Downloads skills from a remote index.json and all referenced files.

        Args:
            url: Base URL of the skills repository

        Returns:
            List of downloaded skill directory paths

        Example:
            ```python
            discovery = SkillDiscovery()
            skills = await discovery.pull("https://example.com/skills")
            # Downloads skills from https://example.com/skills/index.json
            ```
        """
        result: List[str] = []

        # Ensure URL ends with /
        base = url if url.endswith("/") else f"{url}/"
        index_url = f"{base}index.json"

        logger.info(f"Fetching index from {index_url}")

        try:
            # Fetch index
            with urllib.request.urlopen(index_url) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch index: status {response.status}")
                    return result

                data = json.loads(response.read())

            # Validate index format
            if not isinstance(data, dict) or "skills" not in data:
                logger.warning(f"Invalid index format at {index_url}")
                return result

            skills_data = data["skills"]
            if not isinstance(skills_data, list):
                logger.warning(f"Invalid skills list in index at {index_url}")
                return result

            # Filter valid skill entries
            valid_skills = []
            for skill in skills_data:
                if not isinstance(skill, dict):
                    continue
                if "name" not in skill or "files" not in skill:
                    logger.warning(f"Invalid skill entry in index from {index_url}")
                    continue
                if not isinstance(skill["files"], list):
                    logger.warning(f"Invalid files list for skill {skill.get('name')}")
                    continue
                valid_skills.append(skill)

            # Download all skills
            download_tasks = []
            for skill in valid_skills:
                task = self._download_skill(base, skill)
                download_tasks.append(task)

            skill_dirs = await asyncio.gather(*download_tasks, return_exceptions=True)

            # Collect successful downloads
            for skill_dir in skill_dirs:
                if isinstance(skill_dir, str):
                    result.append(skill_dir)
                elif isinstance(skill_dir, Exception):
                    logger.error(f"Error downloading skill: {skill_dir}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse index from {index_url}: {e}")
        except urllib.error.URLError as e:
            logger.error(f"Failed to fetch index from {index_url}: {e}")
        except Exception as e:
            logger.error(f"Error pulling skills from {url}: {e}")

        return result

    async def _download_skill(self, base_url: str, skill_data: Dict[str, Any]) -> Optional[str]:
        """
        Download a single skill and its files.

        Args:
            base_url: Base URL of the skills repository
            skill_data: Skill data from index

        Returns:
            Path to the downloaded skill directory, or None if failed
        """
        skill_name = skill_data["name"]
        files = skill_data["files"]

        # Create skill directory
        skill_dir = os.path.join(self.cache_dir, skill_name)
        os.makedirs(skill_dir, exist_ok=True)

        # Download all files
        download_tasks = []
        for file_path in files:
            # Construct full URL
            file_url = f"{base_url}{skill_name}/{file_path}"
            dest_path = os.path.join(skill_dir, file_path)

            task = self._download_file(file_url, dest_path)
            download_tasks.append(task)

        # Wait for all files to download
        results = await asyncio.gather(*download_tasks, return_exceptions=True)

        # Check if SKILL.md exists
        skill_md_path = os.path.join(skill_dir, "SKILL.md")
        if os.path.exists(skill_md_path):
            return skill_dir

        logger.warning(f"SKILL.md not found for skill {skill_name}")
        return None

    async def discover_from_urls(self, urls: List[str]) -> List[str]:
        """
        Discover and download skills from multiple URLs.

        Args:
            urls: List of skill repository URLs

        Returns:
            List of all downloaded skill directory paths
        """
        all_skills = []

        pull_tasks = []
        for url in urls:
            task = self.pull(url)
            pull_tasks.append(task)

        results = await asyncio.gather(*pull_tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_skills.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Error pulling from URL: {result}")

        return all_skills

    def clear_cache(self):
        """Clear the skill cache directory."""
        import shutil

        if os.path.exists(self.cache_dir):
            shutil.rmtree(self.cache_dir)
            logger.info(f"Cleared skill cache at {self.cache_dir}")

        os.makedirs(self.cache_dir, exist_ok=True)

    def get_cache_size(self) -> int:
        """
        Get the size of the cache directory in bytes.

        Returns:
            Size in bytes
        """
        total_size = 0

        if not os.path.exists(self.cache_dir):
            return 0

        for dirpath, dirnames, filenames in os.walk(self.cache_dir):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.isfile(filepath):
                    total_size += os.path.getsize(filepath)

        return total_size


# Convenience functions
async def pull_skills(url: str, cache_dir: Optional[str] = None) -> List[str]:
    """
    Pull skills from a remote URL.

    Convenience function that creates a SkillDiscovery and pulls skills.

    Args:
        url: URL of the skills repository
        cache_dir: Optional cache directory

    Returns:
        List of downloaded skill directories
    """
    discovery = SkillDiscovery(cache_dir)
    return await discovery.pull(url)
