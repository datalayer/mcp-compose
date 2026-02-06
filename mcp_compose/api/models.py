# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Pydantic models for API requests and responses.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class HealthStatus(str, Enum):
    """Health status enum."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


class ServerStatus(str, Enum):
    """Server status enum."""

    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    CRASHED = "crashed"
    UNKNOWN = "unknown"


# Health & Version Models


class HealthResponse(BaseModel):
    """Health check response."""

    status: HealthStatus
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str


class DetailedHealthResponse(BaseModel):
    """Detailed health check response."""

    status: HealthStatus
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str
    servers: dict[str, ServerStatus]
    uptime_seconds: float
    total_servers: int
    running_servers: int
    failed_servers: int


class VersionResponse(BaseModel):
    """Version information response."""

    version: str
    build_date: datetime | None = None
    git_commit: str | None = None
    python_version: str
    platform: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Server Models


class ServerInfo(BaseModel):
    """Server information."""

    id: str
    name: str
    status: ServerStatus
    type: str = "stdio"  # "stdio", "sse", "embedded"
    command: str | None = None
    url: str | None = None
    pid: int | None = None
    uptime_seconds: float | None = None
    restart_count: int = 0
    last_error: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    transport: str | None = None
    auto_start: bool = False


class ServerListResponse(BaseModel):
    """Server list response."""

    servers: list[ServerInfo]
    total: int
    offset: int = 0
    limit: int = 100


class ServerDetailResponse(BaseModel):
    """Detailed server information."""

    server: ServerInfo
    tools_count: int = 0
    prompts_count: int = 0
    resources_count: int = 0
    uptime_seconds: float = 0.0


class ServerStartRequest(BaseModel):
    """Server start request."""

    timeout: int | None = Field(default=30, description="Timeout in seconds for server start")


class ServerStopRequest(BaseModel):
    """Server stop request."""

    timeout: int | None = Field(default=10, description="Timeout in seconds for graceful shutdown")
    force: bool = Field(default=False, description="Force kill if graceful shutdown fails")


class ServerActionResponse(BaseModel):
    """Server action response."""

    success: bool
    message: str
    server_id: str
    status: ServerStatus | None = None


# Tool Models


class ToolParameter(BaseModel):
    """Tool parameter schema."""

    name: str
    type: str
    description: str | None = None
    required: bool = False
    default: Any | None = None


class ToolInfo(BaseModel):
    """Tool information."""

    id: str
    name: str
    description: str | None = None
    parameters: list[ToolParameter] = []
    server_id: str
    version: str | None = None


class ToolListResponse(BaseModel):
    """Tool list response."""

    tools: list[ToolInfo]
    total: int
    offset: int = 0
    limit: int = 100


class ToolInvokeRequest(BaseModel):
    """Tool invocation request."""

    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolInvokeResponse(BaseModel):
    """Tool invocation response."""

    success: bool
    result: Any | None = None
    error: str | None = None
    tool_id: str
    execution_time_ms: float | None = None


# Prompt Models


class PromptInfo(BaseModel):
    """Prompt information."""

    id: str
    name: str
    description: str | None = None
    arguments: list[str] = []
    server_id: str


class PromptListResponse(BaseModel):
    """Prompt list response."""

    prompts: list[PromptInfo]
    total: int
    offset: int = 0
    limit: int = 100


# Resource Models


class ResourceInfo(BaseModel):
    """Resource information."""

    uri: str
    name: str | None = None
    description: str | None = None
    mime_type: str | None = None
    server_id: str


class ResourceListResponse(BaseModel):
    """Resource list response."""

    resources: list[ResourceInfo]
    total: int
    offset: int = 0
    limit: int = 100


# Configuration Models


class ConfigResponse(BaseModel):
    """Configuration response."""

    config: dict[str, Any]


class ConfigUpdateRequest(BaseModel):
    """Configuration update request."""

    config: dict[str, Any]


class ConfigValidateRequest(BaseModel):
    """Configuration validation request."""

    config: dict[str, Any]


class ConfigValidateResponse(BaseModel):
    """Configuration validation response."""

    valid: bool
    errors: list[str] = []


class ConfigReloadResponse(BaseModel):
    """Configuration reload response."""

    success: bool
    message: str
    reloaded_at: datetime = Field(default_factory=datetime.utcnow)


# Composition Models


class CompositionResponse(BaseModel):
    """Composition summary response."""

    total_servers: int
    total_tools: int
    total_prompts: int
    total_resources: int
    servers: list[ServerInfo]
    conflicts: list[dict[str, Any]] = []


# Error Models


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    message: str
    details: dict[str, Any] | None = None


# Pagination Models


class PaginationParams(BaseModel):
    """Pagination parameters."""

    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=1000)


__all__ = [
    # Enums
    "HealthStatus",
    "ServerStatus",
    # Health & Version
    "HealthResponse",
    "DetailedHealthResponse",
    "VersionResponse",
    # Server
    "ServerInfo",
    "ServerListResponse",
    "ServerDetailResponse",
    "ServerStartRequest",
    "ServerStopRequest",
    "ServerActionResponse",
    # Tool
    "ToolParameter",
    "ToolInfo",
    "ToolListResponse",
    "ToolInvokeRequest",
    "ToolInvokeResponse",
    # Prompt
    "PromptInfo",
    "PromptListResponse",
    # Resource
    "ResourceInfo",
    "ResourceListResponse",
    # Configuration
    "ConfigResponse",
    "ConfigUpdateRequest",
    "ConfigValidateRequest",
    "ConfigValidateResponse",
    "ConfigReloadResponse",
    # Composition
    "CompositionResponse",
    # Error
    "ErrorResponse",
    # Pagination
    "PaginationParams",
]
