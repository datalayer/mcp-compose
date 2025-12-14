"""
Configuration management endpoints.

Provides endpoints for retrieving, updating, validating, and reloading
the MCP Compose configuration.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from ..dependencies import get_composer, require_auth
from ..models import (
    ConfigResponse,
    ConfigReloadResponse,
    ConfigUpdateRequest,
    ConfigValidateRequest,
    ConfigValidateResponse,
)
from ...auth import AuthContext
from ...composer import MCPServerComposer
from ...exceptions import MCPConfigurationError

router = APIRouter(tags=["config"])


@router.get("/config", response_model=ConfigResponse)
async def get_config(
    composer: MCPServerComposer = Depends(get_composer),
    auth: AuthContext = Depends(require_auth),
) -> ConfigResponse:
    """
    Get current configuration.
    
    Returns the current MCP Compose configuration including
    all server definitions, authentication settings, and global options.
    
    Args:
        composer: MCPServerComposer instance.
        auth: Authentication context.
    
    Returns:
        ConfigResponse with current configuration.
    """
    # Convert Pydantic config to dict
    config_dict = composer.config.model_dump() if composer.config else {}
    
    return ConfigResponse(config=config_dict)


@router.put("/config", response_model=ConfigResponse)
async def update_config(
    request: ConfigUpdateRequest,
    composer: MCPServerComposer = Depends(get_composer),
    auth: AuthContext = Depends(require_auth),
) -> ConfigResponse:
    """
    Update configuration.
    
    Updates the MCP Compose configuration with the provided
    settings. This does not automatically reload the configuration;
    use POST /config/reload to apply changes.
    
    Args:
        request: Configuration update request.
        composer: MCPServerComposer instance.
        auth: Authentication context.
    
    Returns:
        ConfigResponse with updated configuration.
    
    Raises:
        HTTPException: If configuration update fails.
    """
    try:
        # Validate configuration first
        from ...config import ComposerConfig
        
        # Create new config from dict
        new_config = ComposerConfig.from_dict(request.config)
        
        # Update composer configuration
        composer.config = new_config
        
        # Get updated configuration
        config_dict = new_config.to_dict() if hasattr(new_config, 'to_dict') else request.config
        
        return ConfigResponse(config=config_dict)
    
    except MCPConfigurationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid configuration: {str(e)}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update configuration: {str(e)}",
        )


@router.post("/config/validate", response_model=ConfigValidateResponse)
async def validate_config(
    request: ConfigValidateRequest,
    composer: MCPServerComposer = Depends(get_composer),
    auth: AuthContext = Depends(require_auth),
) -> ConfigValidateResponse:
    """
    Validate configuration.
    
    Validates the provided configuration without applying it.
    Returns validation result with any errors found.
    
    Args:
        request: Configuration validation request.
        composer: MCPServerComposer instance.
        auth: Authentication context.
    
    Returns:
        ConfigValidateResponse with validation result and errors.
    """
    errors = []
    
    try:
        # Try to create config from dict
        from ...config import ComposerConfig
        
        new_config = ComposerConfig.from_dict(request.config)
        
        # Additional validation checks
        if not new_config.servers:
            errors.append("Configuration must include at least one server")
        
        # Validate each server
        for server_id, server_config in new_config.servers.items():
            if not server_config.name:
                errors.append(f"Server '{server_id}' missing name")
            
            # Check transport-specific requirements
            transport = getattr(server_config.transport, 'value', 'stdio') if hasattr(server_config, 'transport') else 'stdio'
            
            if transport == 'stdio':
                if not getattr(server_config, 'command', None):
                    errors.append(f"Server '{server_id}' with stdio transport must have command")
            elif transport == 'sse':
                if not getattr(server_config, 'url', None):
                    errors.append(f"Server '{server_id}' with SSE transport must have url")
        
        # If no errors found during validation
        if not errors:
            return ConfigValidateResponse(valid=True, errors=[])
    
    except MCPConfigurationError as e:
        errors.append(str(e))
    except Exception as e:
        errors.append(f"Configuration validation failed: {str(e)}")
    
    return ConfigValidateResponse(valid=len(errors) == 0, errors=errors)


@router.post("/config/reload", response_model=ConfigReloadResponse)
async def reload_config(
    composer: MCPServerComposer = Depends(get_composer),
    auth: AuthContext = Depends(require_auth),
) -> ConfigReloadResponse:
    """
    Reload configuration.
    
    Reloads the configuration and restarts all servers with the new
    configuration. This operation may cause temporary service disruption.
    
    Args:
        composer: MCPServerComposer instance.
        auth: Authentication context.
    
    Returns:
        ConfigReloadResponse with reload result.
    
    Raises:
        HTTPException: If reload fails.
    """
    try:
        # Stop all running proxied servers
        process_info = composer.get_proxied_servers_info() if composer.process_manager else {}
        running_servers = [
            server_id for server_id, info in process_info.items()
            if info.get('state') == 'running'
        ]
        
        for server_id in running_servers:
            try:
                await composer.process_manager.stop_process(server_id)
            except Exception:
                pass  # Continue even if stop fails
        
        # Reload configuration (if composer has reload method)
        if hasattr(composer, 'reload_config'):
            await composer.reload_config()
        
        # Start auto-start servers
        for server_id, server_config in composer.config.servers.items():
            if getattr(server_config, 'auto_start', True):
                try:
                    await composer.start_server(server_id)
                except Exception:
                    pass  # Continue even if start fails
        
        # Rediscover servers
        await composer.discover_servers()
        
        return ConfigReloadResponse(
            success=True,
            message="Configuration reloaded successfully",
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reload configuration: {str(e)}",
        )


__all__ = ["router"]
