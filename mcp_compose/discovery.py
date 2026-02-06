# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
MCP Server Discovery Module.

This module provides functionality to discover MCP servers from package dependencies,
analyze their structure, and extract tool and prompt information.
"""

import importlib
import logging
import sys
from pathlib import Path
from typing import Any

try:
    import toml
except ImportError:
    raise ImportError(
        "toml package is required for parsing pyproject.toml files. "
        "Install it with: pip install toml"
    )

from .config import EmbeddedServerConfig, MCPComposerConfig
from .exceptions import MCPDiscoveryError, MCPImportError

logger = logging.getLogger(__name__)


class MCPServerInfo:
    """Information about a discovered MCP server."""

    def __init__(
        self,
        package_name: str,
        version: str,
        tools: dict[str, Any] | None = None,
        prompts: dict[str, Any] | None = None,
        resources: dict[str, Any] | None = None,
        server_instance: Any = None,
    ) -> None:
        self.package_name = package_name
        self.version = version
        self.tools = tools or {}
        self.prompts = prompts or {}
        self.resources = resources or {}
        self.server_instance = server_instance

    def __repr__(self) -> str:
        return (
            f"MCPServerInfo(package_name='{self.package_name}', version='{self.version}', "
            f"tools={len(self.tools)}, prompts={len(self.prompts)})"
        )


class MCPServerDiscovery:
    """Discovers MCP servers from package dependencies."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        """
        Initialize MCP server discovery.

        Args:
            project_root: Root directory of the project. If None, uses current directory.
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.discovered_servers: dict[str, MCPServerInfo] = {}
        self._mcp_server_patterns = [
            "mcp-server",
            "mcp_server",
            "mcpserver",
            "-mcp-",
            "_mcp_",
        ]

    def discover_from_pyproject(
        self, pyproject_path: str | Path | None = None
    ) -> dict[str, MCPServerInfo]:
        """
        Discover MCP servers from pyproject.toml dependencies.

        Args:
            pyproject_path: Path to pyproject.toml file. If None, searches in project_root.

        Returns:
            Dictionary mapping server names to MCPServerInfo objects.

        Raises:
            MCPDiscoveryError: If pyproject.toml cannot be found or parsed.
        """
        if pyproject_path is None:
            pyproject_path = self.project_root / "pyproject.toml"
        else:
            pyproject_path = Path(pyproject_path)

        if not pyproject_path.exists():
            raise MCPDiscoveryError(
                f"pyproject.toml not found at {pyproject_path}", search_paths=[str(pyproject_path)]
            )

        logger.info(f"Discovering MCP servers from {pyproject_path}")

        try:
            with open(pyproject_path, encoding="utf-8") as f:
                pyproject_data = toml.load(f)
        except Exception as e:
            raise MCPDiscoveryError(
                f"Failed to parse pyproject.toml: {e}", search_paths=[str(pyproject_path)]
            ) from e

        # Extract dependencies
        dependencies = self._extract_dependencies(pyproject_data)

        # Discover MCP servers in dependencies
        mcp_dependencies = self._filter_mcp_dependencies(dependencies)

        logger.info(f"Found {len(mcp_dependencies)} potential MCP server dependencies")

        # Analyze each potential MCP server dependency
        for dep_name in mcp_dependencies:
            try:
                server_info = self._analyze_mcp_server(dep_name)
                if server_info:
                    self.discovered_servers[dep_name] = server_info
                    logger.info(f"Successfully discovered MCP server: {dep_name}")
            except Exception as e:
                logger.warning(f"Failed to analyze potential MCP server '{dep_name}': {e}")

        return self.discovered_servers

    def discover_from_config(
        self, config: MCPComposerConfig | list[EmbeddedServerConfig]
    ) -> dict[str, MCPServerInfo]:
        """
        Discover MCP servers from configuration.

        Args:
            config: Either a full MCPComposerConfig or a list of EmbeddedServerConfig.

        Returns:
            Dictionary mapping server names to MCPServerInfo objects.

        Raises:
            MCPDiscoveryError: If server discovery or import fails.
        """
        # Extract server configs
        if isinstance(config, MCPComposerConfig):
            server_configs = config.servers.embedded.servers
        else:
            server_configs = config

        logger.info(f"Discovering {len(server_configs)} MCP servers from configuration")

        # Analyze each configured server
        for server_config in server_configs:
            if not server_config.enabled:
                logger.info(f"Skipping disabled server: {server_config.name}")
                continue

            try:
                server_info = self._analyze_mcp_server(
                    server_config.package, version=server_config.version or "latest"
                )
                if server_info:
                    # Use the configured name instead of package name
                    self.discovered_servers[server_config.name] = server_info
                    logger.info(f"Successfully discovered MCP server: {server_config.name}")
                else:
                    logger.warning(f"Failed to discover server: {server_config.name}")
            except Exception as e:
                logger.error(f"Failed to analyze MCP server '{server_config.name}': {e}")
                raise MCPDiscoveryError(
                    f"Failed to discover server '{server_config.name}': {e}",
                    package_name=server_config.package,
                ) from e

        return self.discovered_servers

    def _parse_pyproject_dependencies(self, pyproject_path: str | Path) -> set[str]:
        """Parse dependencies from pyproject.toml file."""
        pyproject_path = Path(pyproject_path)

        if not pyproject_path.exists():
            raise MCPDiscoveryError(
                f"pyproject.toml not found at {pyproject_path}", search_paths=[str(pyproject_path)]
            )

        try:
            with open(pyproject_path, encoding="utf-8") as f:
                pyproject_data = toml.load(f)
        except Exception as e:
            raise MCPDiscoveryError(
                f"Failed to parse pyproject.toml: {e}", search_paths=[str(pyproject_path)]
            ) from e

        return self._extract_dependencies(pyproject_data)

    def _is_mcp_server_package(self, package_name: str) -> bool:
        """Check if a package name indicates it might be an MCP server."""
        package_lower = package_name.lower().replace("-", "_")

        # Check if package name contains MCP server patterns
        for pattern in self._mcp_server_patterns:
            pattern_normalized = pattern.replace("-", "_")
            if pattern_normalized in package_lower:
                return True

        return False

    def _get_package_version(self, dependency_spec: str) -> str:
        """Extract version specification from dependency string."""
        dep_name = dependency_spec.strip()

        # Handle PEP 508 markers - split on semicolon first
        if ";" in dep_name:
            dep_name = dep_name.split(";")[0].strip()

        # Find version specifiers
        for separator in [">=", "<=", "==", "!=", ">", "<", "~=", "^"]:
            if separator in dep_name:
                version_part = dep_name.split(separator, 1)[1]
                # Handle multiple constraints like ">=1.0,<2.0"
                return separator + version_part.strip()

        return "latest"

    def _extract_dependencies(self, pyproject_data: dict[str, Any]) -> set[str]:
        """Extract all dependencies from pyproject.toml."""
        dependencies = set()

        # Main dependencies
        project_deps = pyproject_data.get("project", {}).get("dependencies", [])
        for dep in project_deps:
            dep_name = self._parse_dependency_name(dep)
            if dep_name:
                dependencies.add(dep_name)

        # Optional dependencies
        optional_deps = pyproject_data.get("project", {}).get("optional-dependencies", {})
        for group_deps in optional_deps.values():
            for dep in group_deps:
                dep_name = self._parse_dependency_name(dep)
                if dep_name:
                    dependencies.add(dep_name)

        return dependencies

    def _parse_dependency_name(self, dependency_spec: str) -> str | None:
        """Parse dependency name from dependency specification."""
        # Handle various dependency formats:
        # - package_name
        # - package_name>=1.0.0
        # - package_name[extra]>=1.0.0

        dep_name = dependency_spec.strip()

        # Remove version specifiers
        for separator in [">=", "<=", "==", "!=", ">", "<", "~=", "^"]:
            if separator in dep_name:
                dep_name = dep_name.split(separator)[0]
                break

        # Remove extras
        if "[" in dep_name:
            dep_name = dep_name.split("[")[0]

        # Clean up
        dep_name = dep_name.strip()

        return dep_name if dep_name else None

    def _filter_mcp_dependencies(self, dependencies: set[str]) -> list[str]:
        """Filter dependencies that might be MCP servers."""
        mcp_deps = []

        for dep in dependencies:
            dep_lower = dep.lower().replace("-", "_")

            # Check if dependency name contains MCP server patterns
            for pattern in self._mcp_server_patterns:
                pattern_normalized = pattern.replace("-", "_")
                if pattern_normalized in dep_lower:
                    mcp_deps.append(dep)
                    break

        return mcp_deps

    def _analyze_mcp_server(
        self, package_name: str, version: str = "latest"
    ) -> MCPServerInfo | None:
        """
        Analyze a package to determine if it's an MCP server and extract its components.

        Args:
            package_name: Name of the package to analyze.

        Returns:
            MCPServerInfo if the package is an MCP server, None otherwise.
        """
        logger.debug(f"Analyzing package: {package_name}")

        try:
            # Add project_root to sys.path for importing local modules
            project_root_str = str(self.project_root)
            added_to_path = False
            if project_root_str not in sys.path:
                sys.path.insert(0, project_root_str)
                added_to_path = True
                logger.debug(f"Added {project_root_str} to sys.path for local imports")

            # Try different import patterns
            import_patterns = [
                package_name,
                f"{package_name}.server",
                f"{package_name}.main",
                package_name.replace("-", "_"),
                f"{package_name.replace('-', '_')}.server",
            ]

            server_module = None
            module_path = None

            for pattern in import_patterns:
                try:
                    logger.debug(f"Trying to import: {pattern}")
                    server_module = importlib.import_module(pattern)
                    module_path = pattern
                    break
                except ImportError as ie:
                    logger.debug(f"Failed to import {pattern}: {ie}")
                    continue

            # Clean up sys.path if we added to it
            if added_to_path and project_root_str in sys.path:
                sys.path.remove(project_root_str)

            if not server_module:
                logger.debug(f"Could not import any module for package: {package_name}")
                raise MCPImportError(
                    f"Could not import package '{package_name}'",
                    module_name=package_name,
                    import_error=ImportError(f"No importable module found for {package_name}"),
                )

            # Look for MCP server instance
            server_instance = self._find_mcp_server_instance(server_module)
            if not server_instance:
                logger.debug(f"No MCP server instance found in {module_path}")
                raise MCPImportError(
                    f"No MCP server instance found in '{package_name}'",
                    module_name=package_name,
                    import_error=AttributeError(f"No app attribute found in {module_path}"),
                )

            # Extract tools, prompts, and resources
            tools = self._extract_tools(server_instance)
            prompts = self._extract_prompts(server_instance)
            resources = self._extract_resources(server_instance)

            logger.info(
                f"Discovered MCP server '{package_name}': "
                f"{len(tools)} tools, {len(prompts)} prompts, {len(resources)} resources"
            )

            return MCPServerInfo(
                package_name=package_name,
                version=version,
                tools=tools,
                prompts=prompts,
                resources=resources,
                server_instance=server_instance,
            )

        except Exception as e:
            raise MCPImportError(
                f"Failed to analyze MCP server '{package_name}'",
                module_name=package_name,
                import_error=e,
            ) from e

    def _find_mcp_server_instance(self, module: Any) -> Any | None:
        """Find MCP server instance in a module."""
        # Common variable names for MCP server instances
        server_names = ["app", "mcp", "server", "fastmcp", "mcp_server"]

        candidates = []

        for name in server_names:
            if hasattr(module, name):
                instance = getattr(module, name)
                # Check if it looks like an MCP server
                if self._is_mcp_server_instance(instance):
                    # Give preference to instances that actually have tools/prompts/resources
                    has_content = (
                        len(self._extract_tools(instance)) > 0
                        or len(self._extract_prompts(instance)) > 0
                        or len(self._extract_resources(instance)) > 0
                    )
                    candidates.append((instance, has_content, name))

        if not candidates:
            return None

        # Sort by: has_content (True first), then by name priority
        candidates.sort(key=lambda x: (not x[1], server_names.index(x[2])))
        return candidates[0][0]

    def _is_mcp_server_instance(self, instance: Any) -> bool:
        """Check if an object is an MCP server instance."""
        # Check for common MCP server attributes/methods
        mcp_indicators = [
            "_tool_manager",
            "_prompt_manager",
            "_resource_manager",
            "tools",
            "prompts",
            "list_tools",
            "call_tool",
            "list_prompts",
        ]

        indicator_count = sum(1 for indicator in mcp_indicators if hasattr(instance, indicator))

        # If the instance has multiple MCP indicators, it's likely an MCP server
        return indicator_count >= 2

    def _extract_tools(self, server_instance: Any) -> dict[str, Any]:
        """Extract tools from MCP server instance."""
        tools = {}

        # Try different patterns for accessing tools
        tool_sources = [
            lambda: getattr(getattr(server_instance, "_tool_manager", None), "_tools", {})
            if hasattr(server_instance, "_tool_manager")
            else {},
            lambda: getattr(server_instance, "tools", {}),
            lambda: getattr(server_instance, "_tools", {}),
        ]

        for source in tool_sources:
            try:
                candidate_tools = source()
                if candidate_tools and isinstance(candidate_tools, dict):
                    tools.update(candidate_tools)
                    break
            except (AttributeError, TypeError):
                continue

        return tools

    def _extract_prompts(self, server_instance: Any) -> dict[str, Any]:
        """Extract prompts from MCP server instance."""
        prompts = {}

        # Try different patterns for accessing prompts
        prompt_sources = [
            lambda: getattr(getattr(server_instance, "_prompt_manager", None), "_prompts", {})
            if hasattr(server_instance, "_prompt_manager")
            else {},
            lambda: getattr(server_instance, "prompts", {}),
            lambda: getattr(server_instance, "_prompts", {}),
        ]

        for source in prompt_sources:
            try:
                candidate_prompts = source()
                if candidate_prompts and isinstance(candidate_prompts, dict):
                    prompts.update(candidate_prompts)
                    break
            except (AttributeError, TypeError):
                continue

        return prompts

    def _extract_resources(self, server_instance: Any) -> dict[str, Any]:
        """Extract resources from MCP server instance."""
        resources = {}

        # Try different patterns for accessing resources
        resource_sources = [
            lambda: getattr(getattr(server_instance, "_resource_manager", None), "_resources", {})
            if hasattr(server_instance, "_resource_manager")
            else {},
            lambda: getattr(server_instance, "resources", {}),
            lambda: getattr(server_instance, "_resources", {}),
        ]

        for source in resource_sources:
            try:
                candidate_resources = source()
                if candidate_resources and isinstance(candidate_resources, dict):
                    resources.update(candidate_resources)
                    break
            except (AttributeError, TypeError):
                continue

        return resources

    def list_discovered_servers(self) -> list[str]:
        """Get list of discovered server names."""
        return list(self.discovered_servers.keys())

    def get_server_info(self, server_name: str) -> MCPServerInfo | None:
        """Get detailed information about a discovered server."""
        return self.discovered_servers.get(server_name)

    def get_composition_summary(self) -> dict[str, Any]:
        """Get a summary of all discovered servers for composition."""
        total_tools = 0
        total_prompts = 0
        total_resources = 0
        server_details = {}

        for name, info in self.discovered_servers.items():
            tool_count = len(info.tools)
            prompt_count = len(info.prompts)
            resource_count = len(info.resources)

            total_tools += tool_count
            total_prompts += prompt_count
            total_resources += resource_count

            server_details[name] = {
                "tools": tool_count,
                "prompts": prompt_count,
                "resources": resource_count,
                "module_path": info.module_path,
            }

        return {
            "discovered_servers": len(self.discovered_servers),
            "total_tools": total_tools,
            "total_prompts": total_prompts,
            "total_resources": total_resources,
            "servers": server_details,
        }
