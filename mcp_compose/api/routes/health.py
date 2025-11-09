"""
Health check endpoints.

Provides endpoints for monitoring API and server health.
"""

from datetime import datetime, timedelta
from typing import Dict

from fastapi import APIRouter, Depends

from ..dependencies import get_composer
from ..models import (
    DetailedHealthResponse,
    HealthResponse,
    HealthStatus,
    ServerStatus,
)
from ...composer import MCPServerComposer

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
    
    # Get all servers
    servers = composer.list_servers()
    
    # Count servers by status
    status_counts: Dict[ServerStatus, int] = {
        ServerStatus.RUNNING: 0,
        ServerStatus.STOPPED: 0,
        ServerStatus.STARTING: 0,
        ServerStatus.STOPPING: 0,
        ServerStatus.CRASHED: 0,
        ServerStatus.UNKNOWN: 0,
    }
    
    server_statuses = {}
    for server_id in servers:
        # Get server status (simplified - in reality would query process manager)
        # For now, assume servers are running if they exist
        is_running = True  # composer.get_server_status(server_id)
        status = ServerStatus.RUNNING if is_running else ServerStatus.STOPPED
        status_counts[status] += 1
        server_statuses[server_id] = status
    
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
