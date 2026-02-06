# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
MCP Compose Module.

This module provides the main functionality for composing multiple MCP servers
into a single unified server instance.
"""

import asyncio
import logging
import signal
import subprocess
from enum import Enum
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .config import MCPComposerConfig, ToolManagerConfig
from .discovery import MCPServerDiscovery, MCPServerInfo
from .exceptions import (
    MCPCompositionError,
    MCPPromptConflictError,
    MCPToolConflictError,
)
from .process_manager import ProcessManager
from .tool_manager import ToolManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module-level composer registry for signal-based graceful shutdown.
#
# Signal handlers are global per process, so we maintain a registry of all
# active MCPServerComposer instances.  A *single* module-level handler
# iterates the registry and shuts down every composer when SIGTERM or
# SIGINT is received.  Composers are registered in __init__ (so they are
# always covered, even if start() is never called) and unregistered in
# stop().  The module-level handler is installed on the first registration
# and restored to the original when the last composer unregisters.
# ---------------------------------------------------------------------------

_active_composers: set["MCPServerComposer"] = set()
_original_sigterm_handler: Any = None
_original_sigint_handler: Any = None
_signal_handlers_installed: bool = False


def _module_signal_handler(sig, frame):
    """Shut down every registered composer on SIGTERM / SIGINT.

    Uses ``asyncio.get_running_loop()`` to obtain the event loop.  This
    is the recommended API since Python 3.10 (``get_event_loop()`` is
    deprecated in non-async contexts).  If no loop is currently running
    or the loop is already closed, the handler returns early — the
    scheduled tasks would not execute anyway.

    Tasks are scheduled with ``loop.create_task()`` via
    ``call_soon_threadsafe()`` because signal handlers run synchronously
    on the main thread.  ``loop.create_task()`` is preferred over the
    deprecated ``asyncio.ensure_future()`` as it is explicitly bound to
    the target loop.
    """
    if not _active_composers:
        return
    logger.info(
        "Received signal %s, scheduling shutdown of %d composer(s)",
        sig,
        len(_active_composers),
    )
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("No running event loop, cannot schedule async shutdown")
        return
    if loop.is_closed():
        logger.warning("Event loop is closed, cannot schedule async shutdown")
        return
    for composer in list(_active_composers):
        loop.call_soon_threadsafe(loop.create_task, composer.stop())


def _install_signal_handlers() -> None:
    """Install the module-level signal handlers (idempotent).

    On Windows, ``signal.SIGTERM`` does not exist so only ``SIGINT`` is
    registered.  ``AttributeError`` is caught alongside ``OSError`` and
    ``ValueError`` to cover platforms where specific signals are
    unavailable.
    """
    global _original_sigterm_handler, _original_sigint_handler, _signal_handlers_installed
    if _signal_handlers_installed:
        return
    try:
        if hasattr(signal, "SIGTERM"):
            _original_sigterm_handler = signal.getsignal(signal.SIGTERM)
            signal.signal(signal.SIGTERM, _module_signal_handler)
        _original_sigint_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, _module_signal_handler)
        _signal_handlers_installed = True
        logger.debug(
            "Module-level signal handlers installed for %sSIGINT",
            "SIGTERM and " if hasattr(signal, "SIGTERM") else "",
        )
    except (OSError, ValueError, AttributeError):
        logger.debug(
            "Could not install signal handlers (not on main thread or unsupported platform)"
        )


def _uninstall_signal_handlers() -> None:
    """Restore original signal handlers when no composers remain.

    On Windows, ``signal.SIGTERM`` does not exist so only ``SIGINT`` is
    restored.  ``AttributeError`` is caught for platforms where specific
    signals are unavailable.
    """
    global _original_sigterm_handler, _original_sigint_handler, _signal_handlers_installed
    if not _signal_handlers_installed:
        return
    try:
        if _original_sigterm_handler is not None and hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _original_sigterm_handler)
        if _original_sigint_handler is not None:
            signal.signal(signal.SIGINT, _original_sigint_handler)
        _signal_handlers_installed = False
        _original_sigterm_handler = None
        _original_sigint_handler = None
        logger.debug("Module-level signal handlers restored to originals")
    except (OSError, ValueError, AttributeError):
        logger.debug("Could not restore original signal handlers")


def _register_composer(composer: "MCPServerComposer") -> None:
    """Add a composer to the module-level shutdown registry."""
    _active_composers.add(composer)
    _install_signal_handlers()
    logger.debug(
        "Composer %r registered for signal-based shutdown (%d active)",
        composer.composed_server_name,
        len(_active_composers),
    )


def _unregister_composer(composer: "MCPServerComposer") -> None:
    """Remove a composer from the module-level shutdown registry."""
    _active_composers.discard(composer)
    logger.debug(
        "Composer %r unregistered (%d active)",
        composer.composed_server_name,
        len(_active_composers),
    )
    if not _active_composers:
        _uninstall_signal_handlers()


class ConflictResolution(Enum):
    """Strategies for resolving naming conflicts during composition."""

    PREFIX = "prefix"  # Add server name as prefix
    SUFFIX = "suffix"  # Add server name as suffix
    IGNORE = "ignore"  # Skip conflicting items
    ERROR = "error"  # Raise error on conflicts
    OVERRIDE = "override"  # Last server wins


class MCPServerComposer:
    """Composes multiple MCP servers into a unified server."""

    def __init__(
        self,
        composed_server_name: str = "composed-mcp-server",
        conflict_resolution: ConflictResolution = ConflictResolution.PREFIX,
        discovery: MCPServerDiscovery | None = None,
        config: MCPComposerConfig | None = None,
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
        self.composed_tools: dict[str, Any] = {}
        self.composed_prompts: dict[str, Any] = {}
        self.composed_resources: dict[str, Any] = {}
        self.source_mapping: dict[str, str] = {}  # Maps component name to source server
        self.conflicts_resolved: list[dict[str, Any]] = []
        self.processes: dict[
            str, Any
        ] = {}  # Track auto-started downstream server processes (SSE, Streamable HTTP via subprocess.Popen)
        self._shutting_down: bool = False  # Guard against concurrent shutdown

        # Optional enhanced managers
        self.tool_manager: ToolManager | None = None
        self.process_manager: ProcessManager | None = None

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
                    if (
                        hasattr(server_config, "restart_policy")
                        and server_config.restart_policy.value != "never"
                    ):
                        auto_restart = True
                        break
            self.process_manager = ProcessManager(auto_restart=auto_restart)

        # Register this instance for module-level signal-based shutdown so
        # that all downstream servers are cleaned up on SIGTERM / SIGINT,
        # even if start() is never called explicitly.
        _register_composer(self)

    def compose_from_pyproject(
        self,
        pyproject_path: str | Path | None = None,
        include_servers: list[str] | None = None,
        exclude_servers: list[str] | None = None,
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
        logger.info("Starting composition of MCP servers from pyproject.toml")

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
        config: MCPComposerConfig | None = None,
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
                "No configuration provided", server_name=self.composed_server_name
            )

        logger.info("Starting composition from configuration")

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
                server_name=server_config.name,
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
                "inputSchema": {"type": "object", "properties": {}},
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

    async def _compose_tools_async(self, server_name: str, tools: dict[str, Any]) -> None:
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

    def compose_servers(self, servers: dict[str, MCPServerInfo]) -> FastMCP:
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
        discovered_servers: dict[str, MCPServerInfo],
        include_servers: list[str] | None = None,
        exclude_servers: list[str] | None = None,
    ) -> dict[str, MCPServerInfo]:
        """Filter servers based on include/exclude criteria."""
        filtered_servers = dict(discovered_servers)

        # Apply include filter
        if include_servers:
            filtered_servers = {
                name: info for name, info in filtered_servers.items() if name in include_servers
            }

        # Apply exclude filter
        if exclude_servers:
            filtered_servers = {
                name: info for name, info in filtered_servers.items() if name not in exclude_servers
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

    def _compose_tools(self, server_name: str, tools: dict[str, Any]) -> None:
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

    def _compose_prompts(self, server_name: str, prompts: dict[str, Any]) -> None:
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

    def _compose_resources(self, server_name: str, resources: dict[str, Any]) -> None:
        """Compose resources from a server."""
        # Ensure resource manager exists
        if not hasattr(self.composed_server, "_resource_manager"):
            # Create a simple resource manager if it doesn't exist
            self.composed_server._resource_manager = type(
                "ResourceManager", (), {"_resources": {}}
            )()

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
        existing_components: dict[str, Any],
    ) -> str | None:
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
            self.conflicts_resolved.append(
                {
                    "type": "override",
                    "component_type": component_type,
                    "name": name,
                    "previous_source": existing_source,
                    "new_source": server_name,
                }
            )
            return name

        elif self.conflict_resolution == ConflictResolution.PREFIX:
            resolved_name = f"{server_name}_{name}"
            # Ensure the prefixed name is also unique
            counter = 1
            while resolved_name in existing_components:
                resolved_name = f"{server_name}_{name}_{counter}"
                counter += 1

            # Record the conflict resolution
            self.conflicts_resolved.append(
                {
                    "type": "prefix",
                    "component_type": component_type,
                    "original_name": name,
                    "resolved_name": resolved_name,
                    "server_name": server_name,
                }
            )
            return resolved_name

        elif self.conflict_resolution == ConflictResolution.SUFFIX:
            resolved_name = f"{name}_{server_name}"
            # Ensure the suffixed name is also unique
            counter = 1
            while resolved_name in existing_components:
                resolved_name = f"{name}_{server_name}_{counter}"
                counter += 1

            # Record the conflict resolution
            self.conflicts_resolved.append(
                {
                    "type": "suffix",
                    "component_type": component_type,
                    "original_name": name,
                    "resolved_name": resolved_name,
                    "server_name": server_name,
                }
            )
            return resolved_name

        return name  # Fallback

    def get_composition_summary(self) -> dict[str, Any]:
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

    def list_tools(self) -> list[str]:
        """Get list of all composed tool names."""
        return list(self.composed_tools.keys())

    def get_tool(self, tool_name: str) -> dict[str, Any] | None:
        """Get tool definition by name."""
        return self.composed_tools.get(tool_name)

    def list_prompts(self) -> list[str]:
        """Get list of all composed prompt names."""
        return list(self.composed_prompts.keys())

    def get_prompt(self, prompt_name: str) -> dict[str, Any] | None:
        """Get prompt definition by name."""
        return self.composed_prompts.get(prompt_name)

    def list_resources(self) -> list[str]:
        """Get list of all composed resource names."""
        return list(self.composed_resources.keys())

    def get_resource(self, resource_name: str) -> dict[str, Any] | None:
        """Get resource definition by name."""
        return self.composed_resources.get(resource_name)

    def get_tool_source(self, tool_name: str) -> str | None:
        """Get the source server name for a specific tool."""
        return self.source_mapping.get(tool_name)

    def get_prompt_source(self, prompt_name: str) -> str | None:
        """Get the source server name for a specific prompt."""
        return self.source_mapping.get(prompt_name)

    def get_resource_source(self, resource_name: str) -> str | None:
        """Get the source server name for a specific resource."""
        return self.source_mapping.get(resource_name)

    async def start(self) -> None:
        """Start the composer and all managed processes."""
        if self.process_manager:
            await self.process_manager.start()
        logger.info(f"Composer {self.composed_server_name} started")

    async def stop(self) -> None:
        """Stop the composer, all managed processes, and all auto-started downstream servers.

        Safe to call multiple times — subsequent calls are no-ops.
        """
        if self._shutting_down:
            logger.debug(
                f"Composer {self.composed_server_name} shutdown already in progress, skipping"
            )
            return
        await self.shutdown_all_processes()
        _unregister_composer(self)
        logger.info(f"Composer {self.composed_server_name} stopped")

    async def shutdown_all_processes(self, timeout: float = 5.0) -> None:
        """Shut down all downstream server processes.

        This method is guarded by ``_shutting_down`` to prevent concurrent
        execution (e.g. an explicit ``stop()`` racing with a signal handler).
        Subsequent calls while a shutdown is in progress are no-ops.

        This ensures no ghost MCP server processes are left running when the
        composer exits. It terminates every downstream regardless of transport:

        1. **STDIO proxied servers** – managed by ``ProcessManager``, each
           running as an ``asyncio.subprocess.Process``.  Stopped via
           ``ProcessManager.stop()``.
        2. **Auto-started SSE servers** – launched as ``subprocess.Popen``
           when ``auto_start = true`` in the SSE config.  Tracked in
           ``self.processes``.
        3. **Auto-started Streamable HTTP servers** – launched as
           ``subprocess.Popen`` when ``auto_start = true`` in the
           Streamable HTTP config.  Also tracked in ``self.processes``.

        Each ``subprocess.Popen`` process is shut down via
        ``Popen.terminate()`` first.  If it does not exit within *timeout*
        seconds, ``Popen.kill()`` is used to force termination.

        .. note:: **Platform behaviour**

           On Unix/macOS, ``terminate()`` sends **SIGTERM** (which the child
           can catch for graceful cleanup) and ``kill()`` sends **SIGKILL**
           (which cannot be caught).  On Windows, both ``terminate()`` and
           ``kill()`` call **TerminateProcess**, which cannot be caught or
           ignored — the process is always forcefully terminated.

        Args:
            timeout: Seconds to wait for graceful shutdown per process before
                     escalating to ``Popen.kill()``.
        """
        if self._shutting_down:
            logger.debug("Shutdown already in progress, skipping")
            return
        self._shutting_down = True
        logger.info("Shutting down all downstream MCP server processes")

        # 1. Stop STDIO proxied servers (managed by ProcessManager as asyncio subprocesses)
        if self.process_manager:
            await self.process_manager.stop()
            logger.info("ProcessManager stopped – all STDIO proxied servers terminated")

        # 2. Kill auto-started SSE and Streamable HTTP servers concurrently
        if self.processes:
            logger.info(
                f"Terminating {len(self.processes)} auto-started downstream server(s) "
                f"(SSE / Streamable HTTP)"
            )
            kill_tasks = [
                self._kill_process(name, process, timeout)
                for name, process in self.processes.items()
            ]
            await asyncio.gather(*kill_tasks, return_exceptions=True)
            self.processes.clear()
            logger.info("All auto-started downstream servers terminated")

    async def _kill_process(self, name: str, process: Any, timeout: float = 5.0) -> None:
        """Kill a single subprocess.Popen process gracefully.

        Calls ``Popen.terminate()`` first, then waits up to *timeout*
        seconds using ``asyncio.to_thread()`` so the event loop is **not**
        blocked while the child process shuts down.  If the process does
        not exit in time, ``Popen.kill()`` is called to force termination.
        Also closes any open pipes (stdin, stdout, stderr) to avoid
        resource leaks.

        On Unix, ``terminate()`` sends SIGTERM (catchable) and ``kill()``
        sends SIGKILL (not catchable).  On Windows, both map to
        ``TerminateProcess`` — the child is always forcefully terminated
        and cannot perform graceful cleanup.

        Args:
            name: Human-readable name for the process.
            process: subprocess.Popen instance.
            timeout: Seconds to wait before escalating to ``Popen.kill()``.
        """
        if not hasattr(process, "poll"):
            logger.warning(f"Process {name} is not a subprocess.Popen instance, skipping")
            return

        pid = getattr(process, "pid", "unknown")

        if process.poll() is not None:
            rc = getattr(process, "returncode", "unknown")
            logger.debug(f"Process {name} (PID {pid}) already exited with code {rc}")
            self._close_process_pipes(name, process)
            return

        logger.info(f"Terminating process {name} (PID {pid})")
        try:
            process.terminate()
            try:
                await asyncio.to_thread(process.wait, timeout)
                logger.info(f"Process {name} (PID {pid}) terminated gracefully")
            except subprocess.TimeoutExpired:
                logger.warning(
                    f"Process {name} (PID {pid}) did not terminate gracefully, sending SIGKILL"
                )
                process.kill()
                await asyncio.to_thread(process.wait, 2.0)
                logger.info(f"Process {name} (PID {pid}) killed")
        except OSError as e:
            logger.error(f"Error killing process {name} (PID {pid}): {e}")
        except Exception as e:
            logger.error(f"Unexpected error killing process {name}: {e}")
        finally:
            self._close_process_pipes(name, process)

    @staticmethod
    def _close_process_pipes(name: str, process: Any) -> None:
        """Close stdin, stdout, and stderr pipes of a subprocess.Popen.

        Args:
            name: Human-readable name for the process (for logging).
            process: subprocess.Popen instance.
        """
        for pipe_name in ("stdin", "stdout", "stderr"):
            pipe = getattr(process, pipe_name, None)
            if pipe is not None:
                try:
                    pipe.close()
                except (OSError, ValueError):
                    # Expected: pipe already closed or invalid file descriptor.
                    logger.debug(f"Pipe {pipe_name} for process {name} already closed")
                except Exception as e:
                    # Unexpected error – log at warning to aid production diagnosis.
                    logger.warning(f"Unexpected error closing {pipe_name} for process {name}: {e}")

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

    def get_proxied_servers_info(self) -> dict[str, dict[str, Any]]:
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
