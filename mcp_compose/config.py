"""
Configuration models for MCP Compose.

This module defines the configuration schema using Pydantic models.
"""

import os
import re
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator


class ConflictResolutionStrategy(str, Enum):
    """Strategies for resolving naming conflicts."""
    PREFIX = "prefix"
    SUFFIX = "suffix"
    IGNORE = "ignore"
    ERROR = "error"
    OVERRIDE = "override"
    CUSTOM = "custom"


class RestartPolicy(str, Enum):
    """Restart policies for proxied servers."""
    NEVER = "never"
    ON_FAILURE = "on-failure"
    ALWAYS = "always"


class HealthCheckMethod(str, Enum):
    """Health check methods."""
    TOOL = "tool"
    PING = "ping"
    CUSTOM = "custom"


class AuthProvider(str, Enum):
    """Authentication providers."""
    API_KEY = "api_key"
    JWT = "jwt"
    OAUTH2 = "oauth2"
    MTLS = "mtls"
    ANACONDA = "anaconda"


class AuthzModel(str, Enum):
    """Authorization models."""
    RBAC = "rbac"


class ProxyMode(str, Enum):
    """Proxy modes for SSE servers."""
    PROXY = "proxy"
    TRANSLATOR = "translator"


# ============================================================================
# Composer Configuration
# ============================================================================

class ComposerConfig(BaseModel):
    """Main composer configuration."""
    name: str = Field(default="composed-mcp-server", description="Name of the composed server")
    conflict_resolution: ConflictResolutionStrategy = Field(
        default=ConflictResolutionStrategy.PREFIX,
        description="Default conflict resolution strategy"
    )
    log_level: str = Field(default="INFO", description="Logging level")
    port: int = Field(default=8080, description="Port for HTTP/SSE transport and REST API")


# ============================================================================
# Transport Configuration
# ============================================================================

class TransportConfig(BaseModel):
    """Transport layer configuration."""
    stdio_enabled: bool = Field(default=True, description="Enable STDIO transport")
    sse_enabled: bool = Field(default=True, description="Enable SSE transport")
    sse_path: str = Field(default="/sse", description="SSE endpoint path")
    sse_cors_enabled: bool = Field(default=True, description="Enable CORS for SSE")


# ============================================================================
# Authentication Configuration
# ============================================================================

class ApiKeyAuthConfig(BaseModel):
    """API Key authentication configuration."""
    header_name: str = Field(default="X-API-Key", description="HTTP header name for API key")
    keys: List[str] = Field(default_factory=list, description="List of valid API keys")


class JwtAuthConfig(BaseModel):
    """JWT authentication configuration."""
    secret: str = Field(..., description="JWT secret key")
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    issuer: Optional[str] = Field(default=None, description="JWT issuer")
    audience: Optional[str] = Field(default=None, description="JWT audience")


class OAuth2AuthConfig(BaseModel):
    """OAuth2/OIDC authentication configuration."""
    provider: str = Field(default="auth0", description="OAuth2 provider")
    client_id: str = Field(..., description="OAuth2 client ID")
    client_secret: str = Field(..., description="OAuth2 client secret")
    discovery_url: str = Field(..., description="OAuth2 discovery URL")


class MtlsAuthConfig(BaseModel):
    """Mutual TLS authentication configuration."""
    ca_cert: str = Field(..., description="CA certificate path")
    client_cert: str = Field(..., description="Client certificate path")
    client_key: str = Field(..., description="Client key path")


class AnacondaAuthConfig(BaseModel):
    """Anaconda authentication configuration."""
    domain: str = Field(default="anaconda.com", description="Anaconda domain")


class AuthenticationConfig(BaseModel):
    """Authentication configuration."""
    enabled: bool = Field(default=False, description="Enable authentication")
    providers: List[AuthProvider] = Field(default_factory=lambda: [AuthProvider.API_KEY])
    default_provider: AuthProvider = Field(default=AuthProvider.API_KEY)
    api_key: Optional[ApiKeyAuthConfig] = Field(default=None)
    jwt: Optional[JwtAuthConfig] = Field(default=None)
    oauth2: Optional[OAuth2AuthConfig] = Field(default=None)
    mtls: Optional[MtlsAuthConfig] = Field(default=None)
    anaconda: Optional[AnacondaAuthConfig] = Field(default=None)


# ============================================================================
# Authorization Configuration
# ============================================================================

class RoleConfig(BaseModel):
    """Role configuration."""
    name: str = Field(..., description="Role name")
    permissions: List[str] = Field(default_factory=list, description="List of permissions")


class RateLimitingConfig(BaseModel):
    """Rate limiting configuration."""
    enabled: bool = Field(default=False, description="Enable rate limiting")
    default_limit: int = Field(default=100, description="Default requests per minute")
    per_role_limits: Dict[str, int] = Field(default_factory=dict, description="Per-role rate limits")


class AuthorizationConfig(BaseModel):
    """Authorization configuration."""
    enabled: bool = Field(default=False, description="Enable authorization")
    model: AuthzModel = Field(default=AuthzModel.RBAC, description="Authorization model")
    roles: List[RoleConfig] = Field(default_factory=list, description="Role definitions")
    tools: Dict[str, List[str]] = Field(default_factory=dict, description="Tool-level permissions")
    rate_limiting: RateLimitingConfig = Field(default_factory=RateLimitingConfig)


# ============================================================================
# Server Configuration
# ============================================================================

class EmbeddedServerConfig(BaseModel):
    """Configuration for an embedded MCP server."""
    name: str = Field(..., description="Server name")
    package: str = Field(..., description="Python package name")
    enabled: bool = Field(default=True, description="Enable this server")
    version: Optional[str] = Field(default=None, description="Version constraint")
    tool_mappings: Dict[str, str] = Field(default_factory=dict, description="Tool name mappings")


class ResourceLimits(BaseModel):
    """Resource limits for proxied servers."""
    max_memory_mb: Optional[int] = Field(default=None, description="Maximum memory in MB")
    max_cpu_percent: Optional[int] = Field(default=None, description="Maximum CPU percentage")


class StdioProxiedServerConfig(BaseModel):
    """Configuration for a STDIO proxied MCP server."""
    name: str = Field(..., description="Server name")
    command: List[str] = Field(..., description="Command to start the server")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    working_dir: Optional[str] = Field(default=None, description="Working directory")
    restart_policy: RestartPolicy = Field(default=RestartPolicy.ON_FAILURE)
    max_restarts: int = Field(default=3, description="Maximum restart attempts")
    restart_delay: int = Field(default=5, description="Delay between restarts in seconds")
    health_check_enabled: bool = Field(default=False, description="Enable health checks")
    health_check_interval: int = Field(default=30, description="Health check interval in seconds")
    health_check_timeout: int = Field(default=5, description="Health check timeout in seconds")
    health_check_method: HealthCheckMethod = Field(default=HealthCheckMethod.TOOL)
    health_check_tool: Optional[str] = Field(default=None, description="Tool to invoke for health check")
    resource_limits: Optional[ResourceLimits] = Field(default=None)
    log_stdout: bool = Field(default=True, description="Log stdout")
    log_stderr: bool = Field(default=True, description="Log stderr")
    log_file: Optional[str] = Field(default=None, description="Log file path")


class SseProxiedServerConfig(BaseModel):
    """Configuration for an SSE proxied MCP server."""
    name: str = Field(..., description="Server name")
    url: str = Field(..., description="SSE endpoint URL")
    auth_token: Optional[str] = Field(default=None, description="Authentication token")
    auth_type: str = Field(default="bearer", description="Authentication type")
    timeout: int = Field(default=30, description="Request timeout in seconds")
    retry_interval: int = Field(default=5, description="Retry interval in seconds")
    keep_alive: bool = Field(default=True, description="Keep connection alive")
    reconnect_on_failure: bool = Field(default=True, description="Reconnect on failure")
    max_reconnect_attempts: int = Field(default=10, description="Maximum reconnection attempts")
    health_check_enabled: bool = Field(default=False, description="Enable health checks")
    health_check_interval: int = Field(default=60, description="Health check interval in seconds")
    health_check_endpoint: Optional[str] = Field(default=None, description="Health check endpoint")
    mode: ProxyMode = Field(default=ProxyMode.PROXY, description="Proxy mode")


class EmbeddedServersConfig(BaseModel):
    """Configuration for embedded servers."""
    servers: List[EmbeddedServerConfig] = Field(default_factory=list, description="List of embedded servers")


class ProxiedServersConfig(BaseModel):
    """Configuration for proxied servers."""
    stdio: List[StdioProxiedServerConfig] = Field(default_factory=list, description="STDIO proxied servers")
    sse: List[SseProxiedServerConfig] = Field(default_factory=list, description="SSE proxied servers")


class ServersConfig(BaseModel):
    """Servers configuration."""
    embedded: EmbeddedServersConfig = Field(default_factory=EmbeddedServersConfig)
    proxied: ProxiedServersConfig = Field(default_factory=ProxiedServersConfig)


# ============================================================================
# Tool Manager Configuration
# ============================================================================

class ToolOverrideConfig(BaseModel):
    """Per-tool conflict resolution override."""
    tool_pattern: str = Field(..., description="Tool name pattern (supports wildcards)")
    resolution: ConflictResolutionStrategy = Field(..., description="Resolution strategy")


class CustomTemplateConfig(BaseModel):
    """Custom naming template configuration."""
    template: str = Field(
        default="{server_name}_{tool_name}",
        description="Template string for tool naming"
    )


class VersioningConfig(BaseModel):
    """Tool versioning configuration."""
    enabled: bool = Field(default=False, description="Enable tool versioning")
    allow_multiple_versions: bool = Field(default=False, description="Allow multiple versions")
    version_suffix_format: str = Field(default="_v{version}", description="Version suffix format")


class ToolManagerConfig(BaseModel):
    """Tool manager configuration."""
    conflict_resolution: ConflictResolutionStrategy = Field(
        default=ConflictResolutionStrategy.PREFIX,
        description="Global conflict resolution strategy"
    )
    tool_overrides: List[ToolOverrideConfig] = Field(default_factory=list)
    custom_template: CustomTemplateConfig = Field(default_factory=CustomTemplateConfig)
    aliases: Dict[str, str] = Field(default_factory=dict, description="Tool aliases")
    versioning: VersioningConfig = Field(default_factory=VersioningConfig)


# ============================================================================
# API Configuration
# ============================================================================

class ApiConfig(BaseModel):
    """REST API configuration."""
    enabled: bool = Field(default=True, description="Enable REST API")
    path_prefix: str = Field(default="/api/v1", description="API path prefix")
    host: str = Field(default="0.0.0.0", description="API host")
    port: int = Field(default=8080, description="API port")
    cors_enabled: bool = Field(default=True, description="Enable CORS")
    cors_origins: List[str] = Field(default_factory=list, description="CORS allowed origins")
    cors_methods: List[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE"],
        description="CORS allowed methods"
    )
    docs_enabled: bool = Field(default=True, description="Enable API documentation")
    docs_path: str = Field(default="/docs", description="API documentation path")
    openapi_path: str = Field(default="/openapi.json", description="OpenAPI specification path")


# ============================================================================
# UI Configuration
# ============================================================================

class UiConfig(BaseModel):
    """Web UI configuration."""
    enabled: bool = Field(default=True, description="Enable Web UI")
    framework: str = Field(default="react", description="UI framework")
    mode: str = Field(default="embedded", description="UI mode (embedded or separate)")
    path: str = Field(default="/ui", description="UI path")
    static_dir: Optional[str] = Field(default=None, description="Static files directory")
    features: List[str] = Field(
        default_factory=lambda: [
            "server_management",
            "tool_testing",
            "logs_viewing",
            "metrics_dashboard",
            "configuration_editor"
        ],
        description="Enabled features"
    )


# ============================================================================
# Monitoring Configuration
# ============================================================================

class MetricsConfig(BaseModel):
    """Metrics configuration."""
    enabled: bool = Field(default=True, description="Enable metrics collection")
    provider: str = Field(default="prometheus", description="Metrics provider")
    endpoint: str = Field(default="/metrics", description="Metrics endpoint")
    collection_interval: int = Field(default=15, description="Collection interval in seconds")
    collect: List[str] = Field(
        default_factory=lambda: [
            "tool_invocation_count",
            "tool_invocation_duration",
            "tool_error_rate",
            "server_health_status",
            "process_cpu_usage",
            "process_memory_usage",
            "request_rate",
            "response_time"
        ],
        description="Metrics to collect"
    )


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = Field(default="INFO", description="Log level")
    format: str = Field(default="json", description="Log format (json or text)")
    output: str = Field(default="stdout", description="Log output (stdout, file, or both)")
    log_file: Optional[str] = Field(default=None, description="Log file path")
    rotation: str = Field(default="daily", description="Log rotation (daily or size)")
    max_size_mb: int = Field(default=100, description="Maximum log file size in MB")
    max_files: int = Field(default=7, description="Maximum number of log files")
    aggregate_managed_logs: bool = Field(default=True, description="Aggregate logs from managed processes")


class TracingConfig(BaseModel):
    """Distributed tracing configuration."""
    enabled: bool = Field(default=False, description="Enable distributed tracing")
    provider: str = Field(default="opentelemetry", description="Tracing provider")
    endpoint: str = Field(default="http://localhost:4317", description="Tracing endpoint")
    sample_rate: float = Field(default=1.0, ge=0.0, le=1.0, description="Sampling rate")


class HealthConfig(BaseModel):
    """Health check configuration."""
    endpoint: str = Field(default="/health", description="Health check endpoint")
    detailed_endpoint: str = Field(default="/health/detailed", description="Detailed health check endpoint")


class MonitoringConfig(BaseModel):
    """Monitoring and observability configuration."""
    enabled: bool = Field(default=True, description="Enable monitoring")
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    tracing: TracingConfig = Field(default_factory=TracingConfig)
    health: HealthConfig = Field(default_factory=HealthConfig)


# ============================================================================
# Root Configuration
# ============================================================================

class MCPComposerConfig(BaseModel):
    """Root configuration for MCP Compose."""
    
    composer: ComposerConfig = Field(default_factory=ComposerConfig)
    transport: TransportConfig = Field(default_factory=TransportConfig)
    authentication: AuthenticationConfig = Field(default_factory=AuthenticationConfig)
    authorization: AuthorizationConfig = Field(default_factory=AuthorizationConfig)
    servers: ServersConfig = Field(default_factory=ServersConfig)
    tool_manager: ToolManagerConfig = Field(default_factory=ToolManagerConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    ui: UiConfig = Field(default_factory=UiConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)

    @model_validator(mode='after')
    def validate_config(self) -> 'MCPComposerConfig':
        """Validate configuration consistency."""
        # Validate authentication provider configurations
        if self.authentication.enabled:
            for provider in self.authentication.providers:
                if provider == AuthProvider.API_KEY and not self.authentication.api_key:
                    raise ValueError("API Key authentication enabled but api_key config missing")
                elif provider == AuthProvider.JWT and not self.authentication.jwt:
                    raise ValueError("JWT authentication enabled but jwt config missing")
                elif provider == AuthProvider.OAUTH2 and not self.authentication.oauth2:
                    raise ValueError("OAuth2 authentication enabled but oauth2 config missing")
                elif provider == AuthProvider.MTLS and not self.authentication.mtls:
                    raise ValueError("mTLS authentication enabled but mtls config missing")
                elif provider == AuthProvider.ANACONDA and not self.authentication.anaconda:
                    raise ValueError("Anaconda authentication enabled but anaconda config missing")
        
        # Validate health check configurations
        for stdio_server in self.servers.proxied.stdio:
            if stdio_server.health_check_enabled:
                if stdio_server.health_check_method == HealthCheckMethod.TOOL and not stdio_server.health_check_tool:
                    raise ValueError(f"Server {stdio_server.name}: health_check_method is 'tool' but health_check_tool not specified")
        
        return self

    def substitute_env_vars(self) -> 'MCPComposerConfig':
        """Substitute environment variables in configuration values."""
        self._substitute_env_recursive(self.model_dump())
        return self
    
    def _substitute_env_recursive(self, obj: Any) -> Any:
        """Recursively substitute environment variables."""
        if isinstance(obj, dict):
            return {k: self._substitute_env_recursive(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._substitute_env_recursive(item) for item in obj]
        elif isinstance(obj, str):
            return self._substitute_env_var(obj)
        else:
            return obj
    
    def _substitute_env_var(self, value: str) -> str:
        """Substitute environment variable in a string value."""
        # Match ${VAR_NAME} or $VAR_NAME patterns
        pattern = r'\$\{([^}]+)\}|\$([A-Z_][A-Z0-9_]*)'
        
        def replace_match(match: re.Match) -> str:
            var_name = match.group(1) or match.group(2)
            env_value = os.environ.get(var_name)
            if env_value is None:
                # Keep original if not found
                return match.group(0)
            return env_value
        
        return re.sub(pattern, replace_match, value)
