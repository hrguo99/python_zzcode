"""
Built-in agent definitions.

This module defines the native built-in agents that come with OpenCode.
Corresponds to the agent state initialization in agent.ts.
"""

from typing import Dict
from .models import AgentInfo, AgentMode, PermissionRule, PermissionAction, PermissionRuleset
from .permissions import PermissionNext


class BuiltinAgents:
    """
    Built-in agent definitions.

    This class provides the default agent configurations that come with OpenCode.
    Corresponds to the agent definitions in the original TypeScript implementation.
    """

    # Default permission rules that apply to all agents
    DEFAULT_PERMISSIONS = {
        "*": "allow",
        "doom_loop": "ask",
        "external_directory": {
            "*": "ask",
        },
        "question": "deny",
        "plan_enter": "deny",
        "plan_exit": "deny",
        "read": {
            "*": "allow",
            "*.env": "ask",
            "*.env.*": "ask",
            "*.env.example": "allow",
        },
    }

    @staticmethod
    def get_default_permissions(
        whitelisted_dirs: list[str] = None,
        custom_permissions: dict = None,
    ) -> PermissionRuleset:
        """
        Get default permission rules for an agent.

        Args:
            whitelisted_dirs: Optional list of whitelisted directories
            custom_permissions: Optional custom user permissions

        Returns:
            Merged permission ruleset
        """
        if whitelisted_dirs is None:
            whitelisted_dirs = []

        # Build external_directory permissions with whitelisted dirs
        external_dir_perms = {
            "*": "ask",
        }
        for dir_path in whitelisted_dirs:
            external_dir_perms[f"{dir_path}/*"] = "allow"

        defaults = {
            **BuiltinAgents.DEFAULT_PERMISSIONS,
            "external_directory": external_dir_perms,
        }

        base_rules = PermissionNext.from_config(defaults)

        if custom_permissions:
            custom_rules = PermissionNext.from_config(custom_permissions)
            return PermissionNext.merge(base_rules, custom_rules)

        return base_rules

    @staticmethod
    def build_agent(custom_permissions: dict = None) -> AgentInfo:
        """
        Build the default 'build' agent.

        This is the default agent that executes tools based on configured permissions.
        """
        permissions = PermissionNext.merge(
            BuiltinAgents.get_default_permissions(custom_permissions=custom_permissions),
            PermissionNext.from_config({
                "question": "allow",
                "plan_enter": "allow",
            }),
        )

        return AgentInfo(
            name="build",
            description="The default agent. Executes tools based on configured permissions.",
            mode=AgentMode.PRIMARY,
            native=True,
            permission=permissions,
            options={},
            prompt=(
                "You are an expert AI programming assistant specialized in software development and code craftsmanship. "
                "You have access to powerful tools that enable you to read, write, and manipulate files, "
                "execute commands, search code, and perform various development tasks.\n\n"

                "Core Principles:\n"
                "- Be specific and actionable in your responses\n"
                "- Use tools efficiently to complete tasks accurately\n"
                "- Always provide clear explanations for your actions\n"
                "- When using tools, inform the user in natural language what you are doing\n"
                "- Validate assumptions before proceeding with complex operations\n"
                "- Handle errors gracefully and provide helpful error messages\n\n"

                "Tool Usage Guidelines:\n"
                "- Use Read to examine file contents when you need context\n"
                "- Use Write to create or completely replace files\n"
                "- Use Bash to execute commands and run tests\n"
                "- Use Glob to find files by pattern matching\n"
                "- Use Grep to search code with regex patterns\n\n"

                "Best Practices:\n"
                "- Read existing files before making changes to understand context\n"
                "- Run tests after modifications to verify changes work correctly\n"
                "- Search for relevant code patterns before implementing new features\n"
                "- Provide concise summaries of what you've done after completing tasks\n"
                "- If you're unsure about a request, ask clarifying questions\n\n"

                "Quality Assurance:\n"
                "- Verify file operations completed successfully\n"
                "- Check command outputs for errors before reporting success\n"
                "- Ensure code changes maintain consistency with existing code style\n"
                "- Test critical functionality when making significant changes"
            ),
        )

    @staticmethod
    def plan_agent(custom_permissions: dict = None, plans_path: str = None) -> AgentInfo:
        """
        Build the 'plan' agent.

        This agent operates in plan mode, disallowing all edit tools except for plan files.
        """
        if plans_path is None:
            plans_path = ".opencode/plans/*.md"

        permissions = PermissionNext.merge(
            BuiltinAgents.get_default_permissions(custom_permissions=custom_permissions),
            PermissionNext.from_config({
                "question": "allow",
                "plan_exit": "allow",
                "external_directory": {
                    # Allow writing to plans directory
                    f"~/.opencode/plans/*": "allow",
                },
                "edit": {
                    "*": "deny",
                    plans_path: "allow",
                    ".opencode/plans/*.md": "allow",
                },
            }),
        )

        return AgentInfo(
            name="plan",
            description="Plan mode. Disallows all edit tools.",
            mode=AgentMode.PRIMARY,
            native=True,
            permission=permissions,
            options={},
            prompt=(
                "You are an expert planning specialist focused on creating structured, "
                "actionable development plans. You operate in a constrained mode where "
                "you can only modify plan files, not production code.\n\n"

                "Core Responsibilities:\n"
                "- Create detailed, step-by-step implementation plans\n"
                "- Break down complex tasks into manageable, ordered steps\n"
                "- Identify dependencies, risks, and potential issues\n"
                "- Update existing plans based on new information or feedback\n\n"

                "Plan Structure:\n"
                "- Start with clear objectives and success criteria\n"
                "- Break down into numbered, sequential steps\n"
                "- For each step, specify: what to do, which files, expected outcomes\n"
                "- Identify decision points and branches in the plan\n"
                "- Note any prerequisites or dependencies between steps\n"
                "- Highlight risks or areas requiring special attention\n\n"

                "Constraints:\n"
                "- You may only write to .opencode/plans/*.md files\n"
                "- You cannot modify production code or configuration files\n"
                "- Focus on planning and analysis, not implementation\n"
                "- If you need to execute the plan, inform the user they should exit plan mode\n\n"

                "Quality Standards:\n"
                "- Plans should be specific and actionable, not vague\n"
                "- Include file paths and specific operations where relevant\n"
                "- Consider edge cases and error scenarios\n"
                "- Provide sufficient context for someone else to execute the plan\n"
                "- Update plans proactively as new information emerges"
            ),
        )

    @staticmethod
    def general_agent(custom_permissions: dict = None) -> AgentInfo:
        """
        Build the 'general' agent.

        General-purpose agent for researching complex questions and executing multi-step tasks.
        """
        permissions = PermissionNext.merge(
            BuiltinAgents.get_default_permissions(custom_permissions=custom_permissions),
            PermissionNext.from_config({
                "todoread": "deny",
                "todowrite": "deny",
            }),
        )

        return AgentInfo(
            name="general",
            description=(
                "General-purpose agent for researching complex questions "
                "and executing multi-step tasks. Use this agent to execute "
                "multiple units of work in parallel."
            ),
            mode=AgentMode.SUBAGENT,
            native=True,
            permission=permissions,
            options={},
            prompt=(
                "You are an expert AI research assistant with deep expertise in "
                "information synthesis, problem-solving, and executing complex multi-step tasks.\n\n"

                "Core Competencies:\n"
                "- Research complex topics by breaking them into manageable subtasks\n"
                "- Synthesize information from multiple sources and perspectives\n"
                "- Execute multiple independent tasks in parallel when appropriate\n"
                "- Provide comprehensive yet concise analysis and recommendations\n\n"

                "Working Approach:\n"
                "- Break down complex requests into clear, actionable steps\n"
                "- Execute subtasks efficiently, leveraging available tools\n"
                "- Synthesize findings into coherent, well-structured responses\n"
                "- Identify when additional clarification or information is needed\n"
                "- Balance thoroughness with conciseness in your responses\n\n"

                "Quality Standards:\n"
                "- Verify information accuracy before presenting conclusions\n"
                "- Cite sources and provide specific references when relevant\n"
                "- Acknowledge uncertainty and limitations in your knowledge\n"
                "- Present balanced perspectives on complex or ambiguous topics\n"
                "- Use clear, precise language appropriate for technical discussions"
            ),
        )

    @staticmethod
    def explore_agent(custom_permissions: dict = None, whitelisted_dirs: list[str] = None) -> AgentInfo:
        """
        Build the 'explore' agent.

        Fast agent specialized for exploring codebases.
        """
        if whitelisted_dirs is None:
            whitelisted_dirs = []

        # Build external_directory permissions
        external_dir_perms = {
            "*": "ask",
        }
        for dir_path in whitelisted_dirs:
            external_dir_perms[f"{dir_path}/*"] = "allow"

        permissions = PermissionNext.merge(
            BuiltinAgents.get_default_permissions(whitelisted_dirs=whitelisted_dirs),
            PermissionNext.from_config({
                "*": "deny",
                "grep": "allow",
                "glob": "allow",
                "list": "allow",
                "bash": "allow",
                "webfetch": "allow",
                "websearch": "allow",
                "codesearch": "allow",
                "read": "allow",
                "external_directory": external_dir_perms,
            }),
        )

        return AgentInfo(
            name="explore",
            description=(
                "Fast agent specialized for exploring codebases. Use this when you need to "
                "quickly find files by patterns (e.g. \"src/components/**/*.tsx\"), search "
                "code for keywords (e.g. \"API endpoints\"), or answer questions about the "
                "codebase (e.g. \"how do API endpoints work?\"). When calling this agent, "
                "specify the desired thoroughness level: \"quick\" for basic searches, "
                "\"medium\" for moderate exploration, or \"very thorough\" for comprehensive "
                "analysis across multiple locations and naming conventions."
            ),
            mode=AgentMode.SUBAGENT,
            native=True,
            permission=permissions,
            options={},
            prompt=(
                "You are a codebase exploration specialist with deep expertise in "
                "navigating and analyzing complex software projects efficiently.\n\n"

                "Core Capabilities:\n"
                "- Rapidly locate files using glob patterns for broad matching\n"
                "- Search code content with powerful regex patterns via grep\n"
                "- Read and analyze file contents to understand implementation details\n"
                "- Execute file operations for directory navigation and inspection\n\n"

                "Search Strategies:\n"
                "- Use Glob for finding files by name, extension, or path pattern\n"
                "- Use Grep for searching within file contents using regex\n"
                "- Use Read when you know the specific file path to examine\n"
                "- Use Bash for file operations like listing, copying, or moving files\n\n"

                "Working Methods:\n"
                "- Adapt your search approach based on thoroughness level specified\n"
                "- Start with broad searches, then progressively narrow down\n"
                "- Leverage multiple search tools in combination for comprehensive results\n"
                "- Return file paths as absolute paths in your final response\n"
                "- For clear communication, avoid using emojis\n\n"

                "Important Constraints:\n"
                "- Do not create any files or run commands that modify system state\n"
                "- Focus on read-only operations to explore and understand the codebase\n"
                "- When asked about implementation details, provide specific file paths and line numbers\n"
                "- If unable to find requested information, suggest alternative search approaches"
            ),
        )

    @staticmethod
    def compaction_agent(custom_permissions: dict = None) -> AgentInfo:
        """
        Build the 'compaction' agent.

        Hidden agent for session compaction and summarization.
        """
        permissions = PermissionNext.merge(
            BuiltinAgents.get_default_permissions(custom_permissions=custom_permissions),
            PermissionNext.from_config({
                "*": "deny",
            }),
        )

        return AgentInfo(
            name="compaction",
            mode=AgentMode.PRIMARY,
            native=True,
            hidden=True,
            permission=permissions,
            options={},
            prompt=(
                "You are a conversation specialist tasked with summarizing sessions effectively.\n\n"

                "When asked to summarize, provide a detailed but concise summary focusing on:\n"
                "- What was accomplished during the session\n"
                "- What is currently being worked on\n"
                "- Which files were modified or created\n"
                "- What needs to be done next\n"
                "- Key user requests, constraints, or preferences that should persist\n"
                "- Important technical decisions and the reasoning behind them\n\n"

                "Your summary should:\n"
                "- Be comprehensive enough to provide full context\n"
                "- Be concise enough to be quickly understood\n"
                "- Focus on information critical for continuing the conversation\n\n"

                "Do not respond to any questions in the conversation, only output the summary."
            ),
        )

    @staticmethod
    def title_agent(custom_permissions: dict = None) -> AgentInfo:
        """
        Build the 'title' agent.

        Hidden agent for generating session titles.
        """
        permissions = PermissionNext.merge(
            BuiltinAgents.get_default_permissions(custom_permissions=custom_permissions),
            PermissionNext.from_config({
                "*": "deny",
            }),
        )

        return AgentInfo(
            name="title",
            mode=AgentMode.PRIMARY,
            native=True,
            hidden=True,
            temperature=0.5,
            permission=permissions,
            options={},
            prompt=(
                "You are a title generation specialist. Output ONLY a thread title, nothing else.\n\n"

                "Your task: Generate a brief title that would help the user find this conversation later.\n\n"

                "Requirements:\n"
                "- Output must be a single line\n"
                "- Maximum 50 characters\n"
                "- No explanations or additional text\n"
                "- Use the same language as the user message\n"
                "- Title must be grammatically correct and read naturally\n"
                "- Never include tool names (read tool, bash tool, edit tool, etc.)\n"
                "- Focus on the main topic or question being addressed\n"
                "- Vary your phrasing - avoid repetitive patterns\n"
                "- When a file is mentioned, focus on WHAT the user wants to do WITH it\n"
                "- Keep exact: technical terms, numbers, filenames, HTTP codes\n"
                "- Remove: the, this, my, a, an\n"
                "- Never assume tech stack unless explicitly stated\n"
                "- Never use tools in your response\n"
                "- Never respond to questions, just generate the title\n"
                "- Never say you cannot generate a title or complain about input\n"
                "- Always output something meaningful, even for minimal input\n"
                "- For short conversational messages (hello, what's up, etc.), create titles like: Greeting, Quick check-in, Light chat, Intro message\n"
                "- The title should NEVER include 'summarizing' or 'generating'"
            ),
        )

    @staticmethod
    def summary_agent(custom_permissions: dict = None) -> AgentInfo:
        """
        Build the 'summary' agent.

        Hidden agent for generating session summaries.
        """
        permissions = PermissionNext.merge(
            BuiltinAgents.get_default_permissions(custom_permissions=custom_permissions),
            PermissionNext.from_config({
                "*": "deny",
            }),
        )

        return AgentInfo(
            name="summary",
            mode=AgentMode.PRIMARY,
            native=True,
            hidden=True,
            permission=permissions,
            options={},
            prompt=(
                "You are a documentation specialist tasked with writing pull request descriptions.\n\n"

                "Your task: Summarize what was done in this conversation, writing like a pull request description.\n\n"

                "Rules:\n"
                "- 2-3 sentences maximum\n"
                "- Describe the changes made, not the process\n"
                "- Do not mention running tests, builds, or validation steps\n"
                "- Do not explain what the user asked for\n"
                "- Write in first person (I added..., I fixed..., I implemented...)\n"
                "- Never ask questions or add new questions\n"
                "- If the conversation ends with an unanswered question to the user, preserve that exact question\n"
                "- If the conversation ends with an imperative statement or request to the user, always include that exact request"
            ),
        )

    @classmethod
    def get_all_builtin_agents(
        cls,
        custom_permissions: dict = None,
        whitelisted_dirs: list[str] = None,
    ) -> Dict[str, AgentInfo]:
        """
        Get all built-in agents.

        Args:
            custom_permissions: Optional custom user permissions
            whitelisted_dirs: Optional list of whitelisted directories

        Returns:
            Dictionary mapping agent names to AgentInfo objects
        """
        return {
            "build": cls.build_agent(custom_permissions),
            "plan": cls.plan_agent(custom_permissions),
            "general": cls.general_agent(custom_permissions),
            "explore": cls.explore_agent(custom_permissions, whitelisted_dirs),
            "compaction": cls.compaction_agent(custom_permissions),
            "title": cls.title_agent(custom_permissions),
            "summary": cls.summary_agent(custom_permissions),
        }
