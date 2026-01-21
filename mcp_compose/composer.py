# Copyright (c) 2023-2025 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
MCP Compose Module.

This module provides the main functionality for composing multiple MCP servers
into a single unified server instance.
"""

import asyncio
import logging
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from mcp.server.fastmcp import FastMCP

from .discovery import MCPServerDiscovery, MCPServerInfo
from .exceptions import (
    MCPCompositionError,
    MCPPromptConflictError,
    MCPToolConflictError,
)
from .process_manager import ProcessManager
from .tool_manager import ToolManager
from .config import MCPComposerConfig, ToolManagerConfig

logger = logging.getLogger(__name__)


class ConflictResolution(Enum):
    """Strategies for resolving naming conflicts during composition."""
    
    PREFIX = "prefix"           # Add server name as prefix
    SUFFIX = "suffix"           # Add server name as suffix  
    IGNORE = "ignore"           # Skip conflicting items
    ERROR = "error"             # Raise error on conflicts
    OVERRIDE = "override"       # Last server wins


class MCPServerComposer:
    """Composes multiple MCP servers into a unified server."""

    def __init__(
        self,
        composed_server_name: str = "composed-mcp-server",
        conflict_resolution: ConflictResolution = ConflictResolution.PREFIX,
        discovery: Optional[MCPServerDiscovery] = None,
        config: Optional[MCPComposerConfig] = None,
        use_tool_manager: bool = False,
        use_process_manager: bool = False,
    ) -> None:
        """
        Initialize MCP Compose.

        Args:
            composed_server_name: Name for the composed server.
            conflict_resolution: Strategy for resolving naming conflicts.
            discovery: MCP server discovery instance. If None, creates a new one.
            config: Full composer configuration. If provided, overrides other parameters.
            use_tool_manager: Whether to use the enhanced ToolManager for conflict resolution.
            use_process_manager: Whether to use ProcessManager for proxied servers.
        """
        self.composed_server_name = composed_server_name
        self.conflict_resolution = conflict_resolution
        self.discovery = discovery or MCPServerDiscovery()
        self.config = config
        
        # Create the composed server instance
        self.composed_server = FastMCP(composed_server_name)
        
        # Track composition state
        self.composed_tools: Dict[str, Any] = {}
        self.composed_prompts: Dict[str, Any] = {}
        self.composed_resources: Dict[str, Any] = {}
        self.source_mapping: Dict[str, str] = {}  # Maps component name to source server
        self.conflicts_resolved: List[Dict[str, Any]] = []
        self.processes: Dict[str, Any] = {}  # Track auto-started processes for SSE/Streamable HTTP servers
        
        # Optional enhanced managers
        self.tool_manager: Optional[ToolManager] = None
        self.process_manager: Optional[ProcessManager] = None
        
        if use_tool_manager:
            # Initialize ToolManager from config or defaults
            tool_config = config.tool_manager if config else ToolManagerConfig()
            self.tool_manager = ToolManager(tool_config)
        
        if use_process_manager:
            # Initialize ProcessManager
            auto_restart = False
            if config and config.servers and config.servers.proxied:
                # Check if any proxied server has auto-restart enabled
                for server_config in config.servers.proxied.stdio:
                    if hasattr(server_config, 'restart_policy') and server_config.restart_policy.value != 'never':
                        auto_restart = True
                        break
            self.process_manager = ProcessManager(auto_restart=auto_restart)

    def compose_from_pyproject(
        self,
        pyproject_path: Optional[Union[str, Path]] = None,
        include_servers: Optional[List[str]] = None,
        exclude_servers: Optional[List[str]] = None,
    ) -> FastMCP:
        """
        Compose MCP servers discovered from pyproject.toml dependencies.

        Args:
            pyproject_path: Path to pyproject.toml file.
            include_servers: List of server names to include. If None, includes all discovered.
            exclude_servers: List of server names to exclude.

        Returns:
            Composed FastMCP server instance.

        Raises:
            MCPCompositionError: If composition fails.
        """
        logger.info(f"Starting composition of MCP servers from pyproject.toml")

        # Discover servers
        discovered_servers = self.discovery.discover_from_pyproject(pyproject_path)
        
        if not discovered_servers:
            logger.warning("No MCP servers discovered from dependencies")
            return self.composed_server

        # Filter servers based on include/exclude lists
        servers_to_compose = self._filter_servers(
            discovered_servers, include_servers, exclude_servers
        )

        if not servers_to_compose:
            logger.warning("No servers selected for composition after filtering")
            return self.composed_server

        logger.info(f"Composing {len(servers_to_compose)} MCP servers")

        # Compose each server
        composition_errors = []
        for server_name, server_info in servers_to_compose.items():
            try:
                self._compose_server(server_name, server_info)
                logger.info(f"Successfully composed server: {server_name}")
            except Exception as e:
                error_msg = f"Failed to compose server '{server_name}': {e}"
                logger.error(error_msg)
                composition_errors.append(error_msg)

        # Report composition results
        total_tools = len(self.composed_tools)
        total_prompts = len(self.composed_prompts)
        total_resources = len(self.composed_resources)
        
        logger.info(
            f"Composition complete: {total_tools} tools, {total_prompts} prompts, "
            f"{total_resources} resources from {len(servers_to_compose)} servers"
        )

        if self.conflicts_resolved:
            logger.info(f"Resolved {len(self.conflicts_resolved)} naming conflicts")

        if composition_errors:
            error_summary = "; ".join(composition_errors)
            raise MCPCompositionError(
                f"Composition completed with errors: {error_summary}",
                server_name=self.composed_server_name,
                failed_components=composition_errors,
            )

        return self.composed_server

    async def compose_from_config(
        self,
        config: Optional[MCPComposerConfig] = None,
    ) -> FastMCP:
        """
        Compose MCP servers from configuration.
        
        This method supports both embedded and proxied servers:
        - Embedded servers are discovered and imported directly
        - Proxied servers are started as subprocesses via ProcessManager
        
        Args:
            config: Composer configuration. Uses self.config if not provided.
        
        Returns:
            Composed FastMCP server instance.
        
        Raises:
            MCPCompositionError: If composition fails.
        """
        config = config or self.config
        if not config:
            raise MCPCompositionError(
                "No configuration provided",
                server_name=self.composed_server_name
            )
        
        logger.info(f"Starting composition from configuration")
        
        # Start process manager if needed
        if self.process_manager:
            await self.process_manager.start()
        
        composition_errors = []
        
        # Compose embedded servers
        if config.servers and config.servers.embedded and config.servers.embedded.servers:
            logger.info(f"Composing {len(config.servers.embedded.servers)} embedded servers")
            for server_config in config.servers.embedded.servers:
                if not server_config.enabled:
                    logger.info(f"Skipping disabled embedded server: {server_config.name}")
                    continue
                
                try:
                    # Discover embedded server
                    discovered = self.discovery.discover_from_config([server_config])
                    if discovered:
                        server_info = next(iter(discovered.values()))
                        await self._compose_server_async(server_config.name, server_info)
                        logger.info(f"Successfully composed embedded server: {server_config.name}")
                except Exception as e:
                    error_msg = f"Failed to compose embedded server '{server_config.name}': {e}"
                    logger.error(error_msg)
                    composition_errors.append(error_msg)
        
        # Compose proxied STDIO servers
        if config.servers and config.servers.proxied and config.servers.proxied.stdio:
            logger.info(f"Composing {len(config.servers.proxied.stdio)} proxied STDIO servers")
            for server_config in config.servers.proxied.stdio:
                try:
                    await self._compose_proxied_server(server_config)
                    logger.info(f"Successfully composed proxied server: {server_config.name}")
                except Exception as e:
                    error_msg = f"Failed to compose proxied server '{server_config.name}': {e}"
                    logger.error(error_msg)
                    composition_errors.append(error_msg)
        
        # Report composition results
        self._log_composition_summary()
        
        if composition_errors:
            error_summary = "; ".join(composition_errors)
            raise MCPCompositionError(
                f"Composition completed with errors: {error_summary}",
                server_name=self.composed_server_name,
                failed_components=composition_errors,
            )
        
        return self.composed_server
    
    async def _compose_proxied_server(self, server_config) -> None:
        """
        Compose a proxied STDIO server.
        
        Args:
            server_config: StdioProxiedServerConfig instance.
        
        Raises:
            MCPCompositionError: If process manager is not initialized.
        """
        if not self.process_manager:
            raise MCPCompositionError(
                "ProcessManager not initialized. Set use_process_manager=True",
                server_name=server_config.name
            )
        
        logger.info(f"Starting proxied server: {server_config.name}")
        
        # Start the process
        process = await self.process_manager.add_from_config(server_config, auto_start=True)
        
        # TODO: Implement MCP protocol communication over STDIO
        # For now, we'll just register placeholder tools
        # In a real implementation, we would:
        # 1. Send MCP initialization request to the process
        # 2. Receive available tools/prompts/resources
        # 3. Register them with the composed server
        
        placeholder_tools = {
            f"{server_config.name}_tool": {
                "description": f"Placeholder tool from proxied server {server_config.name}",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        }
        
        await self._compose_tools_async(server_config.name, placeholder_tools)
        
        logger.info(f"Proxied server {server_config.name} started with PID {process.pid}")
    
    async def _compose_server_async(self, server_name: str, server_info: MCPServerInfo) -> None:
        """Async version of _compose_server for embedded servers."""
        logger.debug(f"Composing embedded server: {server_name}")

        # Compose tools
        await self._compose_tools_async(server_name, server_info.tools)
        
        # Compose prompts
        self._compose_prompts(server_name, server_info.prompts)
        
        # Compose resources
        self._compose_resources(server_name, server_info.resources)
    
    async def _compose_tools_async(self, server_name: str, tools: Dict[str, Any]) -> None:
        """Async version of _compose_tools."""
        if self.tool_manager:
            # Use enhanced ToolManager
            name_mapping = self.tool_manager.register_tools(server_name, tools)
            
            # Add to composed server
            for original_name, resolved_name in name_mapping.items():
                tool_def = tools[original_name]
                self.composed_server._tool_manager._tools[resolved_name] = tool_def
                self.composed_tools[resolved_name] = tool_def
                self.source_mapping[resolved_name] = server_name
                logger.debug(f"Added tool: {resolved_name} from {server_name}")
            
            # Record conflicts from tool manager
            for conflict in self.tool_manager.conflicts_resolved:
                self.conflicts_resolved.append(conflict)
        else:
            # Use legacy conflict resolution
            self._compose_tools(server_name, tools)
    
    def _log_composition_summary(self) -> None:
        """Log composition summary."""
        total_tools = len(self.composed_tools)
        total_prompts = len(self.composed_prompts)
        total_resources = len(self.composed_resources)
        
        logger.info(
            f"Composition complete: {total_tools} tools, {total_prompts} prompts, "
            f"{total_resources} resources"
        )

        if self.conflicts_resolved:
            logger.info(f"Resolved {len(self.conflicts_resolved)} naming conflicts")
        
        if self.process_manager:
            processes = self.process_manager.list_processes()
            logger.info(f"Managing {len(processes)} proxied server processes")

    def compose_servers(self, servers: Dict[str, MCPServerInfo]) -> FastMCP:
        """
        Compose specific MCP servers.

        Args:
            servers: Dictionary mapping server names to MCPServerInfo objects.

        Returns:
            Composed FastMCP server instance.
        """
        logger.info(f"Composing {len(servers)} specified MCP servers")

        for server_name, server_info in servers.items():
            self._compose_server(server_name, server_info)

        return self.composed_server

    def _filter_servers(
        self,
        discovered_servers: Dict[str, MCPServerInfo],
        include_servers: Optional[List[str]] = None,
        exclude_servers: Optional[List[str]] = None,
    ) -> Dict[str, MCPServerInfo]:
        """Filter servers based on include/exclude criteria."""
        filtered_servers = dict(discovered_servers)

        # Apply include filter
        if include_servers:
            filtered_servers = {
                name: info
                for name, info in filtered_servers.items()
                if name in include_servers
            }

        # Apply exclude filter
        if exclude_servers:
            filtered_servers = {
                name: info
                for name, info in filtered_servers.items()
                if name not in exclude_servers
            }

        return filtered_servers

    def _compose_server(self, server_name: str, server_info: MCPServerInfo) -> None:
        """Compose a single MCP server into the unified server."""
        logger.debug(f"Composing server: {server_name}")

        # Compose tools
        self._compose_tools(server_name, server_info.tools)
        
        # Compose prompts
        self._compose_prompts(server_name, server_info.prompts)
        
        # Compose resources
        self._compose_resources(server_name, server_info.resources)

    def _compose_tools(self, server_name: str, tools: Dict[str, Any]) -> None:
        """Compose tools from a server."""
        for tool_name, tool_def in tools.items():
            resolved_name = self._resolve_name_conflict(
                "tool", tool_name, server_name, self.composed_tools
            )
            
            if resolved_name:
                # Add to composed server
                self.composed_server._tool_manager._tools[resolved_name] = tool_def
                self.composed_tools[resolved_name] = tool_def
                self.source_mapping[resolved_name] = server_name
                
                logger.debug(f"Added tool: {resolved_name} from {server_name}")

    def _compose_prompts(self, server_name: str, prompts: Dict[str, Any]) -> None:
        """Compose prompts from a server."""
        # Ensure prompt manager exists
        if not hasattr(self.composed_server, "_prompt_manager"):
            # Create a simple prompt manager if it doesn't exist
            self.composed_server._prompt_manager = type("PromptManager", (), {"_prompts": {}})()
        
        for prompt_name, prompt_def in prompts.items():
            resolved_name = self._resolve_name_conflict(
                "prompt", prompt_name, server_name, self.composed_prompts
            )
            
            if resolved_name:
                # Add to composed server
                self.composed_server._prompt_manager._prompts[resolved_name] = prompt_def
                self.composed_prompts[resolved_name] = prompt_def
                self.source_mapping[resolved_name] = server_name
                
                logger.debug(f"Added prompt: {resolved_name} from {server_name}")

    def _compose_resources(self, server_name: str, resources: Dict[str, Any]) -> None:
        """Compose resources from a server."""
        # Ensure resource manager exists
        if not hasattr(self.composed_server, "_resource_manager"):
            # Create a simple resource manager if it doesn't exist
            self.composed_server._resource_manager = type("ResourceManager", (), {"_resources": {}})()
        
        for resource_name, resource_def in resources.items():
            resolved_name = self._resolve_name_conflict(
                "resource", resource_name, server_name, self.composed_resources
            )
            
            if resolved_name:
                # Add to composed server
                self.composed_server._resource_manager._resources[resolved_name] = resource_def
                self.composed_resources[resolved_name] = resource_def
                self.source_mapping[resolved_name] = server_name
                
                logger.debug(f"Added resource: {resolved_name} from {server_name}")

    def _resolve_name_conflict(
        self,
        component_type: str,
        name: str,
        server_name: str,
        existing_components: Dict[str, Any],
    ) -> Optional[str]:
        """
        Resolve naming conflicts based on the configured strategy.

        Args:
            component_type: Type of component ("tool", "prompt", "resource").
            name: Original component name.
            server_name: Name of the server providing the component.
            existing_components: Dictionary of existing components.

        Returns:
            Resolved name to use, or None if component should be skipped.
        """
        if name not in existing_components:
            return name  # No conflict

        # Handle conflict based on resolution strategy
        if self.conflict_resolution == ConflictResolution.ERROR:
            existing_source = self.source_mapping.get(name, "unknown")
            if component_type == "tool":
                raise MCPToolConflictError(name, [existing_source, server_name])
            elif component_type == "prompt":
                raise MCPPromptConflictError(name, [existing_source, server_name])
            else:
                raise MCPCompositionError(
                    f"{component_type.title()} name conflict: '{name}' from {server_name} "
                    f"conflicts with existing {component_type} from {existing_source}"
                )

        elif self.conflict_resolution == ConflictResolution.IGNORE:
            logger.warning(
                f"Ignoring {component_type} '{name}' from {server_name} due to name conflict"
            )
            return None

        elif self.conflict_resolution == ConflictResolution.OVERRIDE:
            existing_source = self.source_mapping.get(name, "unknown")
            logger.warning(
                f"Overriding {component_type} '{name}' from {existing_source} "
                f"with version from {server_name}"
            )
            # Record the conflict resolution
            self.conflicts_resolved.append({
                "type": "override",
                "component_type": component_type,
                "name": name,
                "previous_source": existing_source,
                "new_source": server_name,
            })
            return name

        elif self.conflict_resolution == ConflictResolution.PREFIX:
            resolved_name = f"{server_name}_{name}"
            # Ensure the prefixed name is also unique
            counter = 1
            while resolved_name in existing_components:
                resolved_name = f"{server_name}_{name}_{counter}"
                counter += 1
            
            # Record the conflict resolution
            self.conflicts_resolved.append({
                "type": "prefix",
                "component_type": component_type,
                "original_name": name,
                "resolved_name": resolved_name,
                "server_name": server_name,
            })
            return resolved_name

        elif self.conflict_resolution == ConflictResolution.SUFFIX:
            resolved_name = f"{name}_{server_name}"
            # Ensure the suffixed name is also unique
            counter = 1
            while resolved_name in existing_components:
                resolved_name = f"{name}_{server_name}_{counter}"
                counter += 1
            
            # Record the conflict resolution
            self.conflicts_resolved.append({
                "type": "suffix",
                "component_type": component_type,
                "original_name": name,
                "resolved_name": resolved_name,
                "server_name": server_name,
            })
            return resolved_name

        return name  # Fallback

    def get_composition_summary(self) -> Dict[str, Any]:
        """Get a summary of the composition results."""
        return {
            "composed_server_name": self.composed_server_name,
            "conflict_resolution_strategy": self.conflict_resolution.value,
            "total_tools": len(self.composed_tools),
            "total_prompts": len(self.composed_prompts),
            "total_resources": len(self.composed_resources),
            "source_servers": len(set(self.source_mapping.values())),
            "conflicts_resolved": len(self.conflicts_resolved),
            "conflict_details": self.conflicts_resolved,
            "component_sources": dict(self.source_mapping),
        }

    def list_tools(self) -> List[str]:
        """Get list of all composed tool names."""
        return list(self.composed_tools.keys())

    def get_tool(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get tool definition by name."""
        return self.composed_tools.get(tool_name)

    def list_prompts(self) -> List[str]:
        """Get list of all composed prompt names."""
        return list(self.composed_prompts.keys())

    def get_prompt(self, prompt_name: str) -> Optional[Dict[str, Any]]:
        """Get prompt definition by name."""
        return self.composed_prompts.get(prompt_name)

    def list_resources(self) -> List[str]:
        """Get list of all composed resource names."""
        return list(self.composed_resources.keys())

    def get_resource(self, resource_name: str) -> Optional[Dict[str, Any]]:
        """Get resource definition by name."""
        return self.composed_resources.get(resource_name)

    def get_tool_source(self, tool_name: str) -> Optional[str]:
        """Get the source server name for a specific tool."""
        return self.source_mapping.get(tool_name)

    def get_prompt_source(self, prompt_name: str) -> Optional[str]:
        """Get the source server name for a specific prompt."""
        return self.source_mapping.get(prompt_name)

    def get_resource_source(self, resource_name: str) -> Optional[str]:
        """Get the source server name for a specific resource."""
        return self.source_mapping.get(resource_name)
    
    async def start(self) -> None:
        """Start the composer and all managed processes."""
        if self.process_manager:
            await self.process_manager.start()
        logger.info(f"Composer {self.composed_server_name} started")
    
    async def stop(self) -> None:
        """Stop the composer and all managed processes."""
        if self.process_manager:
            await self.process_manager.stop()
        logger.info(f"Composer {self.composed_server_name} stopped")
    
    async def restart_proxied_server(self, server_name: str) -> None:
        """
        Restart a specific proxied server.
        
        Args:
            server_name: Name of the proxied server to restart.
        
        Raises:
            ValueError: If process manager is not initialized or server not found.
        """
        if not self.process_manager:
            raise ValueError("ProcessManager not initialized")
        
        await self.process_manager.restart_process(server_name)
        logger.info(f"Restarted proxied server: {server_name}")
    
    def get_proxied_servers_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about all proxied servers.
        
        Returns:
            Dictionary mapping server names to their process info.
        """
        if not self.process_manager:
            return {}
        
        return self.process_manager.get_all_process_info()
    
    async def __aenter__(self):
        """Context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.stop()

