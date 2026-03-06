"""
Language extension mappings for LSP.

This module provides file extension to language ID mappings
used by LSP servers.
"""

from typing import Dict

# Language ID mappings based on file extensions
LANGUAGE_EXTENSIONS: Dict[str, str] = {
    # Web technologies
    ".js": "javascript",
    ".jsx": "javascriptreact",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescriptreact",
    ".mts": "typescript",
    ".cts": "typescript",
    ".vue": "vue",
    ".svelte": "svelte",
    ".astro": "astro",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    ".json": "json",
    ".jsonc": "jsonc",

    # Python
    ".py": "python",
    ".pyi": "python",

    # Go
    ".go": "go",

    # Rust
    ".rs": "rust",

    # Java
    ".java": "java",
    ".jsp": "jsp",

    # Kotlin
    ".kt": "kotlin",
    ".kts": "kotlin",

    # C/C++
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c++": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".hxx": "cpp",
    ".h++": "cpp",

    # C#
    ".cs": "csharp",

    # PHP
    ".php": "php",

    # Ruby
    ".rb": "ruby",
    ".rake": "ruby",
    ".gemspec": "ruby",

    # Swift
    ".swift": "swift",
    ".objc": "objective-c",
    ".objcpp": "objective-cpp",

    # Shell
    ".sh": "shellscript",
    ".bash": "shellscript",
    ".zsh": "shellscript",
    ".ksh": "shellscript",
    ".fish": "fish",

    # Configuration
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".ini": "ini",
    ".xml": "xml",
    ".dockerfile": "dockerfile",
    "Dockerfile": "dockerfile",

    # Markdown
    ".md": "markdown",
    ".mdx": "mdx",

    # Other
    ".sql": "sql",
    ".graphql": "graphql",
    ".gql": "graphql",
    ".rlib": "rust",
    ".cmake": "cmake",
    ".lua": "lua",
    ".dart": "dart",
    ".ex": "elixir",
    ".exs": "elixir",
    ".ml": "ocaml",
    ".mli": "ocaml",
    ".zig": "zig",
    ".zon": "zig",
    ".nix": "nix",
    ".tex": "latex",
    ".bib": "bibtex",
    ".tf": "terraform",
    ".tfvars": "terraform",
    ".prisma": "prisma",
    ".typ": "typst",
    ".gleam": "gleam",
    ".jl": "julia",
    ".clj": "clojure",
    ".cljs": "clojure",
    ".cljc": "clojure",
    ".edn": "clojure",
    ".hs": "haskell",
    ".lhs": "haskell",
}


def get_language_id(extension: str) -> str:
    """
    Get the language ID for a file extension.

    Args:
        extension: File extension (e.g., ".py", ".ts")

    Returns:
        Language ID string
    """
    # Ensure extension starts with a dot
    if not extension.startswith("."):
        extension = "." + extension

    return LANGUAGE_EXTENSIONS.get(extension, "plaintext")
