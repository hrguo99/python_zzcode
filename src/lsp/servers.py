"""
Comprehensive LSP Server definitions and management.

This module provides extensive language server definitions for various
programming languages, similar to the TypeScript implementation.
"""

import asyncio
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from enum import Enum
import shutil

from .project_root import (
    find_nearest_root,
    find_git_root,
    find_package_json_root,
    find_python_root,
    find_cargo_root,
    find_go_mod_root,
    find_java_root,
    find_csharp_root,
    find_ruby_root,
)

logger = logging.getLogger(__name__)


class LanguageServerID(str, Enum):
    """Language server identifiers."""
    # JavaScript/TypeScript
    TYPESCRIPT = "typescript"
    VUE = "vue"
    SVELTE = "svelte"
    ASTRO = "astro"
    ESLINT = "eslint"
    OXLINT = "oxlint"
    BIOME = "biome"
    DENO = "deno"

    # Python
    PYRIGHT = "pyright"
    TY = "ty"  # Experimental

    # Go
    GOPLS = "gopls"

    # Rust
    RUST_ANALYZER = "rust-analyzer"

    # Java
    JDTLS = "jdtls"

    # Kotlin
    KOTLIN = "kotlin-ls"

    # C#
    CSHARP = "csharp"

    # F#
    FSHARP = "fsharp"

    # PHP
    INTELEPHENSE = "intelephense"

    # Ruby
    RUBY_LSP = "ruby-lsp"

    # Swift
    SOURCEKIT = "sourcekit-lsp"

    # C/C++
    CLANGD = "clangd"

    # Zig
    ZLS = "zls"

    # Elixir
    ELIXIR_LS = "elixir-ls"

    # Lua
    LUA_LS = "lua-ls"

    # YAML
    YAML_LS = "yaml-ls"

    # Bash
    BASH_LS = "bash"

    # Terraform
    TERRAFORM_LS = "terraform"

    # LaTeX
    TEXLAB = "texlab"

    # Dockerfile
    DOCKER_LS = "dockerfile"

    # Dart
    DART = "dart"

    # OCaml
    OCAML = "ocaml-lsp"

    # Gleam
    GLEAM = "gleam"

    # Clojure
    CLOJURE = "clojure-lsp"

    # Nix
    NIXD = "nixd"

    # Typst
    TINYMIST = "tinymist"

    # Haskell
    HASKELL = "haskell-language-server"

    # Julia
    JULIA = "julials"


@dataclass
class LSPServerHandle:
    """Handle to a running LSP server process."""
    command: List[str]
    cwd: str
    env: Dict[str, str]
    initialization_options: Optional[Dict[str, Any]] = None


@dataclass
class LSPServerInfo:
    """Information about an LSP server."""
    id: str
    name: str
    extensions: List[str]
    global_server: bool = False
    root_function: Optional[Callable[[str], Optional[str]]] = None
    spawn_command: Optional[Callable[[str], Optional[LSPServerHandle]]] = None


class LSPServerRegistry:
    """
    Registry for LSP server definitions.

    This class manages the definitions of all available language servers.
    """

    def __init__(self, project_root: str = "."):
        """Initialize the registry with default servers."""
        self.project_root = os.path.abspath(project_root)
        self._servers: Dict[str, LSPServerInfo] = {}
        self._disabled: set = set()
        self._register_default_servers()

    def _register_default_servers(self):
        """Register default language server definitions."""

        # TypeScript/JavaScript
        self._servers[LanguageServerID.TYPESCRIPT.value] = LSPServerInfo(
            id="typescript",
            name="TypeScript Server",
            extensions=["ts", "tsx", "js", "jsx", "mjs", "cjs", "mts", "cts"],
            global_server=True,
            root_function=lambda f: find_nearest_root(
                f,
                ["package-lock.json", "bun.lockb", "bun.lock", "pnpm-lock.yaml", "yarn.lock"],
                ["deno.json", "deno.jsonc"],
                stop_at=self.project_root,
            ),
            spawn_command=self._spawn_typescript,
        )

        self._servers[LanguageServerID.VUE.value] = LSPServerInfo(
            id="vue",
            name="Vue Language Server",
            extensions=["vue"],
            root_function=lambda f: find_package_json_root(f, stop_at=self.project_root),
            spawn_command=self._spawn_vue,
        )

        self._servers[LanguageServerID.BIOME.value] = LSPServerInfo(
            id="biome",
            name="Biome (JavaScript/TypeScript/JSON/CSS)",
            extensions=["ts", "tsx", "js", "jsx", "mjs", "cjs", "json", "jsonc", "css", "vue", "astro", "svelte"],
            root_function=lambda f: find_nearest_root(
                f,
                ["biome.json", "biome.jsonc", "package-lock.json", "bun.lockb", "bun.lock"],
                stop_at=self.project_root,
            ),
            spawn_command=self._spawn_biome,
        )

        self._servers[LanguageServerID.PYRIGHT.value] = LSPServerInfo(
            id="pyright",
            name="Pyright (Python)",
            extensions=["py", "pyi"],
            root_function=lambda f: find_python_root(f, stop_at=self.project_root),
            spawn_command=self._spawn_pyright,
        )

        self._servers[LanguageServerID.GOPLS.value] = LSPServerInfo(
            id="gopls",
            name="Go Language Server",
            extensions=["go"],
            root_function=lambda f: find_go_mod_root(f, stop_at=self.project_root),
            spawn_command=self._spawn_gopls,
        )

        self._servers[LanguageServerID.RUST_ANALYZER.value] = LSPServerInfo(
            id="rust-analyzer",
            name="Rust Analyzer",
            extensions=["rs"],
            root_function=lambda f: find_cargo_root(f, stop_at=self.project_root),
            spawn_command=self._spawn_rust_analyzer,
        )

        self._servers[LanguageServerID.JDTLS.value] = LSPServerInfo(
            id="jdtls",
            name="Eclipse JDT LS (Java)",
            extensions=["java"],
            root_function=lambda f: find_java_root(f, stop_at=self.project_root),
            spawn_command=self._spawn_jdtls,
        )

        self._servers[LanguageServerID.CSHARP.value] = LSPServerInfo(
            id="csharp",
            name="C# Language Server",
            extensions=["cs"],
            root_function=lambda f: find_csharp_root(f, stop_at=self.project_root),
            spawn_command=self._spawn_csharp,
        )

        self._servers[LanguageServerID.CLANGD.value] = LSPServerInfo(
            id="clangd",
            name="clangd (C/C++)",
            extensions=["c", "cpp", "cc", "cxx", "c++", "h", "hpp", "hh", "hxx", "h++"],
            root_function=lambda f: find_nearest_root(
                f,
                ["compile_commands.json", "compile_flags.txt", ".clangd", "CMakeLists.txt", "Makefile"],
                stop_at=self.project_root,
            ),
            spawn_command=self._spawn_clangd,
        )

        self._servers[LanguageServerID.RUBY_LSP.value] = LSPServerInfo(
            id="ruby-lsp",
            name="Ruby LSP",
            extensions=["rb", "rake", "gemspec"],
            root_function=lambda f: find_ruby_root(f, stop_at=self.project_root),
            spawn_command=self._spawn_ruby_lsp,
        )

        self._servers[LanguageServerID.YAML_LS.value] = LSPServerInfo(
            id="yaml-ls",
            name="YAML Language Server",
            extensions=["yaml", "yml"],
            root_function=lambda f: find_package_json_root(f, stop_at=self.project_root),
            spawn_command=self._spawn_yaml_ls,
        )

        self._servers[LanguageServerID.BASH_LS.value] = LSPServerInfo(
            id="bash",
            name="Bash Language Server",
            extensions=["sh", "bash", "zsh", "ksh"],
            root_function=lambda f: self.project_root,
            spawn_command=self._spawn_bash_ls,
        )

        self._servers[LanguageServerID.TERRAFORM_LS.value] = LSPServerInfo(
            id="terraform",
            name="Terraform Language Server",
            extensions=["tf", "tfvars"],
            root_function=lambda f: find_nearest_root(
                f,
                [".terraform.lock.hcl", "terraform.tfstate"],
                stop_at=self.project_root,
            ),
            spawn_command=self._spawn_terraform_ls,
        )

        self._servers[LanguageServerID.DOCKER_LS.value] = LSPServerInfo(
            id="dockerfile",
            name="Dockerfile Language Server",
            extensions=["dockerfile"],
            root_function=lambda f: self.project_root,
            spawn_command=self._spawn_docker_ls,
        )

        self._servers[LanguageServerID.DART.value] = LSPServerInfo(
            id="dart",
            name="Dart Language Server",
            extensions=["dart"],
            root_function=lambda f: find_nearest_root(
                f,
                ["pubspec.yaml", "analysis_options.yaml"],
                stop_at=self.project_root,
            ),
            spawn_command=self._spawn_dart,
        )

        self._servers[LanguageServerID.OCAML.value] = LSPServerInfo(
            id="ocaml-lsp",
            name="OCaml Language Server",
            extensions=["ml", "mli"],
            root_function=lambda f: find_nearest_root(
                f,
                ["dune-project", "dune-workspace", ".merlin", "opam"],
                stop_at=self.project_root,
            ),
            spawn_command=self._spawn_ocaml,
        )

        self._servers[LanguageServerID.GLEAM.value] = LSPServerInfo(
            id="gleam",
            name="Gleam Language Server",
            extensions=["gleam"],
            root_function=lambda f: find_nearest_root(
                f,
                ["gleam.toml"],
                stop_at=self.project_root,
            ),
            spawn_command=self._spawn_gleam,
        )

        self._servers[LanguageServerID.CLOJURE.value] = LSPServerInfo(
            id="clojure-lsp",
            name="Clojure Language Server",
            extensions=["clj", "cljs", "cljc", "edn"],
            root_function=lambda f: find_nearest_root(
                f,
                ["deps.edn", "project.clj", "shadow-cljs.edn", "bb.edn", "build.boot"],
                stop_at=self.project_root,
            ),
            spawn_command=self._spawn_clojure_lsp,
        )

        self._servers[LanguageServerID.NIXD.value] = LSPServerInfo(
            id="nixd",
            name="Nix Language Server",
            extensions=["nix"],
            root_function=lambda f: find_nearest_root(
                f,
                ["flake.nix"],
                stop_at=self.project_root,
            ) or find_git_root(f, stop_at=self.project_root) or self.project_root,
            spawn_command=self._spawn_nixd,
        )

        self._servers[LanguageServerID.TINYMIST.value] = LSPServerInfo(
            id="tinymist",
            name="Typst Language Server",
            extensions=["typ", "typc"],
            root_function=lambda f: find_nearest_root(
                f,
                ["typst.toml"],
                stop_at=self.project_root,
            ),
            spawn_command=self._spawn_tinymist,
        )

        self._servers[LanguageServerID.HASKELL.value] = LSPServerInfo(
            id="haskell-language-server",
            name="Haskell Language Server",
            extensions=["hs", "lhs"],
            root_function=lambda f: find_nearest_root(
                f,
                ["stack.yaml", "cabal.project", "hie.yaml"],
                stop_at=self.project_root,
            ),
            spawn_command=self._spawn_haskell,
        )

        self._servers[LanguageServerID.JULIA.value] = LSPServerInfo(
            id="julials",
            name="Julia Language Server",
            extensions=["jl"],
            root_function=lambda f: find_nearest_root(
                f,
                ["Project.toml", "Manifest.toml"],
                stop_at=self.project_root,
            ),
            spawn_command=self._spawn_julia,
        )

    # Spawn command methods
    async def _spawn_typescript(self, root: str) -> Optional[LSPServerHandle]:
        """Spawn TypeScript language server."""
        cmd = ["typescript-language-server", "--stdio"]
        if not shutil.which("typescript-language-server"):
            # Try using npx
            cmd = ["npx", "typescript-language-server", "--stdio"]
            if not shutil.which("npx"):
                logger.warning("typescript-language-server not found")
                return None

        return LSPServerHandle(command=cmd, cwd=root, env={})

    async def _spawn_vue(self, root: str) -> Optional[LSPServerHandle]:
        """Spawn Vue language server."""
        cmd = ["vue-language-server", "--stdio"]
        if not shutil.which("vue-language-server"):
            cmd = ["npx", "@vue/language-server", "--stdio"]
            if not shutil.which("npx"):
                logger.warning("vue-language-server not found")
                return None

        return LSPServerHandle(command=cmd, cwd=root, env={})

    async def _spawn_biome(self, root: str) -> Optional[LSPServerHandle]:
        """Spawn Biome language server."""
        cmd = ["biome", "lsp-proxy", "--stdio"]
        if not shutil.which("biome"):
            logger.warning("biome not found")
            return None

        return LSPServerHandle(command=cmd, cwd=root, env={})

    async def _spawn_pyright(self, root: str) -> Optional[LSPServerHandle]:
        """Spawn Pyright language server."""
        cmd = ["pyright-langserver", "--stdio"]
        if not shutil.which("pyright-langserver"):
            # Try using npx
            cmd = ["npx", "pyright", "--stdio"]
            if not shutil.which("npx"):
                logger.warning("pyright-langserver not found")
                return None

        # Check for virtual environment
        venv_paths = [
            os.environ.get("VIRTUAL_ENV"),
            os.path.join(root, ".venv"),
            os.path.join(root, "venv"),
        ]

        init_options = {}
        for venv_path in venv_paths:
            if venv_path and os.path.exists(venv_path):
                if os.name == "nt":  # Windows
                    python_path = os.path.join(venv_path, "Scripts", "python.exe")
                else:
                    python_path = os.path.join(venv_path, "bin", "python")

                if os.path.exists(python_path):
                    init_options["pythonPath"] = python_path
                    break

        return LSPServerHandle(
            command=cmd,
            cwd=root,
            env={},
            initialization_options=init_options if init_options else None,
        )

    async def _spawn_gopls(self, root: str) -> Optional[LSPServerHandle]:
        """Spawn gopls language server."""
        cmd = ["gopls"]
        if not shutil.which("gopls"):
            logger.warning("gopls not found")
            return None

        return LSPServerHandle(command=cmd, cwd=root, env={})

    async def _spawn_rust_analyzer(self, root: str) -> Optional[LSPServerHandle]:
        """Spawn rust-analyzer language server."""
        cmd = ["rust-analyzer"]
        if not shutil.which("rust-analyzer"):
            logger.warning("rust-analyzer not found")
            return None

        return LSPServerHandle(command=cmd, cwd=root, env={})

    async def _spawn_jdtls(self, root: str) -> Optional[LSPServerHandle]:
        """Spawn JDTLS language server."""
        if not shutil.which("java"):
            logger.warning("Java not found")
            return None

        # JDTLS requires special handling
        # This is a simplified version
        logger.warning("JDTLS support requires manual configuration")
        return None

    async def _spawn_csharp(self, root: str) -> Optional[LSPServerHandle]:
        """Spawn C# language server."""
        cmd = ["csharp-ls"]
        if not shutil.which("csharp-ls"):
            logger.warning("csharp-ls not found")
            return None

        return LSPServerHandle(command=cmd, cwd=root, env={})

    async def _spawn_clangd(self, root: str) -> Optional[LSPServerHandle]:
        """Spawn clangd language server."""
        cmd = ["clangd", "--background-index", "--clang-tidy"]
        if not shutil.which("clangd"):
            logger.warning("clangd not found")
            return None

        return LSPServerHandle(command=cmd, cwd=root, env={})

    async def _spawn_ruby_lsp(self, root: str) -> Optional[LSPServerHandle]:
        """Spawn Ruby language server."""
        cmd = ["rubocop", "--lsp"]
        if not shutil.which("rubocop"):
            logger.warning("rubocop not found")
            return None

        return LSPServerHandle(command=cmd, cwd=root, env={})

    async def _spawn_yaml_ls(self, root: str) -> Optional[LSPServerHandle]:
        """Spawn YAML language server."""
        cmd = ["yaml-language-server", "--stdio"]
        if not shutil.which("yaml-language-server"):
            cmd = ["npx", "yaml-language-server", "--stdio"]
            if not shutil.which("npx"):
                logger.warning("yaml-language-server not found")
                return None

        return LSPServerHandle(command=cmd, cwd=root, env={})

    async def _spawn_bash_ls(self, root: str) -> Optional[LSPServerHandle]:
        """Spawn Bash language server."""
        cmd = ["bash-language-server", "start"]
        if not shutil.which("bash-language-server"):
            cmd = ["npx", "bash-language-server", "start"]
            if not shutil.which("npx"):
                logger.warning("bash-language-server not found")
                return None

        return LSPServerHandle(command=cmd, cwd=root, env={})

    async def _spawn_terraform_ls(self, root: str) -> Optional[LSPServerHandle]:
        """Spawn Terraform language server."""
        cmd = ["terraform-ls", "serve"]
        if not shutil.which("terraform-ls"):
            logger.warning("terraform-ls not found")
            return None

        init_options = {
            "experimentalFeatures": {
                "prefillRequiredFields": True,
                "validateOnSave": True,
            }
        }

        return LSPServerHandle(
            command=cmd,
            cwd=root,
            env={},
            initialization_options=init_options,
        )

    async def _spawn_docker_ls(self, root: str) -> Optional[LSPServerHandle]:
        """Spawn Dockerfile language server."""
        cmd = ["docker-langserver", "--stdio"]
        if not shutil.which("docker-langserver"):
            cmd = ["npx", "dockerfile-language-server-nodejs", "--stdio"]
            if not shutil.which("npx"):
                logger.warning("docker-langserver not found")
                return None

        return LSPServerHandle(command=cmd, cwd=root, env={})

    async def _spawn_dart(self, root: str) -> Optional[LSPServerHandle]:
        """Spawn Dart language server."""
        cmd = ["dart", "language-server", "--lsp"]
        if not shutil.which("dart"):
            logger.warning("dart not found")
            return None

        return LSPServerHandle(command=cmd, cwd=root, env={})

    async def _spawn_ocaml(self, root: str) -> Optional[LSPServerHandle]:
        """Spawn OCaml language server."""
        cmd = ["ocamllsp"]
        if not shutil.which("ocamllsp"):
            logger.warning("ocamllsp not found")
            return None

        return LSPServerHandle(command=cmd, cwd=root, env={})

    async def _spawn_gleam(self, root: str) -> Optional[LSPServerHandle]:
        """Spawn Gleam language server."""
        cmd = ["gleam", "lsp"]
        if not shutil.which("gleam"):
            logger.warning("gleam not found")
            return None

        return LSPServerHandle(command=cmd, cwd=root, env={})

    async def _spawn_clojure_lsp(self, root: str) -> Optional[LSPServerHandle]:
        """Spawn Clojure language server."""
        cmd = ["clojure-lsp"]
        if not shutil.which("clojure-lsp"):
            logger.warning("clojure-lsp not found")
            return None

        return LSPServerHandle(command=cmd, cwd=root, env={})

    async def _spawn_nixd(self, root: str) -> Optional[LSPServerHandle]:
        """Spawn Nix language server."""
        cmd = ["nixd"]
        if not shutil.which("nixd"):
            logger.warning("nixd not found")
            return None

        return LSPServerHandle(command=cmd, cwd=root, env={})

    async def _spawn_tinymist(self, root: str) -> Optional[LSPServerHandle]:
        """Spawn Typst language server."""
        cmd = ["tinymist"]
        if not shutil.which("tinymist"):
            logger.warning("tinymist not found")
            return None

        return LSPServerHandle(command=cmd, cwd=root, env={})

    async def _spawn_haskell(self, root: str) -> Optional[LSPServerHandle]:
        """Spawn Haskell language server."""
        cmd = ["haskell-language-server-wrapper", "--lsp"]
        if not shutil.which("haskell-language-server-wrapper"):
            logger.warning("haskell-language-server-wrapper not found")
            return None

        return LSPServerHandle(command=cmd, cwd=root, env={})

    async def _spawn_julia(self, root: str) -> Optional[LSPServerHandle]:
        """Spawn Julia language server."""
        cmd = ["julia", "--startup-file=no", "--history-file=no", "-e", "using LanguageServer; runserver()"]
        if not shutil.which("julia"):
            logger.warning("julia not found")
            return None

        return LSPServerHandle(command=cmd, cwd=root, env={})

    def disable(self, server_id: str):
        """
        Disable a language server.

        Args:
            server_id: Server identifier
        """
        self._disabled.add(server_id)

    def enable(self, server_id: str):
        """
        Enable a language server.

        Args:
            server_id: Server identifier
        """
        self._disabled.discard(server_id)

    def register(self, server: LSPServerInfo):
        """
        Register a language server.

        Args:
            server: Server information
        """
        self._servers[server.id] = server

    def get(self, server_id: str) -> Optional[LSPServerInfo]:
        """
        Get a server by ID.

        Args:
            server_id: Server identifier

        Returns:
            Server info if found and enabled, None otherwise
        """
        if server_id in self._disabled:
            return None
        return self._servers.get(server_id)

    def list(self) -> List[LSPServerInfo]:
        """
        List all registered servers.

        Returns:
            List of server information
        """
        return [
            server for server_id, server in self._servers.items()
            if server_id not in self._disabled
        ]

    def get_for_extension(self, extension: str) -> List[LSPServerInfo]:
        """
        Get servers that support a file extension.

        Args:
            extension: File extension (e.g., "py", "ts")

        Returns:
            List of matching servers
        """
        return [
            server for server in self._servers.values()
            if extension.lstrip('.') in server.extensions and server.id not in self._disabled
        ]

    def get_for_file(self, filepath: str) -> List[LSPServerInfo]:
        """
        Get servers that support a file.

        Args:
            filepath: Path to file

        Returns:
            List of matching servers
        """
        ext = Path(filepath).suffix.lstrip('.')
        return self.get_for_extension(ext)

    def remove(self, server_id: str) -> bool:
        """
        Remove a server from the registry.

        Args:
            server_id: Server identifier

        Returns:
            True if removed, False if not found
        """
        if server_id in self._servers:
            del self._servers[server_id]
            return True
        return False


# Global registry instance (will be initialized with project root)
_global_registry: Optional[LSPServerRegistry] = None


def get_global_registry(project_root: str = ".") -> LSPServerRegistry:
    """
    Get the global LSP server registry.

    Args:
        project_root: Project root directory

    Returns:
        Global LSPServerRegistry instance
    """
    global _global_registry
    if _global_registry is None or _global_registry.project_root != os.path.abspath(project_root):
        _global_registry = LSPServerRegistry(project_root)
    return _global_registry


def register_server(server: LSPServerInfo):
    """
    Register a server in the global registry.

    Args:
        server: Server information
    """
    registry = get_global_registry()
    registry.register(server)


def get_server(server_id: str, project_root: str = ".") -> Optional[LSPServerInfo]:
    """
    Get a server from the global registry.

    Args:
        server_id: Server identifier
        project_root: Project root directory

    Returns:
        Server info if found
    """
    registry = get_global_registry(project_root)
    return registry.get(server_id)


def list_servers(project_root: str = ".") -> List[LSPServerInfo]:
    """
    List all servers in the global registry.

    Args:
        project_root: Project root directory

    Returns:
        List of server information
    """
    registry = get_global_registry(project_root)
    return registry.list()
