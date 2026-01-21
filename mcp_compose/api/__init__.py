# Copyright (c) 2023-2025 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
REST API module for MCP Compose.

This module provides a FastAPI-based REST API for managing and monitoring
the MCP Compose, including server lifecycle management, tool invocation,
configuration, and health monitoring.
"""

from .app import create_app
from .dependencies import (
    get_auth_context,
    get_authz_middleware,
    get_composer,
    get_role_manager,
    get_tool_permission_manager,
    require_auth,
    require_permission,
    require_tool_permission,
    set_authz_middleware,
    set_composer,
    set_role_manager,
    set_tool_permission_manager,
)
from .models import (
    ConfigReloadResponse,
    ConfigResponse,
    ConfigUpdateRequest,
    ConfigValidateRequest,
    ConfigValidateResponse,
    DetailedHealthResponse,
    ErrorResponse,
    HealthResponse,
    HealthStatus,
    PaginationParams,
    PromptInfo,
    PromptListResponse,
    ResourceInfo,
    ResourceListResponse,
    ServerActionResponse,
    ServerDetailResponse,
    ServerInfo,
    ServerListResponse,
    ServerStartRequest,
    ServerStatus,
    ServerStopRequest,
    ToolInfo,
    ToolInvokeRequest,
    ToolInvokeResponse,
    ToolListResponse,
    ToolParameter,
    VersionResponse,
)

__all__ = [
    # Application
    "create_app",
    # Dependencies
    "get_composer",
    "get_role_manager",
    "get_authz_middleware",
    "get_tool_permission_manager",
    "get_auth_context",
    "require_auth",
    "require_permission",
    "require_tool_permission",
    "set_composer",
    "set_role_manager",
    "set_authz_middleware",
    "set_tool_permission_manager",
    # Models - Enums
    "HealthStatus",
    "ServerStatus",
    # Models - Health & Version
    "HealthResponse",
    "DetailedHealthResponse",
    "VersionResponse",
    # Models - Servers
    "ServerInfo",
    "ServerListResponse",
    "ServerDetailResponse",
    "ServerStartRequest",
    "ServerStopRequest",
    "ServerActionResponse",
    # Models - Tools
    "ToolParameter",
    "ToolInfo",
    "ToolListResponse",
    "ToolInvokeRequest",
    "ToolInvokeResponse",
    # Models - Prompts
    "PromptInfo",
    "PromptListResponse",
    # Models - Resources
    "ResourceInfo",
    "ResourceListResponse",
    # Models - Config
    "ConfigResponse",
    "ConfigUpdateRequest",
    "ConfigValidateRequest",
    "ConfigValidateResponse",
    "ConfigReloadResponse",
    # Models - Error & Pagination
    "ErrorResponse",
    "PaginationParams",
]
