"""
FastAPI dependencies for dependency injection.

This module provides dependency injection functions for authentication,
authorization, and access to shared resources.
"""

from typing import Optional

from fastapi import Depends, Header, HTTPException, status

from ..auth import AuthContext, AuthType
from ..authz import AuthorizationMiddleware, RoleManager
from ..composer import MCPServerComposer
from ..tool_authz import ToolPermissionManager


# Global instances (to be initialized by application)
_composer: Optional[MCPServerComposer] = None
_role_manager: Optional[RoleManager] = None
_authz_middleware: Optional[AuthorizationMiddleware] = None
_tool_permission_manager: Optional[ToolPermissionManager] = None


def set_composer(composer: MCPServerComposer) -> None:
    """Set the global composer instance."""
    global _composer
    _composer = composer


def set_role_manager(role_manager: RoleManager) -> None:
    """Set the global role manager instance."""
    global _role_manager
    _role_manager = role_manager


def set_authz_middleware(middleware: AuthorizationMiddleware) -> None:
    """Set the global authorization middleware instance."""
    global _authz_middleware
    _authz_middleware = middleware


def set_tool_permission_manager(manager: ToolPermissionManager) -> None:
    """Set the global tool permission manager instance."""
    global _tool_permission_manager
    _tool_permission_manager = manager


async def get_composer() -> MCPServerComposer:
    """
    Get the MCPServerComposer instance.
    
    Returns:
        MCPServerComposer instance.
    
    Raises:
        HTTPException: If composer is not initialized.
    """
    if _composer is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Composer not initialized"
        )
    return _composer


async def get_role_manager() -> Optional[RoleManager]:
    """Get the RoleManager instance."""
    return _role_manager


async def get_authz_middleware() -> Optional[AuthorizationMiddleware]:
    """Get the AuthorizationMiddleware instance."""
    return _authz_middleware


async def get_tool_permission_manager() -> Optional[ToolPermissionManager]:
    """Get the ToolPermissionManager instance."""
    return _tool_permission_manager


async def get_auth_context(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
) -> Optional[AuthContext]:
    """
    Extract authentication context from request headers.
    
    Supports:
    - API Key: X-API-Key header
    - Bearer token: Authorization header
    
    Args:
        authorization: Authorization header value.
        x_api_key: X-API-Key header value.
    
    Returns:
        AuthContext if authentication provided, None otherwise.
    """
    # Check for API key
    if x_api_key:
        # In production, validate the API key here
        # For now, create a basic auth context
        return AuthContext(
            user_id=f"api_key_{x_api_key[:8]}",
            auth_type=AuthType.API_KEY,
            token=x_api_key,
            scopes=["*"],  # Full access for API keys
        )
    
    # Check for Bearer token
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        # In production, validate the JWT token here
        # For now, create a basic auth context
        return AuthContext(
            user_id="jwt_user",
            auth_type=AuthType.JWT,
            token=token,
            scopes=["*"],  # Full access for valid tokens
        )
    
    return None


async def require_auth(
    auth_context: Optional[AuthContext] = Depends(get_auth_context),
) -> AuthContext:
    """
    Require authentication for endpoint.
    
    Args:
        auth_context: Authentication context from headers.
    
    Returns:
        AuthContext if authenticated.
    
    Raises:
        HTTPException: If not authenticated.
    """
    if auth_context is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth_context


async def require_permission(
    resource: str,
    action: str,
    auth_context: AuthContext = Depends(require_auth),
    authz: Optional[AuthorizationMiddleware] = Depends(get_authz_middleware),
) -> AuthContext:
    """
    Require specific permission for endpoint.
    
    Args:
        resource: Required resource.
        action: Required action.
        auth_context: Authentication context.
        authz: Authorization middleware.
    
    Returns:
        AuthContext if authorized.
    
    Raises:
        HTTPException: If not authorized.
    """
    if authz and not authz.check_permission(auth_context, resource, action):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing permission: {resource}:{action}",
        )
    return auth_context


async def require_tool_permission(
    tool_name: str,
    action: str = "execute",
    auth_context: AuthContext = Depends(require_auth),
    tool_mgr: Optional[ToolPermissionManager] = Depends(get_tool_permission_manager),
) -> AuthContext:
    """
    Require tool-specific permission.
    
    Args:
        tool_name: Tool name.
        action: Action to perform.
        auth_context: Authentication context.
        tool_mgr: Tool permission manager.
    
    Returns:
        AuthContext if authorized.
    
    Raises:
        HTTPException: If not authorized.
    """
    if tool_mgr and not tool_mgr.check_tool_permission(
        auth_context.user_id,
        tool_name,
        action,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing tool permission: {tool_name}:{action}",
        )
    return auth_context


__all__ = [
    "set_composer",
    "set_role_manager",
    "set_authz_middleware",
    "set_tool_permission_manager",
    "get_composer",
    "get_role_manager",
    "get_authz_middleware",
    "get_tool_permission_manager",
    "get_auth_context",
    "require_auth",
    "require_permission",
    "require_tool_permission",
]
