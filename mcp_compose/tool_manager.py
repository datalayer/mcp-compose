# Copyright (c) 2023-2025 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Tool Manager Module.

This module provides functionality for managing tools from multiple MCP servers,
including conflict resolution, versioning, and aliasing.
"""

import fnmatch
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from .config import ConflictResolutionStrategy, ToolManagerConfig
from .exceptions import MCPToolConflictError

logger = logging.getLogger(__name__)


class ToolManager:
    """Manages tools from multiple MCP servers with conflict resolution."""

    def __init__(self, config: Optional[ToolManagerConfig] = None) -> None:
        """
        Initialize Tool Manager.

        Args:
            config: Tool manager configuration.
        """
        self.config = config or ToolManagerConfig()
        self.tools: Dict[str, Any] = {}
        self.tool_sources: Dict[str, str] = {}  # Maps tool name to source server
        self.tool_versions: Dict[str, List[Tuple[str, str]]] = {}  # tool_name -> [(version, full_name)]
        self.aliases: Dict[str, str] = dict(self.config.aliases)
        self.conflicts_resolved: List[Dict[str, Any]] = []

    def register_tools(
        self,
        server_name: str,
        tools: Dict[str, Any],
        server_version: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Register tools from a server with conflict resolution.

        Args:
            server_name: Name of the server providing the tools.
            tools: Dictionary of tool name to tool definition.
            server_version: Version of the server (for versioning support).

        Returns:
            Dictionary mapping original tool names to resolved names.

        Raises:
            MCPToolConflictError: If conflict resolution strategy is ERROR and conflicts exist.
        """
        name_mapping: Dict[str, str] = {}
        
        for original_name, tool_def in tools.items():
            # Check for conflicts
            if original_name in self.tools:
                # Conflict detected
                conflicting_server = self.tool_sources[original_name]
                resolved_name = self._resolve_conflict(
                    original_name,
                    server_name,
                    conflicting_server
                )
                
                # Check if we should skip registration (IGNORE strategy)
                strategy = self._get_resolution_strategy(original_name)
                if strategy == ConflictResolutionStrategy.IGNORE:
                    # Skip registration for IGNORE strategy
                    name_mapping[original_name] = original_name
                    # Record conflict resolution
                    self.conflicts_resolved.append({
                        "tool": original_name,
                        "servers": [conflicting_server, server_name],
                        "resolution": original_name,
                        "strategy": strategy.value
                    })
                    continue
                
                # Record conflict resolution
                self.conflicts_resolved.append({
                    "tool": original_name,
                    "servers": [conflicting_server, server_name],
                    "resolution": resolved_name,
                    "strategy": strategy.value
                })
                
                name_mapping[original_name] = resolved_name
            else:
                resolved_name = original_name
                name_mapping[original_name] = resolved_name
            
            # Handle versioning if enabled
            if self.config.versioning.enabled and server_version:
                versioned_name = self._apply_versioning(
                    resolved_name,
                    server_version
                )
                self.tools[versioned_name] = tool_def
                self.tool_sources[versioned_name] = server_name
                
                # Track versions
                if resolved_name not in self.tool_versions:
                    self.tool_versions[resolved_name] = []
                self.tool_versions[resolved_name].append((server_version, versioned_name))
                
                name_mapping[original_name] = versioned_name
            else:
                self.tools[resolved_name] = tool_def
                self.tool_sources[resolved_name] = server_name
        
        logger.info(f"Registered {len(tools)} tools from {server_name}")
        return name_mapping

    def _resolve_conflict(
        self,
        tool_name: str,
        new_server: str,
        existing_server: str
    ) -> str:
        """
        Resolve naming conflict between tools.

        Args:
            tool_name: Original tool name.
            new_server: Name of the new server providing the tool.
            existing_server: Name of the existing server with the tool.

        Returns:
            Resolved tool name.

        Raises:
            MCPToolConflictError: If strategy is ERROR.
        """
        strategy = self._get_resolution_strategy(tool_name)
        
        if strategy == ConflictResolutionStrategy.ERROR:
            raise MCPToolConflictError(
                tool_name=tool_name,
                conflicting_servers=[existing_server, new_server],
                resolution_strategy="error"
            )
        
        elif strategy == ConflictResolutionStrategy.IGNORE:
            logger.warning(
                f"Ignoring duplicate tool '{tool_name}' from {new_server} "
                f"(already exists from {existing_server})"
            )
            return tool_name  # Keep existing
        
        elif strategy == ConflictResolutionStrategy.OVERRIDE:
            logger.info(
                f"Overriding tool '{tool_name}' from {existing_server} "
                f"with version from {new_server}"
            )
            return tool_name  # Use new one
        
        elif strategy == ConflictResolutionStrategy.PREFIX:
            resolved = f"{new_server}_{tool_name}"
            logger.info(
                f"Resolving conflict for '{tool_name}' with prefix: {resolved}"
            )
            return resolved
        
        elif strategy == ConflictResolutionStrategy.SUFFIX:
            resolved = f"{tool_name}_{new_server}"
            logger.info(
                f"Resolving conflict for '{tool_name}' with suffix: {resolved}"
            )
            return resolved
        
        elif strategy == ConflictResolutionStrategy.CUSTOM:
            resolved = self._apply_custom_template(tool_name, new_server)
            logger.info(
                f"Resolving conflict for '{tool_name}' with custom template: {resolved}"
            )
            return resolved
        
        else:
            # Fallback to prefix
            return f"{new_server}_{tool_name}"

    def _get_resolution_strategy(self, tool_name: str) -> ConflictResolutionStrategy:
        """
        Get resolution strategy for a specific tool.

        Args:
            tool_name: Tool name to check.

        Returns:
            Resolution strategy to use.
        """
        # Check for per-tool overrides
        for override in self.config.tool_overrides:
            if fnmatch.fnmatch(tool_name, override.tool_pattern):
                return override.resolution
        
        # Use global strategy
        return self.config.conflict_resolution

    def _apply_custom_template(self, tool_name: str, server_name: str) -> str:
        """
        Apply custom naming template.

        Args:
            tool_name: Original tool name.
            server_name: Server name.

        Returns:
            Tool name formatted with template.
        """
        template = self.config.custom_template.template
        
        # Replace template variables
        result = template.replace("{tool_name}", tool_name)
        result = result.replace("{server_name}", server_name)
        
        return result

    def _apply_versioning(self, tool_name: str, version: str) -> str:
        """
        Apply version suffix to tool name.

        Args:
            tool_name: Tool name.
            version: Version string.

        Returns:
            Versioned tool name.
        """
        version_suffix = self.config.versioning.version_suffix_format.format(
            version=version
        )
        return f"{tool_name}{version_suffix}"

    def add_alias(self, alias: str, target: str) -> None:
        """
        Add a tool alias.

        Args:
            alias: Alias name.
            target: Target tool name.
        """
        if target not in self.tools:
            logger.warning(f"Cannot create alias '{alias}': target '{target}' does not exist")
            return
        
        self.aliases[alias] = target
        logger.info(f"Added alias: {alias} -> {target}")

    def resolve_alias(self, name: str) -> str:
        """
        Resolve a tool name or alias to the actual tool name.

        Args:
            name: Tool name or alias.

        Returns:
            Resolved tool name.
        """
        return self.aliases.get(name, name)

    def get_tool(self, name: str) -> Optional[Any]:
        """
        Get a tool by name or alias.

        Args:
            name: Tool name or alias.

        Returns:
            Tool definition or None if not found.
        """
        resolved_name = self.resolve_alias(name)
        return self.tools.get(resolved_name)

    def get_tools(self) -> Dict[str, Any]:
        """
        Get all registered tools.

        Returns:
            Dictionary of tool names to definitions.
        """
        return dict(self.tools)

    def get_tool_source(self, name: str) -> Optional[str]:
        """
        Get the source server for a tool.

        Args:
            name: Tool name.

        Returns:
            Source server name or None if not found.
        """
        resolved_name = self.resolve_alias(name)
        return self.tool_sources.get(resolved_name)

    def get_tool_versions(self, base_name: str) -> List[Tuple[str, str]]:
        """
        Get all versions of a tool.

        Args:
            base_name: Base tool name (without version suffix).

        Returns:
            List of (version, full_name) tuples.
        """
        return self.tool_versions.get(base_name, [])

    def list_tools(self, server_name: Optional[str] = None) -> List[str]:
        """
        List all tool names, optionally filtered by server.

        Args:
            server_name: Optional server name to filter by.

        Returns:
            List of tool names.
        """
        if server_name:
            return [
                name for name, source in self.tool_sources.items()
                if source == server_name
            ]
        return list(self.tools.keys())

    def list_aliases(self) -> Dict[str, str]:
        """
        List all tool aliases.

        Returns:
            Dictionary of alias to target mappings.
        """
        return dict(self.aliases)

    def get_conflicts(self) -> List[Dict[str, Any]]:
        """
        Get list of resolved conflicts.

        Returns:
            List of conflict resolution records.
        """
        return list(self.conflicts_resolved)

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the tool manager state.

        Returns:
            Summary dictionary with statistics.
        """
        return {
            "total_tools": len(self.tools),
            "total_aliases": len(self.aliases),
            "conflicts_resolved": len(self.conflicts_resolved),
            "servers": len(set(self.tool_sources.values())),
            "versioning_enabled": self.config.versioning.enabled,
            "versioned_tools": len(self.tool_versions) if self.config.versioning.enabled else 0
        }

    def clear(self) -> None:
        """Clear all registered tools and state."""
        self.tools.clear()
        self.tool_sources.clear()
        self.tool_versions.clear()
        self.aliases = dict(self.config.aliases)  # Reset to config aliases
        self.conflicts_resolved.clear()
        logger.info("Tool manager cleared")
