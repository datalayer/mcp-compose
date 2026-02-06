# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Custom exceptions for MCP Compose.

This module defines exception classes for different types of errors
that can occur during MCP server composition and discovery.
"""

from typing import Any


class MCPComposerError(Exception):
    """Base exception for MCP Compose errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class MCPDiscoveryError(MCPComposerError):
    """Raised when MCP server discovery fails."""

    def __init__(
        self,
        message: str,
        package_name: str | None = None,
        search_paths: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.package_name = package_name
        self.search_paths = search_paths or []


class MCPImportError(MCPComposerError):
    """Raised when importing MCP server modules fails."""

    def __init__(
        self,
        message: str,
        module_name: str | None = None,
        import_error: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.module_name = module_name
        self.import_error = import_error


class MCPCompositionError(MCPComposerError):
    """Error that occurs during MCP server composition."""

    def __init__(
        self,
        message: str,
        server_name: str | None = None,
        failed_components: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.server_name = server_name
        self.failed_components = failed_components or []


class MCPToolConflictError(MCPCompositionError):
    """Raised when tool name conflicts occur during composition."""

    def __init__(
        self,
        tool_name: str,
        conflicting_servers: list[str],
        resolution_strategy: str | None = None,
    ) -> None:
        message = f"Tool name conflict: '{tool_name}' found in multiple servers"
        super().__init__(message)
        self.tool_name = tool_name
        self.conflicting_servers = conflicting_servers
        self.resolution_strategy = resolution_strategy


class MCPPromptConflictError(MCPCompositionError):
    """Raised when prompt name conflicts occur during composition."""

    def __init__(
        self,
        prompt_name: str,
        conflicting_servers: list[str],
        resolution_strategy: str | None = None,
    ) -> None:
        message = f"Prompt name conflict: '{prompt_name}' found in multiple servers"
        super().__init__(message)
        self.prompt_name = prompt_name
        self.conflicting_servers = conflicting_servers
        self.resolution_strategy = resolution_strategy


class MCPConfigurationError(MCPComposerError):
    """Raised when configuration loading or validation fails."""

    def __init__(
        self,
        message: str,
        config_path: str | None = None,
        validation_errors: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.config_path = config_path
        self.validation_errors = validation_errors or []


class ValidationError(MCPComposerError):
    """Raised when data validation fails."""

    def __init__(
        self,
        message: str,
        field_name: str | None = None,
        invalid_value: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.field_name = field_name
        self.invalid_value = invalid_value
