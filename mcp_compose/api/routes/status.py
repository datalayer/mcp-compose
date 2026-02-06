# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Status and composition endpoints.

Provides endpoints for retrieving system status, composition details,
and aggregated metrics.
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Response

from ...auth import AuthContext
from ...composer import MCPServerComposer
from ...config import MCPComposerConfig
from ...metrics import metrics_collector
from ..dependencies import get_composer, get_config, require_auth
from ..models import (
    CompositionResponse,
    ServerInfo,
    ServerStatus,
)

router = APIRouter(tags=["status"])


@router.get("/status")
async def get_status(
    composer: MCPServerComposer = Depends(get_composer),
    config: MCPComposerConfig = Depends(get_config),
    auth: AuthContext = Depends(require_auth),
) -> dict[str, Any]:
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
    all_servers = []
    if config.servers:
        if config.servers.embedded and config.servers.embedded.servers:
            all_servers.extend(config.servers.embedded.servers)
        if config.servers.proxied:
            if config.servers.proxied.stdio:
                all_servers.extend(config.servers.proxied.stdio)
            if config.servers.proxied.sse:
                all_servers.extend(config.servers.proxied.sse)
            if config.servers.proxied.http:
                all_servers.extend(config.servers.proxied.http)

    total_servers = len(all_servers)

    # Get process info to determine running servers
    process_info = composer.get_proxied_servers_info() if composer.process_manager else {}
    running_servers = sum(1 for info in process_info.values() if info.get("state") == "running")
    stopped_servers = total_servers - running_servers

    # Count capabilities
    total_tools = len(composer.list_tools())
    total_prompts = len(composer.list_prompts())
    total_resources = len(composer.list_resources())

    # Get server statuses
    server_statuses = {}
    for server in all_servers:
        server_id = server.name
        if server_id in process_info:
            state = process_info[server_id].get("state", "stopped")
            if state == "running":
                server_statuses[server_id] = ServerStatus.RUNNING
            elif state == "crashed":
                server_statuses[server_id] = ServerStatus.CRASHED
            elif state == "starting":
                server_statuses[server_id] = ServerStatus.STARTING
            elif state == "stopping":
                server_statuses[server_id] = ServerStatus.STOPPING
            else:
                server_statuses[server_id] = ServerStatus.STOPPED
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
        "uptime_seconds": getattr(composer, "uptime_seconds", 0.0),
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
    servers: list[ServerInfo] = []
    all_servers = []
    if config.servers:
        if config.servers.embedded and config.servers.embedded.servers:
            all_servers.extend(config.servers.embedded.servers)
        if config.servers.proxied:
            if config.servers.proxied.stdio:
                all_servers.extend(config.servers.proxied.stdio)
            if config.servers.proxied.sse:
                all_servers.extend(config.servers.proxied.sse)
            if config.servers.proxied.http:
                all_servers.extend(config.servers.proxied.http)

    # Get process info for server states
    process_info = composer.get_proxied_servers_info() if composer.process_manager else {}

    for server_config in all_servers:
        # Determine status
        server_id = server_config.name
        if server_id in process_info:
            state = process_info[server_id].get("state", "stopped")
            if state == "running":
                server_status = ServerStatus.RUNNING
            elif state == "crashed":
                server_status = ServerStatus.CRASHED
            elif state in ["starting", "stopping"]:
                server_status = (
                    ServerStatus.STARTING if state == "starting" else ServerStatus.STOPPING
                )
            else:
                server_status = ServerStatus.STOPPED
        else:
            server_status = ServerStatus.STOPPED

        # Get server type
        if hasattr(server_config, "url"):
            transport = "sse" if hasattr(server_config, "mode") else "http"
        elif hasattr(server_config, "command"):
            transport = "stdio"
        else:
            transport = "embedded"

        # Create server info
        server_info = ServerInfo(
            id=server_id,
            name=server_config.name,
            status=server_status,
            type=transport,
            command=getattr(server_config, "command", None),
            url=getattr(server_config, "url", None),
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
    tool_names: dict[str, list[str]] = {}
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
            conflicts.append(
                {
                    "type": "tool",
                    "name": tool_name,
                    "servers": server_ids,
                    "message": f"Tool '{tool_name}' defined in multiple servers: {', '.join(server_ids)}",
                }
            )

    return CompositionResponse(
        total_servers=len(servers),
        total_tools=total_tools,
        total_prompts=total_prompts,
        total_resources=total_resources,
        servers=servers,
        conflicts=conflicts,
    )


@router.get("/metrics")
async def get_metrics(
    composer: MCPServerComposer = Depends(get_composer),
    auth: AuthContext = Depends(require_auth),
) -> dict[str, Any]:
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
    all_servers = []
    if composer.config.servers:
        if composer.config.servers.embedded and composer.config.servers.embedded.servers:
            all_servers.extend(composer.config.servers.embedded.servers)
        if composer.config.servers.proxied:
            if composer.config.servers.proxied.stdio:
                all_servers.extend(composer.config.servers.proxied.stdio)
            if composer.config.servers.proxied.sse:
                all_servers.extend(composer.config.servers.proxied.sse)
            if composer.config.servers.proxied.http:
                all_servers.extend(composer.config.servers.proxied.http)

    total_servers = len(all_servers)

    # Get process info to determine running servers
    process_info = composer.get_proxied_servers_info() if composer.process_manager else {}
    running_servers = sum(1 for info in process_info.values() if info.get("state") == "running")

    total_tools = len(composer.list_tools())
    total_prompts = len(composer.list_prompts())
    total_resources = len(composer.list_resources())

    # Aggregate metrics from all servers
    aggregated_metrics = {
        "timestamp": datetime.utcnow(),
        "uptime_seconds": getattr(composer, "uptime_seconds", 0.0),
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
    metrics_collector.update_server_counts(
        total_servers, running_servers, total_servers - running_servers
    )
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
    all_servers = []
    if composer.config.servers:
        if composer.config.servers.embedded and composer.config.servers.embedded.servers:
            all_servers.extend(composer.config.servers.embedded.servers)
        if composer.config.servers.proxied:
            if composer.config.servers.proxied.stdio:
                all_servers.extend(composer.config.servers.proxied.stdio)
            if composer.config.servers.proxied.sse:
                all_servers.extend(composer.config.servers.proxied.sse)
            if composer.config.servers.proxied.http:
                all_servers.extend(composer.config.servers.proxied.http)

    total_servers = len(all_servers)

    # Get process info to determine running servers
    process_info = composer.get_proxied_servers_info() if composer.process_manager else {}
    running_servers = sum(1 for info in process_info.values() if info.get("state") == "running")

    total_tools = len(composer.list_tools())
    total_prompts = len(composer.list_prompts())
    total_resources = len(composer.list_resources())

    metrics_collector.update_uptime()
    metrics_collector.update_server_counts(
        total_servers, running_servers, total_servers - running_servers
    )
    metrics_collector.update_capability_counts(total_tools, total_prompts, total_resources)

    # Return metrics in Prometheus format
    return Response(
        content=metrics_collector.get_metrics(),
        media_type=metrics_collector.get_content_type(),
    )


__all__ = ["router"]
