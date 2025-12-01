"""
FastAPI dependencies for dependency injection.

This module provides dependency injection functions for authentication,
authorization, and access to shared resources.
"""

from typing import Optional

from fastapi import Depends, Header, HTTPException, status

from ..auth import AuthContext, AuthType, create_authenticator
from ..authz import AuthorizationMiddleware, RoleManager
from ..composer import MCPServerComposer
from ..tool_authz import ToolPermissionManager


# Global instances (to be initialized by application)
_composer: Optional[MCPServerComposer] = None
_role_manager: Optional[RoleManager] = None
_authz_middleware: Optional[AuthorizationMiddleware] = None
_tool_permission_manager: Optional[ToolPermissionManager] = None
_authenticator = None  # Store authenticator instance


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


def set_authenticator(authenticator) -> None:
    """Set the global authenticator instance."""
    global _authenticator
    _authenticator = authenticator


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
    # If no authenticator is configured, allow all requests
    if _authenticator is None:
        return None
    
    credentials = {}
    
    # Check for API key
    if x_api_key:
        credentials["api_key"] = x_api_key
    
    # Check for Bearer token
    elif authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        credentials["token"] = token
    
    # If no credentials provided, return None
    if not credentials:
        return None
    
    # Authenticate using the configured authenticator
    try:
        context = await _authenticator.authenticate(credentials)
        return context
    except Exception as e:
        # Log the error and raise 401
        import logging
        from ..auth import InvalidCredentialsError
        logger = logging.getLogger(__name__)
        logger.warning(f"Authentication failed: {e}")
        
        # Raise 401 Unauthorized for invalid credentials
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e) if isinstance(e, InvalidCredentialsError) else "Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_auth(
    auth_context: Optional[AuthContext] = Depends(get_auth_context),
) -> AuthContext:
    """
    Require authentication for endpoint (if authentication is enabled).
    
    If no authenticator is configured, allows anonymous access.
    If authenticator is configured, requires valid credentials.
    
    Args:
        auth_context: Authentication context from headers.
    
    Returns:
        AuthContext if authenticated, or anonymous context if auth is disabled.
    
    Raises:
        HTTPException: If authentication is enabled but credentials are invalid.
    """
    # If no authenticator is configured, allow anonymous access
    if _authenticator is None:
        # Create anonymous context
        return AuthContext(
            user_id="anonymous",
            auth_type=AuthType.NONE,
            scopes=["*"],
        )
    
    # Authenticator is configured, require valid credentials
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
    "set_authenticator",
    "get_composer",
    "get_role_manager",
    "get_authz_middleware",
    "get_tool_permission_manager",
    "get_auth_context",
    "require_auth",
    "require_permission",
    "require_tool_permission",
]
