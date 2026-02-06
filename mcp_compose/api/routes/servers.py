# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Server management endpoints.

Provides endpoints for managing MCP servers: listing, details, lifecycle
control (start/stop/restart), removal, log streaming, and metrics.
"""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from ...auth import AuthContext
from ...composer import MCPServerComposer
from ..dependencies import get_composer, require_auth
from ..models import (
    ServerActionResponse,
    ServerDetailResponse,
    ServerInfo,
    ServerListResponse,
    ServerStatus,
)

router = APIRouter(tags=["servers"])


@router.get("/servers", response_model=ServerListResponse)
async def list_servers(
    offset: int = Query(0, ge=0, description="Number of servers to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of servers to return"),
    status_filter: ServerStatus | None = Query(None, description="Filter by server status"),
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
    # Get all server configurations from config (source of truth for what servers exist)
    all_servers = []
    if composer.config and composer.config.servers:
        # Add embedded servers
        if composer.config.servers.embedded and composer.config.servers.embedded.servers:
            all_servers.extend(composer.config.servers.embedded.servers)

        # Add proxied servers
        if composer.config.servers.proxied:
            if composer.config.servers.proxied.stdio:
                all_servers.extend(composer.config.servers.proxied.stdio)
            if composer.config.servers.proxied.sse:
                all_servers.extend(composer.config.servers.proxied.sse)
            if composer.config.servers.proxied.http:
                all_servers.extend(composer.config.servers.proxied.http)

    # Get process info for status (whether servers are actually running)
    process_info = composer.get_proxied_servers_info() if composer.process_manager else {}

    # Build server info list
    servers: list[ServerInfo] = []
    for server_config in all_servers:
        try:
            server_id = server_config.name

            # Determine server status
            if server_id in process_info:
                # Proxied server - check process state
                proc_info = process_info[server_id]
                state_str = proc_info.get("state", "stopped")
                if state_str == "running":
                    server_status = ServerStatus.RUNNING
                elif state_str in ["starting", "stopping"]:
                    server_status = (
                        ServerStatus.STARTING if state_str == "starting" else ServerStatus.STOPPING
                    )
                elif state_str == "crashed":
                    server_status = ServerStatus.CRASHED
                else:
                    server_status = ServerStatus.STOPPED
            else:
                # Embedded server or not started
                server_status = ServerStatus.STOPPED

            # Apply status filter if specified
            if status_filter and server_status != status_filter:
                continue

            # Determine server type
            if hasattr(server_config, "url"):
                server_type = "sse" if hasattr(server_config, "mode") else "http"
            elif hasattr(server_config, "command"):
                server_type = "stdio"
            else:
                server_type = "embedded"

            # Extract command for display
            command = None
            if hasattr(server_config, "command"):
                if isinstance(server_config.command, list):
                    command = " ".join(server_config.command)
                else:
                    command = str(server_config.command)

            # Extract URL for SSE/HTTP servers
            url = getattr(server_config, "url", None)

            # Get uptime and other process info
            uptime_seconds = None
            pid = None
            restart_count = 0
            if server_id in process_info:
                uptime_seconds = process_info[server_id].get("uptime")
                pid = process_info[server_id].get("pid")
                restart_count = process_info[server_id].get("restart_count", 0)

            # Create server info
            server_info = ServerInfo(
                id=server_id,
                name=server_config.name,
                status=server_status,
                type=server_type,
                command=command,
                url=url,
                pid=pid,
                uptime_seconds=uptime_seconds,
                restart_count=restart_count,
                last_error=None,  # TODO: Track last error from process manager
            )
            servers.append(server_info)
        except Exception as e:
            # Log error and skip servers with errors
            import logging

            logger = logging.getLogger(__name__)
            logger.error(
                f"Error processing server {getattr(server_config, 'name', 'unknown')}: {e}",
                exc_info=True,
            )
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
    # Check if server exists - search in all server categories
    server_config = None
    server_type = None

    # Check embedded servers
    if composer.config.servers.embedded and composer.config.servers.embedded.servers:
        for srv in composer.config.servers.embedded.servers:
            if srv.name == server_id:
                server_config = srv
                server_type = "embedded"
                break

    # Check proxied servers if not found
    if not server_config and composer.config.servers.proxied:
        for srv_list, srv_type in [
            (composer.config.servers.proxied.stdio, "stdio"),
            (composer.config.servers.proxied.sse, "sse"),
            (composer.config.servers.proxied.http, "http"),
        ]:
            if srv_list:
                for srv in srv_list:
                    if srv.name == server_id:
                        server_config = srv
                        server_type = srv_type
                        break
            if server_config:
                break

    if not server_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_id}' not found",
        )

    # Get server status from process_info
    process_info = composer.get_proxied_servers_info()
    is_running = server_id in process_info and process_info[server_id].get("state") == "running"

    # Map process state to ServerStatus
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

    # Get capabilities if server is running
    tools_count = 0
    prompts_count = 0
    resources_count = 0

    if is_running:
        # Count tools from this server using source_mapping
        all_tools = composer.list_tools()
        for tool_name in all_tools:
            source = composer.source_mapping.get(tool_name, {}).get("server")
            if source == server_id:
                tools_count += 1

        # Count prompts from this server using source_mapping
        all_prompts = composer.list_prompts()
        for prompt_name in all_prompts:
            source = composer.source_mapping.get(prompt_name, {}).get("server")
            if source == server_id:
                prompts_count += 1

        # Count resources from this server using source_mapping
        all_resources = composer.list_resources()
        for resource_name in all_resources:
            source = composer.source_mapping.get(resource_name, {}).get("server")
            if source == server_id:
                resources_count += 1

    # Extract command and args
    command = getattr(server_config, "command", "")
    args = getattr(server_config, "args", [])
    if isinstance(command, list):
        args = command[1:] if len(command) > 1 else []
        command = command[0] if command else ""

    # Build server info
    server_info = ServerInfo(
        id=server_id,
        name=server_config.name,
        command=command,
        args=args if isinstance(args, list) else [],
        env=getattr(server_config, "env", {}) or {},
        status=server_status,
        transport=getattr(server_config, "transport", server_type) or "stdio",
        auto_start=getattr(server_config, "auto_start", False),
    )

    # Get uptime from process_info
    uptime = 0.0
    if server_id in process_info:
        uptime = process_info[server_id].get("uptime", 0.0)

    return ServerDetailResponse(
        server=server_info,
        tools_count=tools_count,
        prompts_count=prompts_count,
        resources_count=resources_count,
        uptime_seconds=uptime,
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
    # Check if server exists - search in all server categories
    server_exists = False

    # Check embedded servers
    if composer.config.servers.embedded and composer.config.servers.embedded.servers:
        if any(srv.name == server_id for srv in composer.config.servers.embedded.servers):
            # Embedded servers are always "running" - they're part of the same process
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Server '{server_id}' is an embedded server and cannot be started independently",
            )

    # Check proxied servers
    if composer.config.servers.proxied:
        for srv_list in [
            composer.config.servers.proxied.stdio,
            composer.config.servers.proxied.sse,
            composer.config.servers.proxied.http,
        ]:
            if srv_list and any(srv.name == server_id for srv in srv_list):
                server_exists = True
                break

    if not server_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_id}' not found",
        )

    # Check if already running
    process_info = composer.get_proxied_servers_info()
    if server_id in process_info and process_info[server_id].get("state") == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Server '{server_id}' is already running",
        )

    try:
        # Start server using process manager
        await composer.process_manager.start_process(server_id)

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
    # Check if server exists - search in all server categories
    server_exists = False

    # Check embedded servers
    if composer.config.servers.embedded and composer.config.servers.embedded.servers:
        if any(srv.name == server_id for srv in composer.config.servers.embedded.servers):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Server '{server_id}' is an embedded server and cannot be stopped",
            )

    # Check proxied servers
    if composer.config.servers.proxied:
        for srv_list in [
            composer.config.servers.proxied.stdio,
            composer.config.servers.proxied.sse,
            composer.config.servers.proxied.http,
        ]:
            if srv_list and any(srv.name == server_id for srv in srv_list):
                server_exists = True
                break

    if not server_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_id}' not found",
        )

    # Check if running
    process_info = composer.get_proxied_servers_info()
    if server_id not in process_info or process_info[server_id].get("state") != "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Server '{server_id}' is not running",
        )

    try:
        # Stop server using process manager
        await composer.process_manager.stop_process(server_id)

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
    # Check if server exists - search in all server categories
    server_exists = False

    # Check embedded servers
    if composer.config.servers.embedded and composer.config.servers.embedded.servers:
        if any(srv.name == server_id for srv in composer.config.servers.embedded.servers):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Server '{server_id}' is an embedded server and cannot be restarted",
            )

    # Check proxied servers
    if composer.config.servers.proxied:
        for srv_list in [
            composer.config.servers.proxied.stdio,
            composer.config.servers.proxied.sse,
            composer.config.servers.proxied.http,
        ]:
            if srv_list and any(srv.name == server_id for srv in srv_list):
                server_exists = True
                break

    if not server_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_id}' not found",
        )

    try:
        # Restart server using composer's restart method
        await composer.restart_proxied_server(server_id)

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
    # Check if server exists - search in all server categories
    server_exists = False
    server_list = None
    server_index = -1

    # Check embedded servers
    if composer.config.servers.embedded and composer.config.servers.embedded.servers:
        for idx, srv in enumerate(composer.config.servers.embedded.servers):
            if srv.name == server_id:
                server_exists = True
                server_list = composer.config.servers.embedded.servers
                server_index = idx
                break

    # Check proxied servers if not found
    if not server_exists and composer.config.servers.proxied:
        for srv_list in [
            composer.config.servers.proxied.stdio,
            composer.config.servers.proxied.sse,
            composer.config.servers.proxied.http,
        ]:
            if srv_list:
                for idx, srv in enumerate(srv_list):
                    if srv.name == server_id:
                        server_exists = True
                        server_list = srv_list
                        server_index = idx
                        break
            if server_exists:
                break

    if not server_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_id}' not found",
        )

    # Check if running
    process_info = composer.get_proxied_servers_info()
    if server_id in process_info and process_info[server_id].get("state") == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Server '{server_id}' is still running. Stop it first.",
        )

    try:
        # Remove from configuration list
        if server_list is not None and server_index >= 0:
            server_list.pop(server_index)

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
    # Check if server exists - search in all server categories
    server_exists = False

    # Check embedded servers
    if composer.config.servers.embedded and composer.config.servers.embedded.servers:
        if any(srv.name == server_id for srv in composer.config.servers.embedded.servers):
            server_exists = True

    # Check proxied servers if not found
    if not server_exists and composer.config.servers.proxied:
        for srv_list in [
            composer.config.servers.proxied.stdio,
            composer.config.servers.proxied.sse,
            composer.config.servers.proxied.http,
        ]:
            if srv_list and any(srv.name == server_id for srv in srv_list):
                server_exists = True
                break

    if not server_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_id}' not found",
        )

    # Check if running
    process_info = composer.get_proxied_servers_info()
    if server_id not in process_info or process_info[server_id].get("state") != "running":
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
                yield f"data: {{'timestamp': '2025-10-13T12:00:{i + 1:02d}Z', 'level': 'DEBUG', 'message': 'Processing request #{i + 1}'}}\n\n"
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
) -> dict:
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
    # Check if server exists - search in all server categories
    server_exists = False

    # Check embedded servers
    if composer.config.servers.embedded and composer.config.servers.embedded.servers:
        if any(srv.name == server_id for srv in composer.config.servers.embedded.servers):
            server_exists = True

    # Check proxied servers if not found
    if not server_exists and composer.config.servers.proxied:
        for srv_list in [
            composer.config.servers.proxied.stdio,
            composer.config.servers.proxied.sse,
            composer.config.servers.proxied.http,
        ]:
            if srv_list and any(srv.name == server_id for srv in srv_list):
                server_exists = True
                break

    if not server_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Server '{server_id}' not found",
        )

    # Check if running
    process_info = composer.get_proxied_servers_info()
    is_running = server_id in process_info and process_info[server_id].get("state") == "running"

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
