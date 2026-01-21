# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Tool and resource management endpoints.

Provides endpoints for discovering and invoking tools, accessing prompts,
and reading resources from all composed MCP servers.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from ..dependencies import get_composer, require_auth
from ..models import (
    PaginationParams,
    PromptInfo,
    PromptListResponse,
    ResourceInfo,
    ResourceListResponse,
    ToolInfo,
    ToolInvokeRequest,
    ToolInvokeResponse,
    ToolListResponse,
    ToolParameter,
)
from ...auth import AuthContext
from ...composer import MCPServerComposer

router = APIRouter(tags=["tools", "prompts", "resources"])


# ============================================================================
# Tool Endpoints
# ============================================================================

@router.get("/tools", response_model=ToolListResponse)
async def list_tools(
    offset: int = Query(0, ge=0, description="Number of tools to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of tools to return"),
    server_id: Optional[str] = Query(None, description="Filter by server ID"),
    composer: MCPServerComposer = Depends(get_composer),
    auth: AuthContext = Depends(require_auth),
) -> ToolListResponse:
    """
    List all available tools.
    
    Returns a paginated list of all tools available across all composed
    MCP servers, with optional filtering by server.
    
    Args:
        offset: Number of tools to skip (for pagination).
        limit: Maximum number of tools to return.
        server_id: Optional filter by server ID.
        composer: MCPServerComposer instance.
        auth: Authentication context.
    
    Returns:
        ToolListResponse with list of tools and pagination info.
    """
    # Debug logging
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"composed_tools: {list(composer.composed_tools.keys())}")
    logger.info(f"source_mapping: {composer.source_mapping}")
    
    # Get all tool IDs
    all_tool_ids = composer.list_tools()
    
    # Filter by server if specified
    if server_id:
        all_tool_ids = [
            tid for tid in all_tool_ids
            if tid.startswith(f"{server_id}.")
        ]
    
    # Build tool info list
    tools: List[ToolInfo] = []
    for tool_id in all_tool_ids:
        try:
            # Get tool details from composer
            tool_detail = composer.get_tool(tool_id)
            if not tool_detail:
                continue
            
            # Extract server ID from tool ID (format: server_id.tool_name)
            parts = tool_id.split(".", 1)
            server = parts[0] if len(parts) > 1 else "unknown"
            tool_name = parts[1] if len(parts) > 1 else tool_id
            
            # Create tool info
            tool_info = ToolInfo(
                id=tool_id,
                name=tool_name,
                description=tool_detail.get("description", ""),
                server_id=server,
                parameters=[
                    ToolParameter(
                        name=param_name,
                        type=param_info.get("type", "string"),
                        description=param_info.get("description", ""),
                        required=param_name in tool_detail.get("inputSchema", {}).get("required", []),
                    )
                    for param_name, param_info in tool_detail.get("inputSchema", {}).get("properties", {}).items()
                ],
            )
            tools.append(tool_info)
        except Exception:
            # Skip tools with errors
            continue
    
    # Apply pagination
    total = len(tools)
    paginated_tools = tools[offset : offset + limit]
    
    return ToolListResponse(
        tools=paginated_tools,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/tools/{tool_id}", response_model=ToolInfo)
async def get_tool(
    tool_id: str,
    composer: MCPServerComposer = Depends(get_composer),
    auth: AuthContext = Depends(require_auth),
) -> ToolInfo:
    """
    Get detailed information about a specific tool.
    
    Args:
        tool_id: Tool ID (format: server_id.tool_name).
        composer: MCPServerComposer instance.
        auth: Authentication context.
    
    Returns:
        ToolInfo with detailed tool information.
    
    Raises:
        HTTPException: If tool not found.
    """
    # Get tool details
    tool_detail = composer.get_tool(tool_id)
    if not tool_detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{tool_id}' not found",
        )
    
    # Extract server ID from tool ID
    parts = tool_id.split(".", 1)
    server = parts[0] if len(parts) > 1 else "unknown"
    tool_name = parts[1] if len(parts) > 1 else tool_id
    
    # Create tool info
    tool_info = ToolInfo(
        id=tool_id,
        name=tool_name,
        description=tool_detail.get("description", ""),
        server_id=server,
        parameters=[
            ToolParameter(
                name=param_name,
                type=param_info.get("type", "string"),
                description=param_info.get("description", ""),
                required=param_name in tool_detail.get("inputSchema", {}).get("required", []),
            )
            for param_name, param_info in tool_detail.get("inputSchema", {}).get("properties", {}).items()
        ],
    )
    
    return tool_info


@router.post("/tools/{tool_id}/invoke", response_model=ToolInvokeResponse)
async def invoke_tool(
    tool_id: str,
    request: ToolInvokeRequest,
    composer: MCPServerComposer = Depends(get_composer),
    auth: AuthContext = Depends(require_auth),
) -> ToolInvokeResponse:
    """
    Invoke a tool with the provided arguments.
    
    Args:
        tool_id: Tool ID (format: server_id.tool_name).
        request: Tool invocation request with arguments.
        composer: MCPServerComposer instance.
        auth: Authentication context.
    
    Returns:
        ToolInvokeResponse with invocation result.
    
    Raises:
        HTTPException: If tool not found or invocation fails.
    """
    # Check if tool exists
    tool_detail = composer.get_tool(tool_id)
    if not tool_detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{tool_id}' not found",
        )
    
    try:
        # Invoke tool through composer
        result = await composer.invoke_tool(tool_id, request.arguments)
        
        return ToolInvokeResponse(
            success=True,
            result=result,
            tool_id=tool_id,
        )
    except Exception as e:
        # Handle invocation errors
        return ToolInvokeResponse(
            success=False,
            result=None,
            tool_id=tool_id,
            error=str(e),
        )


# ============================================================================
# Prompt Endpoints
# ============================================================================

@router.get("/prompts", response_model=PromptListResponse)
async def list_prompts(
    offset: int = Query(0, ge=0, description="Number of prompts to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of prompts to return"),
    server_id: Optional[str] = Query(None, description="Filter by server ID"),
    composer: MCPServerComposer = Depends(get_composer),
    auth: AuthContext = Depends(require_auth),
) -> PromptListResponse:
    """
    List all available prompts.
    
    Returns a paginated list of all prompts available across all composed
    MCP servers, with optional filtering by server.
    
    Args:
        offset: Number of prompts to skip (for pagination).
        limit: Maximum number of prompts to return.
        server_id: Optional filter by server ID.
        composer: MCPServerComposer instance.
        auth: Authentication context.
    
    Returns:
        PromptListResponse with list of prompts and pagination info.
    """
    # Get all prompt IDs
    all_prompt_ids = composer.list_prompts()
    
    # Filter by server if specified
    if server_id:
        all_prompt_ids = [
            pid for pid in all_prompt_ids
            if pid.startswith(f"{server_id}.")
        ]
    
    # Build prompt info list
    prompts: List[PromptInfo] = []
    for prompt_id in all_prompt_ids:
        try:
            # Get prompt details from composer
            prompt_detail = composer.get_prompt(prompt_id)
            if not prompt_detail:
                continue
            
            # Extract server ID from prompt ID
            parts = prompt_id.split(".", 1)
            server = parts[0] if len(parts) > 1 else "unknown"
            prompt_name = parts[1] if len(parts) > 1 else prompt_id
            
            # Create prompt info
            prompt_info = PromptInfo(
                id=prompt_id,
                name=prompt_name,
                description=prompt_detail.get("description", ""),
                server_id=server,
                arguments=list(prompt_detail.get("arguments", {}).keys()),
            )
            prompts.append(prompt_info)
        except Exception:
            # Skip prompts with errors
            continue
    
    # Apply pagination
    total = len(prompts)
    paginated_prompts = prompts[offset : offset + limit]
    
    return PromptListResponse(
        prompts=paginated_prompts,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/prompts/{prompt_id}", response_model=PromptInfo)
async def get_prompt(
    prompt_id: str,
    composer: MCPServerComposer = Depends(get_composer),
    auth: AuthContext = Depends(require_auth),
) -> PromptInfo:
    """
    Get detailed information about a specific prompt.
    
    Args:
        prompt_id: Prompt ID (format: server_id.prompt_name).
        composer: MCPServerComposer instance.
        auth: Authentication context.
    
    Returns:
        PromptInfo with detailed prompt information.
    
    Raises:
        HTTPException: If prompt not found.
    """
    # Get prompt details
    prompt_detail = composer.get_prompt(prompt_id)
    if not prompt_detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prompt '{prompt_id}' not found",
        )
    
    # Extract server ID from prompt ID
    parts = prompt_id.split(".", 1)
    server = parts[0] if len(parts) > 1 else "unknown"
    prompt_name = parts[1] if len(parts) > 1 else prompt_id
    
    # Create prompt info
    prompt_info = PromptInfo(
        id=prompt_id,
        name=prompt_name,
        description=prompt_detail.get("description", ""),
        server_id=server,
        arguments=list(prompt_detail.get("arguments", {}).keys()),
    )
    
    return prompt_info


# ============================================================================
# Resource Endpoints
# ============================================================================

@router.get("/resources", response_model=ResourceListResponse)
async def list_resources(
    offset: int = Query(0, ge=0, description="Number of resources to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of resources to return"),
    server_id: Optional[str] = Query(None, description="Filter by server ID"),
    composer: MCPServerComposer = Depends(get_composer),
    auth: AuthContext = Depends(require_auth),
) -> ResourceListResponse:
    """
    List all available resources.
    
    Returns a paginated list of all resources available across all composed
    MCP servers, with optional filtering by server.
    
    Args:
        offset: Number of resources to skip (for pagination).
        limit: Maximum number of resources to return.
        server_id: Optional filter by server ID.
        composer: MCPServerComposer instance.
        auth: Authentication context.
    
    Returns:
        ResourceListResponse with list of resources and pagination info.
    """
    # Get all resource URIs
    all_resource_uris = composer.list_resources()
    
    # Filter by server if specified
    if server_id:
        all_resource_uris = [
            uri for uri in all_resource_uris
            if uri.startswith(f"{server_id}.")
        ]
    
    # Build resource info list
    resources: List[ResourceInfo] = []
    for resource_uri in all_resource_uris:
        try:
            # Get resource details from composer
            resource_detail = composer.get_resource(resource_uri)
            if not resource_detail:
                continue
            
            # Extract server ID from resource URI
            parts = resource_uri.split(".", 1)
            server = parts[0] if len(parts) > 1 else "unknown"
            
            # Create resource info
            resource_info = ResourceInfo(
                uri=resource_uri,
                name=resource_detail.get("name", resource_uri),
                description=resource_detail.get("description", ""),
                mime_type=resource_detail.get("mimeType", "text/plain"),
                server_id=server,
            )
            resources.append(resource_info)
        except Exception:
            # Skip resources with errors
            continue
    
    # Apply pagination
    total = len(resources)
    paginated_resources = resources[offset : offset + limit]
    
    return ResourceListResponse(
        resources=paginated_resources,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/resources/{resource_uri:path}")
async def read_resource(
    resource_uri: str,
    composer: MCPServerComposer = Depends(get_composer),
    auth: AuthContext = Depends(require_auth),
) -> Dict[str, Any]:
    """
    Read a resource's contents.
    
    Args:
        resource_uri: Resource URI (format: server_id.resource_path).
        composer: MCPServerComposer instance.
        auth: Authentication context.
    
    Returns:
        Dictionary with resource contents and metadata.
    
    Raises:
        HTTPException: If resource not found or cannot be read.
    """
    # Check if resource exists
    resource_detail = composer.get_resource(resource_uri)
    if not resource_detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resource '{resource_uri}' not found",
        )
    
    try:
        # Read resource through composer
        contents = await composer.read_resource(resource_uri)
        
        return {
            "uri": resource_uri,
            "name": resource_detail.get("name", resource_uri),
            "mime_type": resource_detail.get("mimeType", "text/plain"),
            "contents": contents,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read resource: {str(e)}",
        )


__all__ = ["router"]
