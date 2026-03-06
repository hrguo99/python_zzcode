"""
Built-in tool implementations.

This module provides the standard tools that come with OpenCode.
"""

import asyncio
import os
import subprocess
import glob as glob_module
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
import time

from .base import ToolDefinition, ToolContext, define_tool
from .models import ToolResult, ToolMetadata


class BashTool(ToolDefinition):
    """
    Execute shell commands.

    This tool runs bash commands with timeout control and permission checking.
    """

    DEFAULT_TIMEOUT = 120000  # 2 minutes in milliseconds
    MAX_OUTPUT_LENGTH = 10000

    def __init__(self):
        super().__init__("bash")
        self._description = None
        self._parameters_schema = None

    async def initialize(self) -> None:
        """Initialize the bash tool."""
        self._description = (
            "Execute shell commands in the current directory. "
            "Use this for running commands, scripts, and build tools. "
            "Commands will timeout after 2 minutes by default."
        )

        self._parameters_schema = {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute",
                },
                "timeout": {
                    "type": "number",
                    "description": "Optional timeout in milliseconds (default: 120000)",
                },
                "workdir": {
                    "type": "string",
                    "description": "Working directory for the command (default: current directory)",
                },
                "description": {
                    "type": "string",
                    "description": "Clear, concise description of what this command does (5-10 words)",
                },
            },
            "required": ["command"],
        }

    async def execute(self, args: Dict[str, Any], ctx: ToolContext) -> ToolResult:
        """
        Execute a bash command.

        Args:
            args: Command arguments
            ctx: Execution context

        Returns:
            Command output
        """
        command = args["command"]
        timeout_ms = args.get("timeout", self.DEFAULT_TIMEOUT)
        workdir = args.get("workdir", os.getcwd())
        description = args.get("description", command)

        # Convert timeout to seconds
        timeout_sec = timeout_ms / 1000.0

        # Request permission
        await ctx.ask_permission(
            permission="bash",
            patterns=[command],
            always=[f"{command.split()[0]} *"],
            metadata={
                "command": command,
                "workdir": workdir,
            },
        )

        # Check for abort
        if ctx.is_aborted():
            raise RuntimeError("Command execution aborted")

        start_time = time.time()

        try:
            # Execute command
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=workdir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                shell=True,
            )

            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout_sec,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise RuntimeError(f"Command timed out after {timeout_ms}ms")

            output = stdout.decode("utf-8", errors="replace")
            error_output = stderr.decode("utf-8", errors="replace")

            # Combine stdout and stderr
            if error_output:
                output = f"{output}\n{error_output}" if output else error_output

            # If command succeeded with no output, provide clear success message
            if process.returncode == 0 and not output.strip():
                output = f"Command executed successfully (exit code 0)"

            # Truncate if too long
            truncated = False
            if len(output) > self.MAX_OUTPUT_LENGTH:
                output = output[: self.MAX_OUTPUT_LENGTH] + "\n... (output truncated)"
                truncated = True

            duration = time.time() - start_time

            return ToolResult(
                title=description,
                output=output,
                metadata=ToolMetadata(
                    exit_code=process.returncode,
                    truncated=truncated,
                    duration=duration,
                ),
            )

        except Exception as e:
            duration = time.time() - start_time
            return ToolResult(
                title=description,
                output=f"Error executing command: {str(e)}",
                metadata=ToolMetadata(
                    error=str(e),
                    duration=duration,
                ),
            )


class ReadTool(ToolDefinition):
    """
    Read file contents.

    This tool reads files from the filesystem with support for pagination.
    """

    DEFAULT_LIMIT = 2000

    def __init__(self):
        super().__init__("read")
        self._description = None
        self._parameters_schema = None

    async def initialize(self) -> None:
        """Initialize the read tool."""
        self._description = (
            "Read the contents of a file. "
            "Supports reading files with optional offset and limit for pagination. "
            "Can also list directory contents."
        )

        self._parameters_schema = {
            "type": "object",
            "properties": {
                "filePath": {
                    "type": "string",
                    "description": "Absolute path to the file or directory to read",
                },
                "offset": {
                    "type": "number",
                    "description": "Line number to start reading from (1-indexed, default: 1)",
                },
                "limit": {
                    "type": "number",
                    "description": f"Maximum number of lines to read (default: {self.DEFAULT_LIMIT})",
                },
            },
            "required": ["filePath"],
        }

    async def execute(self, args: Dict[str, Any], ctx: ToolContext) -> ToolResult:
        """
        Read a file or directory.

        Args:
            args: Read arguments
            ctx: Execution context

        Returns:
            File/directory contents
        """
        filepath = args["filePath"]
        offset = args.get("offset", 1)
        limit = args.get("limit", self.DEFAULT_LIMIT)

        if offset < 1:
            raise ValueError("offset must be greater than or equal to 1")

        # Convert to absolute path
        if not os.path.isabs(filepath):
            filepath = os.path.abspath(filepath)

        # Check if path exists
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        # Request permission
        await ctx.ask_permission(
            permission="read",
            patterns=[filepath],
            always=["*"],
            metadata={"filepath": filepath},
        )

        # Check for abort
        if ctx.is_aborted():
            raise RuntimeError("Read operation aborted")

        start_time = time.time()

        try:
            if os.path.isdir(filepath):
                # List directory contents
                entries = os.listdir(filepath)
                entries.sort()

                # Apply pagination
                start_idx = offset - 1
                end_idx = start_idx + limit
                sliced = entries[start_idx:end_idx]
                truncated = end_idx < len(entries)

                output = "\n".join(sliced)
                if truncated:
                    output += f"\n... ({len(entries) - end_idx} more entries)"

                return ToolResult(
                    title=f"Directory listing for {filepath}",
                    output=output,
                    metadata=ToolMetadata(duration=time.time() - start_time),
                )
            else:
                # Read file
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()

                # Apply pagination
                start_idx = offset - 1
                end_idx = start_idx + limit
                sliced = lines[start_idx:end_idx]
                truncated = end_idx < len(lines)

                output = "".join(sliced)
                if truncated:
                    output += f"\n... ({len(lines) - end_idx} more lines)"

                return ToolResult(
                    title=f"Read {filepath}",
                    output=output,
                    metadata=ToolMetadata(
                        truncated=truncated,
                        duration=time.time() - start_time,
                    ),
                )

        except Exception as e:
            duration = time.time() - start_time
            return ToolResult(
                title=f"Read {filepath}",
                output=f"Error reading file: {str(e)}",
                metadata=ToolMetadata(
                    error=str(e),
                    duration=duration,
                ),
            )


class EditTool(ToolDefinition):
    """
    Edit file contents.

    This tool edits files by replacing text.
    """

    def __init__(self):
        super().__init__("edit")
        self._description = None
        self._parameters_schema = None

    async def initialize(self) -> None:
        """Initialize the edit tool."""
        self._description = (
            "Edit a file by replacing text. "
            "Finds occurrences of oldString and replaces them with newString. "
            "Use replaceAll to replace all occurrences instead of just the first."
        )

        self._parameters_schema = {
            "type": "object",
            "properties": {
                "filePath": {
                    "type": "string",
                    "description": "Absolute path to the file to edit",
                },
                "oldString": {
                    "type": "string",
                    "description": "Text to replace (empty to create new file)",
                },
                "newString": {
                    "type": "string",
                    "description": "Replacement text",
                },
                "replaceAll": {
                    "type": "boolean",
                    "description": "Replace all occurrences (default: false)",
                },
            },
            "required": ["filePath", "oldString", "newString"],
        }

    async def execute(self, args: Dict[str, Any], ctx: ToolContext) -> ToolResult:
        """
        Edit a file.

        Args:
            args: Edit arguments
            ctx: Execution context

        Returns:
            Edit result
        """
        filepath = args["filePath"]
        old_string = args["oldString"]
        new_string = args["newString"]
        replace_all = args.get("replaceAll", False)

        if old_string == new_string:
            raise ValueError("oldString and newString must be different")

        # Convert to absolute path
        if not os.path.isabs(filepath):
            filepath = os.path.abspath(filepath)

        # Check for abort
        if ctx.is_aborted():
            raise RuntimeError("Edit operation aborted")

        start_time = time.time()

        try:
            if old_string == "":
                # Create new file
                await ctx.ask_permission(
                    permission="edit",
                    patterns=[filepath],
                    always=["*"],
                    metadata={
                        "filepath": filepath,
                        "operation": "create",
                    },
                )

                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_string)

                return ToolResult(
                    title=f"Created {filepath}",
                    output=f"Created new file with {len(new_string)} characters",
                    metadata=ToolMetadata(duration=time.time() - start_time),
                )
            else:
                # Edit existing file
                if not os.path.exists(filepath):
                    raise FileNotFoundError(f"File not found: {filepath}")

                # Read original content
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                # Perform replacement
                if replace_all:
                    new_content = content.replace(old_string, new_string)
                    count = content.count(old_string)
                else:
                    if old_string not in content:
                        raise ValueError(f"oldString not found in file")
                    new_content = content.replace(old_string, new_string, 1)
                    count = 1

                # Calculate diff
                diff_lines = count
                await ctx.ask_permission(
                    permission="edit",
                    patterns=[filepath],
                    always=["*"],
                    metadata={
                        "filepath": filepath,
                        "operation": "edit",
                        "diff_lines": diff_lines,
                    },
                )

                # Write new content
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)

                return ToolResult(
                    title=f"Edited {filepath}",
                    output=f"Replaced {count} occurrence(s)",
                    metadata=ToolMetadata(duration=time.time() - start_time),
                )

        except Exception as e:
            duration = time.time() - start_time
            return ToolResult(
                title=f"Edit {filepath}",
                output=f"Error editing file: {str(e)}",
                metadata=ToolMetadata(
                    error=str(e),
                    duration=duration,
                ),
            )


class WriteTool(ToolDefinition):
    """
    Write content to a file.

    This tool writes or overwrites files completely.
    """

    def __init__(self):
        super().__init__("write")
        self._description = None
        self._parameters_schema = None

    async def initialize(self) -> None:
        """Initialize the write tool."""
        self._description = (
            "Write content to a file, overwriting any existing content. "
            "Use this to create new files or completely replace file contents."
        )

        self._parameters_schema = {
            "type": "object",
            "properties": {
                "filePath": {
                    "type": "string",
                    "description": "Absolute path to the file to write",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            "required": ["filePath", "content"],
        }

    async def execute(self, args: Dict[str, Any], ctx: ToolContext) -> ToolResult:
        """
        Write to a file.

        Args:
            args: Write arguments
            ctx: Execution context

        Returns:
            Write result
        """
        filepath = args["filePath"]
        content = args["content"]

        # Convert to absolute path
        if not os.path.isabs(filepath):
            filepath = os.path.abspath(filepath)

        # Request permission
        await ctx.ask_permission(
            permission="edit",
            patterns=[filepath],
            always=["*"],
            metadata={
                "filepath": filepath,
                "operation": "write",
            },
        )

        # Check for abort
        if ctx.is_aborted():
            raise RuntimeError("Write operation aborted")

        start_time = time.time()

        try:
            # Write file
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            return ToolResult(
                title=f"Wrote {filepath}",
                output=f"Wrote {len(content)} characters",
                metadata=ToolMetadata(duration=time.time() - start_time),
            )

        except Exception as e:
            duration = time.time() - start_time
            return ToolResult(
                title=f"Write {filepath}",
                output=f"Error writing file: {str(e)}",
                metadata=ToolMetadata(
                    error=str(e),
                    duration=duration,
                ),
            )


class GlobTool(ToolDefinition):
    """
    Find files using glob patterns.

    This tool searches for files matching a pattern.
    """

    def __init__(self):
        super().__init__("glob")
        self._description = None
        self._parameters_schema = None

    async def initialize(self) -> None:
        """Initialize the glob tool."""
        self._description = (
            "Find files using glob patterns. "
            "Supports wildcards like *, ?, and character ranges [a-z]. "
            "Searches recursively in the current directory."
        )

        self._parameters_schema = {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match files (e.g., '*.py', 'src/**/*.ts')",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (default: current directory)",
                },
            },
            "required": ["pattern"],
        }

    async def execute(self, args: Dict[str, Any], ctx: ToolContext) -> ToolResult:
        """
        Execute glob search.

        Args:
            args: Glob arguments
            ctx: Execution context

        Returns:
            Matching files
        """
        pattern = args["pattern"]
        search_path = args.get("path", ".")

        # Convert to absolute path
        if not os.path.isabs(search_path):
            search_path = os.path.abspath(search_path)

        # Request permission
        await ctx.ask_permission(
            permission="glob",
            patterns=[pattern],
            always=["*"],
            metadata={"pattern": pattern, "path": search_path},
        )

        # Check for abort
        if ctx.is_aborted():
            raise RuntimeError("Glob operation aborted")

        start_time = time.time()

        try:
            # Use Python's glob module
            full_pattern = os.path.join(search_path, pattern)
            matches = glob_module.glob(full_pattern, recursive=True)

            # Sort results
            matches.sort()

            # Format output
            output = "\n".join(matches) if matches else "No matches found"

            return ToolResult(
                title=f"Glob: {pattern}",
                output=output,
                metadata=ToolMetadata(
                    duration=time.time() - start_time,
                    extra={"count": len(matches)},
                ),
            )

        except Exception as e:
            duration = time.time() - start_time
            return ToolResult(
                title=f"Glob: {pattern}",
                output=f"Error during glob search: {str(e)}",
                metadata=ToolMetadata(
                    error=str(e),
                    duration=duration,
                ),
            )


class GrepTool(ToolDefinition):
    """
    Search for text in files.

    This tool searches for text patterns in files.
    """

    def __init__(self):
        super().__init__("grep")
        self._description = None
        self._parameters_schema = None

    async def initialize(self) -> None:
        """Initialize the grep tool."""
        self._description = (
            "Search for text patterns in files using regex. "
            "Returns matching lines with file names and line numbers."
        )

        self._parameters_schema = {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regular expression pattern to search for",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (default: current directory)",
                },
                "filePattern": {
                    "type": "string",
                    "description": "Glob pattern to filter files (e.g., '*.py')",
                },
            },
            "required": ["pattern"],
        }

    async def execute(self, args: Dict[str, Any], ctx: ToolContext) -> ToolResult:
        """
        Execute grep search.

        Args:
            args: Grep arguments
            ctx: Execution context

        Returns:
            Matching lines
        """
        pattern = args["pattern"]
        search_path = args.get("path", ".")
        file_pattern = args.get("filePattern")

        # Convert to absolute path
        if not os.path.isabs(search_path):
            search_path = os.path.abspath(search_path)

        # Request permission
        await ctx.ask_permission(
            permission="grep",
            patterns=[pattern],
            always=["*"],
            metadata={"pattern": pattern, "path": search_path},
        )

        # Check for abort
        if ctx.is_aborted():
            raise RuntimeError("Grep operation aborted")

        start_time = time.time()

        try:
            # Compile regex pattern
            regex = re.compile(pattern)

            # Find files
            matches = []
            match_count = 0

            for root, dirs, files in os.walk(search_path):
                for filename in files:
                    filepath = os.path.join(root, filename)

                    # Apply file pattern filter
                    if file_pattern:
                        if not glob_module.fnmatch.fnmatch(filename, file_pattern):
                            continue

                    try:
                        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                            for line_num, line in enumerate(f, 1):
                                if regex.search(line):
                                    rel_path = os.path.relpath(filepath)
                                    matches.append(f"{rel_path}:{line_num}: {line.rstrip()}")
                                    match_count += 1
                    except Exception:
                        # Skip files that can't be read
                        continue

            output = "\n".join(matches) if matches else "No matches found"

            return ToolResult(
                title=f"Grep: {pattern}",
                output=output,
                metadata=ToolMetadata(
                    duration=time.time() - start_time,
                    extra={"count": match_count},
                ),
            )

        except Exception as e:
            duration = time.time() - start_time
            return ToolResult(
                title=f"Grep: {pattern}",
                output=f"Error during grep search: {str(e)}",
                metadata=ToolMetadata(
                    error=str(e),
                    duration=duration,
                ),
            )
