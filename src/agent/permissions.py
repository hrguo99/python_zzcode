"""
Permission system for agents.

This module handles permission rules and evaluation for agents.
Corresponds to the PermissionNext namespace in the TypeScript implementation.
"""

from typing import Dict, Any, List, Union, Optional
from .models import PermissionRule, PermissionAction, PermissionRuleset


class PermissionNext:
    """
    Permission management system.

    This class provides methods to create, merge, and evaluate permission rules.
    Corresponds to the PermissionNext namespace in the original TypeScript implementation.
    """

    @staticmethod
    def from_config(config: Dict[str, Any]) -> PermissionRuleset:
        """
        Create permission ruleset from configuration dictionary.

        The configuration can be:
        - A simple string action: {"edit": "allow"}
        - A dictionary of patterns: {"read": {"*.env": "ask", "*.env.example": "allow"}}
        - A mix of both

        Args:
            config: Configuration dictionary

        Returns:
            List of PermissionRule objects
        """
        rules: PermissionRuleset = []

        for permission_key, value in config.items():
            if isinstance(value, str):
                # Simple action: {"edit": "allow"}
                rules.append(PermissionRule(
                    permission=permission_key,
                    action=PermissionAction(value),
                ))
            elif isinstance(value, dict):
                # Pattern-based: {"read": {"*.env": "ask", "*": "allow"}}
                for pattern, action in value.items():
                    rules.append(PermissionRule(
                        permission=permission_key,
                        action=PermissionAction(action),
                        pattern=pattern,
                    ))

        return rules

    @staticmethod
    def merge(*rulesets: PermissionRuleset) -> PermissionRuleset:
        """
        Merge multiple permission rulesets.

        Later rules override earlier ones when they match the same permission and pattern.
        This implements a "last write wins" semantics similar to the TypeScript implementation.

        Args:
            *rulesets: Variable number of permission rulesets to merge

        Returns:
            Merged permission ruleset
        """
        merged: Dict[tuple, PermissionRule] = {}

        for ruleset in rulesets:
            for rule in ruleset:
                # Create a composite key for deduplication
                key = (rule.permission, rule.pattern or "*")
                merged[key] = rule

        return list(merged.values())

    @staticmethod
    def evaluate(
        rules: PermissionRuleset,
        permission: str,
        pattern: Optional[str] = None,
    ) -> PermissionAction:
        """
        Evaluate permission rules for a given permission and pattern.

        Evaluation follows these rules:
        1. More specific patterns match before general patterns
        2. Later rules override earlier rules for the same specificity
        3. If no rule matches, default to DENY

        Args:
            rules: Permission ruleset to evaluate
            permission: Permission being requested (e.g., "edit", "bash")
            pattern: Optional pattern to match (e.g., file path)

        Returns:
            The action to take (allow, deny, or ask)
        """
        # Find all matching rules
        matching_rules = []

        for rule in rules:
            # Check if permission matches
            permission_matches = rule.permission == permission or rule.permission == "*"

            if not permission_matches:
                continue

            # Check pattern matching
            if rule.pattern:
                if rule.pattern == "*":
                    # Wildcard pattern matches everything
                    matching_rules.append((0, rule))
                elif pattern and PermissionNext._match_pattern(rule.pattern, pattern):
                    # Calculate specificity (more specific = higher priority)
                    specificity = PermissionNext._pattern_specificity(rule.pattern)
                    matching_rules.append((specificity, rule))
            else:
                # Exact permission match without pattern
                matching_rules.append((0, rule))

        if not matching_rules:
            return PermissionAction.DENY

        # Sort by specificity (descending) and take the last matching rule
        # (last write wins for same specificity)
        matching_rules.sort(key=lambda x: x[0], reverse=True)
        max_specificity = matching_rules[0][0]

        # Get all rules with max specificity and take the last one
        best_rules = [r for s, r in matching_rules if s == max_specificity]
        return best_rules[-1].action

    @staticmethod
    def _match_pattern(pattern: str, value: str) -> bool:
        """
        Simple pattern matching.

        Supports:
        - Exact match
        - Wildcard (*) at the end: "*.txt" matches "file.txt"
        - Wildcard at the beginning: "*.env" matches ".env"

        Args:
            pattern: Pattern to match
            value: Value to check

        Returns:
            True if pattern matches
        """
        if pattern == "*":
            return True

        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return value.startswith(prefix)

        if pattern.startswith("*"):
            suffix = pattern[1:]
            return value.endswith(suffix)

        return pattern == value

    @staticmethod
    def _pattern_specificity(pattern: str) -> int:
        """
        Calculate pattern specificity for ordering.

        More specific patterns have higher values:
        - Exact match (no wildcard): 100
        - Extension wildcard (*.txt): 50
        - Full wildcard (*): 0

        Args:
            pattern: Pattern to evaluate

        Returns:
            Specificity score
        """
        if pattern == "*":
            return 0
        if "*" in pattern:
            return 50
        return 100


# Type aliases for compatibility
Ruleset = PermissionRuleset
