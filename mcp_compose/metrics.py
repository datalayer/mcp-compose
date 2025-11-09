"""
Prometheus metrics for MCP Server Composer.

Provides comprehensive metrics collection for monitoring server health,
performance, and usage patterns.
"""

from datetime import datetime
from typing import Dict, Optional

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

# Create registry
registry = CollectorRegistry()

# ============================================================================
# System Metrics
# ============================================================================

# Info about the system
composer_info = Info(
    "mcp_composer",
    "MCP Server Composer information",
    registry=registry,
)

# System uptime
composer_uptime_seconds = Gauge(
    "mcp_composer_uptime_seconds",
    "Uptime of the MCP Server Composer in seconds",
    registry=registry,
)

# ============================================================================
# Server Metrics
# ============================================================================

# Number of servers by status
servers_total = Gauge(
    "mcp_servers_total",
    "Total number of configured servers",
    registry=registry,
)

servers_running = Gauge(
    "mcp_servers_running",
    "Number of servers currently running",
    registry=registry,
)

servers_stopped = Gauge(
    "mcp_servers_stopped",
    "Number of servers currently stopped",
    registry=registry,
)

servers_failed = Gauge(
    "mcp_servers_failed",
    "Number of servers in failed state",
    registry=registry,
)

# Server lifecycle events
server_starts_total = Counter(
    "mcp_server_starts_total",
    "Total number of server start attempts",
    ["server_id", "status"],  # status: success, failed
    registry=registry,
)

server_stops_total = Counter(
    "mcp_server_stops_total",
    "Total number of server stop attempts",
    ["server_id", "status"],  # status: success, failed
    registry=registry,
)

server_restarts_total = Counter(
    "mcp_server_restarts_total",
    "Total number of server restart attempts",
    ["server_id", "reason"],  # reason: manual, crash, config_change
    registry=registry,
)

server_crashes_total = Counter(
    "mcp_server_crashes_total",
    "Total number of server crashes",
    ["server_id"],
    registry=registry,
)

# ============================================================================
# Tool Metrics
# ============================================================================

# Number of tools
tools_total = Gauge(
    "mcp_tools_total",
    "Total number of available tools across all servers",
    registry=registry,
)

tools_by_server = Gauge(
    "mcp_tools_by_server",
    "Number of tools provided by each server",
    ["server_id"],
    registry=registry,
)

# Tool invocations
tool_invocations_total = Counter(
    "mcp_tool_invocations_total",
    "Total number of tool invocations",
    ["tool_id", "status"],  # status: success, error
    registry=registry,
)

tool_invocation_duration_seconds = Histogram(
    "mcp_tool_invocation_duration_seconds",
    "Tool invocation duration in seconds",
    ["tool_id"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
    registry=registry,
)

tool_invocation_errors_total = Counter(
    "mcp_tool_invocation_errors_total",
    "Total number of tool invocation errors",
    ["tool_id", "error_type"],
    registry=registry,
)

# Tool conflicts
tool_conflicts_total = Gauge(
    "mcp_tool_conflicts_total",
    "Number of tool name conflicts detected",
    registry=registry,
)

# ============================================================================
# Prompt Metrics
# ============================================================================

prompts_total = Gauge(
    "mcp_prompts_total",
    "Total number of available prompts across all servers",
    registry=registry,
)

prompts_by_server = Gauge(
    "mcp_prompts_by_server",
    "Number of prompts provided by each server",
    ["server_id"],
    registry=registry,
)

# ============================================================================
# Resource Metrics
# ============================================================================

resources_total = Gauge(
    "mcp_resources_total",
    "Total number of available resources across all servers",
    registry=registry,
)

resources_by_server = Gauge(
    "mcp_resources_by_server",
    "Number of resources provided by each server",
    ["server_id"],
    registry=registry,
)

resource_reads_total = Counter(
    "mcp_resource_reads_total",
    "Total number of resource read operations",
    ["resource_uri", "status"],  # status: success, error
    registry=registry,
)

resource_read_duration_seconds = Histogram(
    "mcp_resource_read_duration_seconds",
    "Resource read duration in seconds",
    ["resource_uri"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=registry,
)

# ============================================================================
# API Metrics
# ============================================================================

# HTTP requests
http_requests_total = Counter(
    "mcp_http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"],
    registry=registry,
)

http_request_duration_seconds = Histogram(
    "mcp_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=registry,
)

http_request_size_bytes = Histogram(
    "mcp_http_request_size_bytes",
    "HTTP request size in bytes",
    ["method", "endpoint"],
    buckets=(10, 100, 1000, 10000, 100000, 1000000, 10000000),
    registry=registry,
)

http_response_size_bytes = Histogram(
    "mcp_http_response_size_bytes",
    "HTTP response size in bytes",
    ["method", "endpoint"],
    buckets=(10, 100, 1000, 10000, 100000, 1000000, 10000000),
    registry=registry,
)

# Authentication
auth_attempts_total = Counter(
    "mcp_auth_attempts_total",
    "Total number of authentication attempts",
    ["method", "status"],  # method: api_key, bearer, oauth2, mtls; status: success, failed
    registry=registry,
)

auth_failures_total = Counter(
    "mcp_auth_failures_total",
    "Total number of authentication failures",
    ["method", "reason"],  # reason: invalid_token, expired, missing, etc.
    registry=registry,
)

# Authorization
authz_checks_total = Counter(
    "mcp_authz_checks_total",
    "Total number of authorization checks",
    ["resource_type", "status"],  # status: allowed, denied
    registry=registry,
)

authz_denials_total = Counter(
    "mcp_authz_denials_total",
    "Total number of authorization denials",
    ["resource_type", "reason"],
    registry=registry,
)

# Rate limiting
rate_limit_exceeded_total = Counter(
    "mcp_rate_limit_exceeded_total",
    "Total number of rate limit violations",
    ["endpoint", "user_id"],
    registry=registry,
)

# ============================================================================
# Configuration Metrics
# ============================================================================

config_reloads_total = Counter(
    "mcp_config_reloads_total",
    "Total number of configuration reload attempts",
    ["status"],  # status: success, failed
    registry=registry,
)

config_validation_errors_total = Counter(
    "mcp_config_validation_errors_total",
    "Total number of configuration validation errors",
    ["error_type"],
    registry=registry,
)

# ============================================================================
# Utility Functions
# ============================================================================

class MetricsCollector:
    """Collector for MCP Server Composer metrics."""
    
    def __init__(self):
        """Initialize metrics collector."""
        self.start_time = datetime.utcnow()
        self._initialized = False
    
    def initialize(self, version: str, platform: str):
        """
        Initialize system metrics.
        
        Args:
            version: MCP Server Composer version.
            platform: Platform information.
        """
        if not self._initialized:
            composer_info.info({
                "version": version,
                "platform": platform,
            })
            self._initialized = True
    
    def update_uptime(self):
        """Update system uptime metric."""
        uptime = (datetime.utcnow() - self.start_time).total_seconds()
        composer_uptime_seconds.set(uptime)
    
    def update_server_counts(
        self,
        total: int,
        running: int,
        stopped: int,
        failed: int = 0,
    ):
        """
        Update server count metrics.
        
        Args:
            total: Total number of servers.
            running: Number of running servers.
            stopped: Number of stopped servers.
            failed: Number of failed servers.
        """
        servers_total.set(total)
        servers_running.set(running)
        servers_stopped.set(stopped)
        servers_failed.set(failed)
    
    def update_capability_counts(
        self,
        tools: int,
        prompts: int,
        resources: int,
    ):
        """
        Update capability count metrics.
        
        Args:
            tools: Total number of tools.
            prompts: Total number of prompts.
            resources: Total number of resources.
        """
        tools_total.set(tools)
        prompts_total.set(prompts)
        resources_total.set(resources)
    
    def update_per_server_tools(self, server_tools: Dict[str, int]):
        """
        Update per-server tool counts.
        
        Args:
            server_tools: Dictionary mapping server ID to tool count.
        """
        for server_id, count in server_tools.items():
            tools_by_server.labels(server_id=server_id).set(count)
    
    def update_per_server_prompts(self, server_prompts: Dict[str, int]):
        """
        Update per-server prompt counts.
        
        Args:
            server_prompts: Dictionary mapping server ID to prompt count.
        """
        for server_id, count in server_prompts.items():
            prompts_by_server.labels(server_id=server_id).set(count)
    
    def update_per_server_resources(self, server_resources: Dict[str, int]):
        """
        Update per-server resource counts.
        
        Args:
            server_resources: Dictionary mapping server ID to resource count.
        """
        for server_id, count in server_resources.items():
            resources_by_server.labels(server_id=server_id).set(count)
    
    def record_server_start(self, server_id: str, success: bool):
        """
        Record server start event.
        
        Args:
            server_id: Server identifier.
            success: Whether start was successful.
        """
        status = "success" if success else "failed"
        server_starts_total.labels(server_id=server_id, status=status).inc()
    
    def record_server_stop(self, server_id: str, success: bool):
        """
        Record server stop event.
        
        Args:
            server_id: Server identifier.
            success: Whether stop was successful.
        """
        status = "success" if success else "failed"
        server_stops_total.labels(server_id=server_id, status=status).inc()
    
    def record_server_restart(self, server_id: str, reason: str = "manual"):
        """
        Record server restart event.
        
        Args:
            server_id: Server identifier.
            reason: Reason for restart (manual, crash, config_change).
        """
        server_restarts_total.labels(server_id=server_id, reason=reason).inc()
    
    def record_server_crash(self, server_id: str):
        """
        Record server crash event.
        
        Args:
            server_id: Server identifier.
        """
        server_crashes_total.labels(server_id=server_id).inc()
    
    def record_tool_invocation(
        self,
        tool_id: str,
        duration_seconds: float,
        success: bool,
        error_type: Optional[str] = None,
    ):
        """
        Record tool invocation.
        
        Args:
            tool_id: Tool identifier.
            duration_seconds: Invocation duration in seconds.
            success: Whether invocation was successful.
            error_type: Error type if failed.
        """
        status = "success" if success else "error"
        tool_invocations_total.labels(tool_id=tool_id, status=status).inc()
        tool_invocation_duration_seconds.labels(tool_id=tool_id).observe(duration_seconds)
        
        if not success and error_type:
            tool_invocation_errors_total.labels(
                tool_id=tool_id,
                error_type=error_type,
            ).inc()
    
    def record_resource_read(
        self,
        resource_uri: str,
        duration_seconds: float,
        success: bool,
    ):
        """
        Record resource read operation.
        
        Args:
            resource_uri: Resource URI.
            duration_seconds: Read duration in seconds.
            success: Whether read was successful.
        """
        status = "success" if success else "error"
        resource_reads_total.labels(resource_uri=resource_uri, status=status).inc()
        resource_read_duration_seconds.labels(resource_uri=resource_uri).observe(duration_seconds)
    
    def record_http_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration_seconds: float,
        request_size_bytes: int = 0,
        response_size_bytes: int = 0,
    ):
        """
        Record HTTP request.
        
        Args:
            method: HTTP method.
            endpoint: Endpoint path.
            status_code: HTTP status code.
            duration_seconds: Request duration in seconds.
            request_size_bytes: Request size in bytes.
            response_size_bytes: Response size in bytes.
        """
        http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=status_code,
        ).inc()
        
        http_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint,
        ).observe(duration_seconds)
        
        if request_size_bytes > 0:
            http_request_size_bytes.labels(
                method=method,
                endpoint=endpoint,
            ).observe(request_size_bytes)
        
        if response_size_bytes > 0:
            http_response_size_bytes.labels(
                method=method,
                endpoint=endpoint,
            ).observe(response_size_bytes)
    
    def record_auth_attempt(self, method: str, success: bool, reason: Optional[str] = None):
        """
        Record authentication attempt.
        
        Args:
            method: Authentication method.
            success: Whether authentication was successful.
            reason: Failure reason if unsuccessful.
        """
        status = "success" if success else "failed"
        auth_attempts_total.labels(method=method, status=status).inc()
        
        if not success and reason:
            auth_failures_total.labels(method=method, reason=reason).inc()
    
    def record_authz_check(self, resource_type: str, allowed: bool, reason: Optional[str] = None):
        """
        Record authorization check.
        
        Args:
            resource_type: Type of resource being accessed.
            allowed: Whether access was allowed.
            reason: Denial reason if not allowed.
        """
        status = "allowed" if allowed else "denied"
        authz_checks_total.labels(resource_type=resource_type, status=status).inc()
        
        if not allowed and reason:
            authz_denials_total.labels(resource_type=resource_type, reason=reason).inc()
    
    def record_rate_limit_exceeded(self, endpoint: str, user_id: str):
        """
        Record rate limit violation.
        
        Args:
            endpoint: Endpoint that was rate limited.
            user_id: User identifier.
        """
        rate_limit_exceeded_total.labels(endpoint=endpoint, user_id=user_id).inc()
    
    def record_config_reload(self, success: bool):
        """
        Record configuration reload attempt.
        
        Args:
            success: Whether reload was successful.
        """
        status = "success" if success else "failed"
        config_reloads_total.labels(status=status).inc()
    
    def record_config_validation_error(self, error_type: str):
        """
        Record configuration validation error.
        
        Args:
            error_type: Type of validation error.
        """
        config_validation_errors_total.labels(error_type=error_type).inc()
    
    def get_metrics(self) -> bytes:
        """
        Get metrics in Prometheus format.
        
        Returns:
            Metrics in Prometheus text format.
        """
        return generate_latest(registry)
    
    def get_content_type(self) -> str:
        """
        Get metrics content type.
        
        Returns:
            Content type for Prometheus metrics.
        """
        return CONTENT_TYPE_LATEST


# Global metrics collector instance
metrics_collector = MetricsCollector()


__all__ = [
    "metrics_collector",
    "MetricsCollector",
    "registry",
]
