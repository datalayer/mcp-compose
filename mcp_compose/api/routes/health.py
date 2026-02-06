# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Health check endpoints.

Provides endpoints for monitoring API and server health.
"""

from datetime import datetime

from fastapi import APIRouter, Depends

from ...composer import MCPServerComposer
from ..dependencies import get_composer
from ..models import (
    DetailedHealthResponse,
    HealthResponse,
    HealthStatus,
    ServerStatus,
)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """
    Simple health check.

    Returns basic health status and version information.
    This endpoint is lightweight and suitable for load balancer health checks.

    Returns:
        HealthResponse with status and version.
    """
    from ...__version__ import __version__

    return HealthResponse(
        status=HealthStatus.HEALTHY,
        version=__version__,
        timestamp=datetime.utcnow(),
    )


@router.get("/health/detailed", response_model=DetailedHealthResponse)
async def get_detailed_health(
    composer: MCPServerComposer = Depends(get_composer),
) -> DetailedHealthResponse:
    """
    Detailed health check.

    Returns comprehensive health information including:
    - Overall health status
    - Server counts and statuses
    - System uptime
    - Configuration status

    Returns:
        DetailedHealthResponse with comprehensive health data.
    """
    from ...__version__ import __version__

    # Get all servers from config
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

    # Count servers by status
    status_counts: dict[ServerStatus, int] = {
        ServerStatus.RUNNING: 0,
        ServerStatus.STOPPED: 0,
        ServerStatus.STARTING: 0,
        ServerStatus.STOPPING: 0,
        ServerStatus.CRASHED: 0,
        ServerStatus.UNKNOWN: 0,
    }

    # Get process info
    process_info = composer.get_proxied_servers_info() if composer.process_manager else {}

    server_statuses = {}
    for server_config in all_servers:
        server_id = server_config.name
        # Determine status from process info
        if server_id in process_info:
            state = process_info[server_id].get("state", "stopped")
            if state == "running":
                server_status = ServerStatus.RUNNING
            elif state == "crashed":
                server_status = ServerStatus.CRASHED
            elif state == "starting":
                server_status = ServerStatus.STARTING
            elif state == "stopping":
                server_status = ServerStatus.STOPPING
            else:
                server_status = ServerStatus.STOPPED
        else:
            server_status = ServerStatus.STOPPED

        status_counts[server_status] += 1
        server_statuses[server_id] = server_status

    # Determine overall health
    total_servers = len(servers)
    if status_counts[ServerStatus.CRASHED] > 0:
        overall_status = HealthStatus.UNHEALTHY
    elif status_counts[ServerStatus.RUNNING] < total_servers:
        overall_status = HealthStatus.DEGRADED
    else:
        overall_status = HealthStatus.HEALTHY

    # Calculate uptime (simplified - would track actual start time)
    uptime_seconds = 3600.0  # Placeholder

    return DetailedHealthResponse(
        status=overall_status,
        version=__version__,
        timestamp=datetime.utcnow(),
        uptime_seconds=uptime_seconds,
        total_servers=total_servers,
        running_servers=status_counts[ServerStatus.RUNNING],
        failed_servers=status_counts[ServerStatus.CRASHED] + status_counts[ServerStatus.STOPPED],
        servers=server_statuses,
    )


__all__ = ["router"]
