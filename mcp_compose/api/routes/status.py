"""
Status and composition endpoints.

Provides endpoints for retrieving system status, composition details,
and aggregated metrics.
"""

from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Response

from ..dependencies import get_composer, get_config, require_auth
from ..models import (
    CompositionResponse,
    DetailedHealthResponse,
    HealthStatus,
    ServerInfo,
    ServerStatus,
)
from ...auth import AuthContext
from ...composer import MCPServerComposer
from ...config import MCPComposerConfig
from ...metrics import metrics_collector

router = APIRouter(tags=["status"])


@router.get("/status")
async def get_status(
    composer: MCPServerComposer = Depends(get_composer),
    config: MCPComposerConfig = Depends(get_config),
    auth: AuthContext = Depends(require_auth),
) -> Dict[str, Any]:
    """
    Get composition status.
    
    Returns the current status of the MCP Compose including
    information about all servers, tools, prompts, and resources.
    
    Args:
        composer: MCPServerComposer instance.
        config: MCPComposerConfig instance.
        auth: Authentication context.
    
    Returns:
        Dictionary with composition status information.
    """
    # Count servers by status
    total_servers = len(config.servers)
    running_servers = len(composer.discovered_servers)
    stopped_servers = total_servers - running_servers
    
    # Count capabilities
    total_tools = len(composer.list_tools())
    total_prompts = len(composer.list_prompts())
    total_resources = len(composer.list_resources())
    
    # Get server statuses
    server_statuses = {}
    for server_id in config.servers.keys():
        if server_id in composer.discovered_servers:
            server_statuses[server_id] = ServerStatus.RUNNING
        else:
            server_statuses[server_id] = ServerStatus.STOPPED
    
    return {
        "status": "healthy" if running_servers > 0 else "degraded",
        "timestamp": datetime.utcnow(),
        "servers": {
            "total": total_servers,
            "running": running_servers,
            "stopped": stopped_servers,
            "statuses": server_statuses,
        },
        "capabilities": {
            "tools": total_tools,
            "prompts": total_prompts,
            "resources": total_resources,
        },
        "uptime_seconds": getattr(composer, 'uptime_seconds', 0.0),
    }


@router.get("/composition", response_model=CompositionResponse)
async def get_composition(
    composer: MCPServerComposer = Depends(get_composer),
    config: MCPComposerConfig = Depends(get_config),
    auth: AuthContext = Depends(require_auth),
) -> CompositionResponse:
    """
    Get detailed composition information.
    
    Returns detailed information about the current composition including
    all servers, their capabilities, and any conflicts.
    
    Args:
        composer: MCPServerComposer instance.
        config: MCPComposerConfig instance.
        auth: Authentication context.
    
    Returns:
        CompositionResponse with detailed composition information.
    """
    # Get all servers
    servers: List[ServerInfo] = []
    for server_id, server_config in config.servers.items():
        # Determine status
        if server_id in composer.discovered_servers:
            server_status = ServerStatus.RUNNING
        else:
            server_status = ServerStatus.STOPPED
        
        # Get server type
        transport = getattr(server_config.transport, 'value', 'stdio') if hasattr(server_config, 'transport') else 'stdio'
        
        # Create server info
        server_info = ServerInfo(
            id=server_id,
            name=server_config.name,
            status=server_status,
            type=transport,
            command=getattr(server_config, 'command', None),
            url=getattr(server_config, 'url', None),
            pid=None,  # TODO: Get from process manager
            uptime_seconds=None,
            restart_count=0,
            last_error=None,
        )
        servers.append(server_info)
    
    # Count capabilities
    total_tools = len(composer.list_tools())
    total_prompts = len(composer.list_prompts())
    total_resources = len(composer.list_resources())
    
    # Detect conflicts (tool name conflicts across servers)
    conflicts = []
    tool_names: Dict[str, List[str]] = {}
    for tool_id in composer.list_tools():
        parts = tool_id.split(".", 1)
        if len(parts) == 2:
            server_id, tool_name = parts
            if tool_name not in tool_names:
                tool_names[tool_name] = []
            tool_names[tool_name].append(server_id)
    
    # Find conflicts
    for tool_name, server_ids in tool_names.items():
        if len(server_ids) > 1:
            conflicts.append({
                "type": "tool",
                "name": tool_name,
                "servers": server_ids,
                "message": f"Tool '{tool_name}' defined in multiple servers: {', '.join(server_ids)}",
            })
    
    return CompositionResponse(
        total_servers=len(servers),
        total_tools=total_tools,
        total_prompts=total_prompts,
        total_resources=total_resources,
        servers=servers,
        conflicts=conflicts,
    )


@router.get("/health/detailed", response_model=DetailedHealthResponse)
async def get_detailed_health(
    composer: MCPServerComposer = Depends(get_composer),
    auth: AuthContext = Depends(require_auth),
) -> DetailedHealthResponse:
    """
    Get detailed health information.
    
    Returns comprehensive health information including server statuses,
    uptime, and failure counts.
    
    Args:
        composer: MCPServerComposer instance.
        auth: Authentication context.
    
    Returns:
        DetailedHealthResponse with comprehensive health information.
    """
    from ...__version__ import __version__
    
    # Count servers
    total_servers = len(composer.config.servers)
    running_servers = len(composer.discovered_servers)
    failed_servers = 0  # TODO: Track failed servers
    
    # Get server statuses
    server_statuses: Dict[str, ServerStatus] = {}
    for server_id in composer.config.servers.keys():
        if server_id in composer.discovered_servers:
            server_statuses[server_id] = ServerStatus.RUNNING
        else:
            server_statuses[server_id] = ServerStatus.STOPPED
    
    # Determine overall health
    if running_servers == 0:
        overall_status = HealthStatus.UNHEALTHY
    elif running_servers < total_servers:
        overall_status = HealthStatus.DEGRADED
    else:
        overall_status = HealthStatus.HEALTHY
    
    return DetailedHealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        version=__version__,
        servers=server_statuses,
        uptime_seconds=getattr(composer, 'uptime_seconds', 0.0),
        total_servers=total_servers,
        running_servers=running_servers,
        failed_servers=failed_servers,
    )


@router.get("/metrics")
async def get_metrics(
    composer: MCPServerComposer = Depends(get_composer),
    auth: AuthContext = Depends(require_auth),
) -> Dict[str, Any]:
    """
    Get aggregated metrics.
    
    Returns aggregated metrics for the entire MCP Compose
    including request counts, performance data, and resource usage.
    
    Args:
        composer: MCPServerComposer instance.
        auth: Authentication context.
    
    Returns:
        Dictionary with aggregated metrics.
    """
    # Get basic counts
    total_servers = len(composer.config.servers)
    running_servers = len(composer.discovered_servers)
    total_tools = len(composer.list_tools())
    total_prompts = len(composer.list_prompts())
    total_resources = len(composer.list_resources())
    
    # Aggregate metrics from all servers
    aggregated_metrics = {
        "timestamp": datetime.utcnow(),
        "uptime_seconds": getattr(composer, 'uptime_seconds', 0.0),
        "servers": {
            "total": total_servers,
            "running": running_servers,
            "stopped": total_servers - running_servers,
        },
        "capabilities": {
            "tools": total_tools,
            "prompts": total_prompts,
            "resources": total_resources,
        },
        "requests": {
            "total": 0,  # TODO: Track request counts
            "successful": 0,
            "failed": 0,
        },
        "performance": {
            "avg_response_time_ms": 0.0,  # TODO: Track response times
            "p95_response_time_ms": 0.0,
            "p99_response_time_ms": 0.0,
        },
        "resources": {
            "memory_mb": 0.0,  # TODO: Track memory usage
            "cpu_percent": 0.0,  # TODO: Track CPU usage
        },
    }
    
    # TODO: Add per-server metrics
    aggregated_metrics["per_server"] = {}
    
    # Update Prometheus metrics
    metrics_collector.update_uptime()
    metrics_collector.update_server_counts(total_servers, running_servers, total_servers - running_servers)
    metrics_collector.update_capability_counts(total_tools, total_prompts, total_resources)
    
    return aggregated_metrics


@router.get("/metrics/prometheus")
async def get_prometheus_metrics(
    composer: MCPServerComposer = Depends(get_composer),
    auth: AuthContext = Depends(require_auth),
) -> Response:
    """
    Get Prometheus metrics.
    
    Returns metrics in Prometheus text format for scraping by
    Prometheus server.
    
    Args:
        composer: MCPServerComposer instance.
        auth: Authentication context.
    
    Returns:
        Response with Prometheus metrics in text format.
    """
    # Update metrics before returning
    total_servers = len(composer.config.servers)
    running_servers = len(composer.discovered_servers)
    total_tools = len(composer.list_tools())
    total_prompts = len(composer.list_prompts())
    total_resources = len(composer.list_resources())
    
    metrics_collector.update_uptime()
    metrics_collector.update_server_counts(total_servers, running_servers, total_servers - running_servers)
    metrics_collector.update_capability_counts(total_tools, total_prompts, total_resources)
    
    # Return metrics in Prometheus format
    return Response(
        content=metrics_collector.get_metrics(),
        media_type=metrics_collector.get_content_type(),
    )


__all__ = ["router"]
