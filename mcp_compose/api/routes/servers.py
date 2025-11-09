"""
Server management endpoints.

Provides endpoints for managing MCP servers: listing, details, lifecycle
control (start/stop/restart), removal, log streaming, and metrics.
"""

import asyncio
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from ..dependencies import get_composer, require_auth
from ..models import (
    PaginationParams,
    ServerActionResponse,
    ServerDetailResponse,
    ServerInfo,
    ServerListResponse,
    ServerStatus,
)
from ...auth import AuthContext
from ...composer import MCPServerComposer

router = APIRouter(tags=["servers"])


@router.get("/servers", response_model=ServerListResponse)
async def list_servers(
    offset: int = Query(0, ge=0, description="Number of servers to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of servers to return"),
    status_filter: Optional[ServerStatus] = Query(None, description="Filter by server status"),
    composer: MCPServerComposer = Depends(get_composer),
    auth: AuthContext = Depends(require_auth),
) -> ServerListResponse:
    """
    List all servers.
    
    Returns a paginated list of all configured servers with their
    current status and basic information.
    
    Args:
        offset: Number of servers to skip (for pagination).
        limit: Maximum number of servers to return.
        status_filter: Optional filter by server status.
        composer: MCPServerComposer instance.
        auth: Authentication context.
    
    Returns:
        ServerListResponse with list of servers and pagination info.
    """
    # Get all server IDs
    all_server_ids = composer.list_servers()
    
    # Build server info list
    servers: List[ServerInfo] = []
    for server_id in all_server_ids:
        try:
            # Get server configuration
            server_config = composer.config.servers.get(server_id)
            if not server_config:
                continue
            
            # Determine server status (simplified - in reality would check process manager)
            # For now, check if server is in discovered servers
            is_running = server_id in composer.discovered_servers
            server_status = ServerStatus.RUNNING if is_running else ServerStatus.STOPPED
            
            # Apply status filter if specified
            if status_filter and server_status != status_filter:
                continue
            
            # Create server info
            server_info = ServerInfo(
                id=server_id,
                name=server_config.name,
                command=server_config.command,
                args=server_config.args or [],
                env=server_config.env or {},
                status=server_status,
                transport=server_config.transport.value if server_config.transport else "stdio",
                auto_start=getattr(server_config, "auto_start", False),
            )
            servers.append(server_info)
        except Exception:
            # Skip servers with errors
            continue
    
    # Apply pagination
    total = len(servers)
    paginated_servers = servers[offset : offset + limit]
    
    return ServerListResponse(
        servers=paginated_servers,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/servers/{server_id}", response_model=ServerDetailResponse)
async def get_server_detail(
    server_id: str,
    composer: MCPServerComposer = Depends(get_composer),
    auth: AuthContext = Depends(require_auth),
) -> ServerDetailResponse:
    """
    Get detailed information about a specific server.
    
    Returns comprehensive information about a server including its
    configuration, status, capabilities, and statistics.
    
    Args:
        server_id: Server ID.
        composer: MCPServerComposer instance.
        auth: Authentication context.
    
    Returns:
        ServerDetailResponse with detailed server information.
    
    Raises:
        HTTPException: If server not found.
    """
    # Check if server exists
    server_config = composer.config.servers.get(server_id)
    if not server_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_id}' not found",
        )
    
    # Get server status
    is_running = server_id in composer.discovered_servers
    server_status = ServerStatus.RUNNING if is_running else ServerStatus.STOPPED
    
    # Get capabilities if server is running
    tools_count = 0
    prompts_count = 0
    resources_count = 0
    
    if is_running:
        # Count tools from this server
        all_tools = composer.list_tools()
        tools_count = sum(1 for tool_id in all_tools if tool_id.startswith(f"{server_id}."))
        
        # Count prompts from this server
        all_prompts = composer.list_prompts()
        prompts_count = sum(1 for prompt_id in all_prompts if prompt_id.startswith(f"{server_id}."))
        
        # Count resources from this server
        all_resources = composer.list_resources()
        resources_count = sum(1 for resource_id in all_resources if resource_id.startswith(f"{server_id}."))
    
    # Build server info
    server_info = ServerInfo(
        id=server_id,
        name=server_config.name,
        command=server_config.command,
        args=server_config.args or [],
        env=server_config.env or {},
        status=server_status,
        transport=server_config.transport.value if server_config.transport else "stdio",
        auto_start=getattr(server_config, "auto_start", False),
    )
    
    return ServerDetailResponse(
        server=server_info,
        tools_count=tools_count,
        prompts_count=prompts_count,
        resources_count=resources_count,
        uptime_seconds=0.0 if not is_running else 3600.0,  # Placeholder
    )


@router.post("/servers/{server_id}/start", response_model=ServerActionResponse)
async def start_server(
    server_id: str,
    composer: MCPServerComposer = Depends(get_composer),
    auth: AuthContext = Depends(require_auth),
) -> ServerActionResponse:
    """
    Start a server.
    
    Starts the specified server if it is currently stopped.
    
    Args:
        server_id: Server ID.
        composer: MCPServerComposer instance.
        auth: Authentication context.
    
    Returns:
        ServerActionResponse with operation result.
    
    Raises:
        HTTPException: If server not found or cannot be started.
    """
    # Check if server exists
    if server_id not in composer.config.servers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_id}' not found",
        )
    
    # Check if already running
    if server_id in composer.discovered_servers:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Server '{server_id}' is already running",
        )
    
    try:
        # Start server (would use process manager in reality)
        # For now, trigger discovery which will start servers
        await composer.discover_servers()
        
        return ServerActionResponse(
            success=True,
            message=f"Server '{server_id}' started successfully",
            server_id=server_id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start server: {str(e)}",
        )


@router.post("/servers/{server_id}/stop", response_model=ServerActionResponse)
async def stop_server(
    server_id: str,
    composer: MCPServerComposer = Depends(get_composer),
    auth: AuthContext = Depends(require_auth),
) -> ServerActionResponse:
    """
    Stop a server.
    
    Stops the specified server if it is currently running.
    
    Args:
        server_id: Server ID.
        composer: MCPServerComposer instance.
        auth: Authentication context.
    
    Returns:
        ServerActionResponse with operation result.
    
    Raises:
        HTTPException: If server not found or cannot be stopped.
    """
    # Check if server exists
    if server_id not in composer.config.servers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_id}' not found",
        )
    
    # Check if running
    if server_id not in composer.discovered_servers:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Server '{server_id}' is not running",
        )
    
    try:
        # Stop server (would use process manager in reality)
        # For now, remove from discovered servers
        if server_id in composer.discovered_servers:
            del composer.discovered_servers[server_id]
        
        return ServerActionResponse(
            success=True,
            message=f"Server '{server_id}' stopped successfully",
            server_id=server_id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop server: {str(e)}",
        )


@router.post("/servers/{server_id}/restart", response_model=ServerActionResponse)
async def restart_server(
    server_id: str,
    composer: MCPServerComposer = Depends(get_composer),
    auth: AuthContext = Depends(require_auth),
) -> ServerActionResponse:
    """
    Restart a server.
    
    Stops and then starts the specified server.
    
    Args:
        server_id: Server ID.
        composer: MCPServerComposer instance.
        auth: Authentication context.
    
    Returns:
        ServerActionResponse with operation result.
    
    Raises:
        HTTPException: If server not found or cannot be restarted.
    """
    # Check if server exists
    if server_id not in composer.config.servers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_id}' not found",
        )
    
    try:
        # Stop if running
        if server_id in composer.discovered_servers:
            del composer.discovered_servers[server_id]
            await asyncio.sleep(0.5)  # Brief pause
        
        # Start server
        await composer.discover_servers()
        
        return ServerActionResponse(
            success=True,
            message=f"Server '{server_id}' restarted successfully",
            server_id=server_id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restart server: {str(e)}",
        )


@router.delete("/servers/{server_id}", response_model=ServerActionResponse)
async def remove_server(
    server_id: str,
    composer: MCPServerComposer = Depends(get_composer),
    auth: AuthContext = Depends(require_auth),
) -> ServerActionResponse:
    """
    Remove a server.
    
    Removes a server from the configuration. The server must be
    stopped before it can be removed.
    
    Args:
        server_id: Server ID.
        composer: MCPServerComposer instance.
        auth: Authentication context.
    
    Returns:
        ServerActionResponse with operation result.
    
    Raises:
        HTTPException: If server not found, still running, or cannot be removed.
    """
    # Check if server exists
    if server_id not in composer.config.servers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_id}' not found",
        )
    
    # Check if running
    if server_id in composer.discovered_servers:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Server '{server_id}' is still running. Stop it first.",
        )
    
    try:
        # Remove from configuration
        del composer.config.servers[server_id]
        
        return ServerActionResponse(
            success=True,
            message=f"Server '{server_id}' removed successfully",
            server_id=server_id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove server: {str(e)}",
        )


@router.get("/servers/{server_id}/logs")
async def stream_server_logs(
    server_id: str,
    composer: MCPServerComposer = Depends(get_composer),
    auth: AuthContext = Depends(require_auth),
) -> StreamingResponse:
    """
    Stream server logs via Server-Sent Events (SSE).
    
    Opens a persistent connection that streams log messages from the
    specified server in real-time.
    
    Args:
        server_id: Server ID.
        composer: MCPServerComposer instance.
        auth: Authentication context.
    
    Returns:
        StreamingResponse with SSE log stream.
    
    Raises:
        HTTPException: If server not found or not running.
    """
    # Check if server exists
    if server_id not in composer.config.servers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_id}' not found",
        )
    
    # Check if running
    if server_id not in composer.discovered_servers:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Server '{server_id}' is not running",
        )
    
    async def log_generator():
        """Generate SSE log events."""
        # In production, this would read from actual log files or process output
        # For now, send some example log messages
        yield f"data: {{'timestamp': '2025-10-13T12:00:00Z', 'level': 'INFO', 'message': 'Server {server_id} started'}}\n\n"
        
        # Keep connection alive and stream logs
        try:
            for i in range(5):
                await asyncio.sleep(1)
                yield f"data: {{'timestamp': '2025-10-13T12:00:{i+1:02d}Z', 'level': 'DEBUG', 'message': 'Processing request #{i+1}'}}\n\n"
        except asyncio.CancelledError:
            # Client disconnected
            pass
    
    return StreamingResponse(
        log_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/servers/{server_id}/metrics")
async def get_server_metrics(
    server_id: str,
    composer: MCPServerComposer = Depends(get_composer),
    auth: AuthContext = Depends(require_auth),
) -> Dict:
    """
    Get server metrics.
    
    Returns performance metrics and statistics for the specified server.
    
    Args:
        server_id: Server ID.
        composer: MCPServerComposer instance.
        auth: Authentication context.
    
    Returns:
        Dictionary with server metrics.
    
    Raises:
        HTTPException: If server not found.
    """
    # Check if server exists
    if server_id not in composer.config.servers:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_id}' not found",
        )
    
    # Check if running
    is_running = server_id in composer.discovered_servers
    
    # Build metrics (placeholder values)
    metrics = {
        "server_id": server_id,
        "status": "running" if is_running else "stopped",
        "uptime_seconds": 3600.0 if is_running else 0.0,
        "requests_total": 42 if is_running else 0,
        "requests_failed": 2 if is_running else 0,
        "requests_per_second": 0.012 if is_running else 0.0,
        "average_response_time_ms": 150.5 if is_running else 0.0,
        "memory_usage_mb": 45.2 if is_running else 0.0,
        "cpu_usage_percent": 5.3 if is_running else 0.0,
    }
    
    return metrics


__all__ = ["router"]
