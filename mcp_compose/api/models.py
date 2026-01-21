# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Pydantic models for API requests and responses.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

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
    servers: Dict[str, ServerStatus]
    uptime_seconds: float
    total_servers: int
    running_servers: int
    failed_servers: int


class VersionResponse(BaseModel):
    """Version information response."""
    version: str
    build_date: Optional[datetime] = None
    git_commit: Optional[str] = None
    python_version: str
    platform: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Server Models

class ServerInfo(BaseModel):
    """Server information."""
    id: str
    name: str
    status: ServerStatus
    type: str  # "stdio", "sse", "embedded"
    command: Optional[str] = None
    url: Optional[str] = None
    pid: Optional[int] = None
    uptime_seconds: Optional[float] = None
    restart_count: int = 0
    last_error: Optional[str] = None


class ServerListResponse(BaseModel):
    """Server list response."""
    servers: List[ServerInfo]
    total: int


class ServerDetailResponse(ServerInfo):
    """Detailed server information."""
    config: Dict[str, Any]
    tools: List[str]
    prompts: List[str]
    resources: List[str]
    health: HealthStatus
    metrics: Optional[Dict[str, Any]] = None


class ServerStartRequest(BaseModel):
    """Server start request."""
    timeout: Optional[int] = Field(
        default=30,
        description="Timeout in seconds for server start"
    )


class ServerStopRequest(BaseModel):
    """Server stop request."""
    timeout: Optional[int] = Field(
        default=10,
        description="Timeout in seconds for graceful shutdown"
    )
    force: bool = Field(
        default=False,
        description="Force kill if graceful shutdown fails"
    )


class ServerActionResponse(BaseModel):
    """Server action response."""
    success: bool
    message: str
    server_id: str
    status: ServerStatus


# Tool Models

class ToolParameter(BaseModel):
    """Tool parameter schema."""
    name: str
    type: str
    description: Optional[str] = None
    required: bool = False
    default: Optional[Any] = None


class ToolInfo(BaseModel):
    """Tool information."""
    id: str
    name: str
    description: Optional[str] = None
    parameters: List[ToolParameter] = []
    server_id: str
    version: Optional[str] = None


class ToolListResponse(BaseModel):
    """Tool list response."""
    tools: List[ToolInfo]
    total: int
    offset: int = 0
    limit: int = 100


class ToolInvokeRequest(BaseModel):
    """Tool invocation request."""
    arguments: Dict[str, Any] = Field(default_factory=dict)


class ToolInvokeResponse(BaseModel):
    """Tool invocation response."""
    success: bool
    result: Optional[Any] = None
    error: Optional[str] = None
    tool_id: str
    execution_time_ms: Optional[float] = None


# Prompt Models

class PromptInfo(BaseModel):
    """Prompt information."""
    id: str
    name: str
    description: Optional[str] = None
    arguments: List[str] = []
    server_id: str


class PromptListResponse(BaseModel):
    """Prompt list response."""
    prompts: List[PromptInfo]
    total: int
    offset: int = 0
    limit: int = 100


# Resource Models

class ResourceInfo(BaseModel):
    """Resource information."""
    uri: str
    name: Optional[str] = None
    description: Optional[str] = None
    mime_type: Optional[str] = None
    server_id: str


class ResourceListResponse(BaseModel):
    """Resource list response."""
    resources: List[ResourceInfo]
    total: int
    offset: int = 0
    limit: int = 100


# Configuration Models

class ConfigResponse(BaseModel):
    """Configuration response."""
    config: Dict[str, Any]


class ConfigUpdateRequest(BaseModel):
    """Configuration update request."""
    config: Dict[str, Any]


class ConfigValidateRequest(BaseModel):
    """Configuration validation request."""
    config: Dict[str, Any]


class ConfigValidateResponse(BaseModel):
    """Configuration validation response."""
    valid: bool
    errors: List[str] = []


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
    servers: List[ServerInfo]
    conflicts: List[Dict[str, Any]] = []


# Error Models

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None


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
