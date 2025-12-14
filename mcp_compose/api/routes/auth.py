"""
Authentication routes for MCP Compose API.

This module provides endpoints for user authentication including login/logout.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response, Depends
from pydantic import BaseModel

from ...auth import AuthContext, AuthenticationError, BasicAuthenticator
from ...config import MCPComposerConfig
from ..dependencies import get_config

logger = logging.getLogger(__name__)

router = APIRouter()

# Session store for authenticated users
_sessions: dict[str, AuthContext] = {}


class LoginRequest(BaseModel):
    """Login request model."""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response model."""
    success: bool
    token: str
    user_id: str
    message: Optional[str] = None


class LogoutResponse(BaseModel):
    """Logout response model."""
    success: bool
    message: str


def get_basic_authenticator(config: MCPComposerConfig = Depends(get_config)) -> Optional[BasicAuthenticator]:
    """
    Get the basic authenticator from config.
    
    Args:
        config: MCP Compose configuration.
    
    Returns:
        BasicAuthenticator if configured, None otherwise.
    """
    if not config.authentication or not config.authentication.enabled:
        return None
    
    if not config.authentication.basic:
        return None
    
    return BasicAuthenticator(
        username=config.authentication.basic.username,
        password=config.authentication.basic.password,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    authenticator: Optional[BasicAuthenticator] = Depends(get_basic_authenticator),
) -> LoginResponse:
    """
    Authenticate user with username and password.
    
    Args:
        request: Login credentials.
        authenticator: Basic authenticator instance.
    
    Returns:
        LoginResponse with authentication token.
    
    Raises:
        HTTPException: If authentication fails.
    """
    if not authenticator:
        raise HTTPException(
            status_code=400,
            detail="Basic authentication is not enabled",
        )
    
    try:
        context = await authenticator.authenticate({
            "username": request.username,
            "password": request.password,
        })
        
        # Store session
        _sessions[context.token] = context
        
        logger.info(f"User {context.user_id} logged in successfully")
        
        return LoginResponse(
            success=True,
            token=context.token,
            user_id=context.user_id,
            message="Login successful",
        )
    
    except AuthenticationError as e:
        logger.warning(f"Login failed for user {request.username}: {e}")
        raise HTTPException(
            status_code=401,
            detail=str(e),
        )


@router.post("/logout", response_model=LogoutResponse)
async def logout(request: Request) -> LogoutResponse:
    """
    Logout current user and invalidate session.
    
    Args:
        request: HTTP request.
    
    Returns:
        LogoutResponse indicating success.
    """
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        if token in _sessions:
            del _sessions[token]
            logger.info(f"User session {token[:8]}... logged out")
            return LogoutResponse(
                success=True,
                message="Logout successful",
            )
    
    return LogoutResponse(
        success=True,
        message="No active session found",
    )


@router.get("/me")
async def get_current_user(request: Request) -> dict:
    """
    Get current authenticated user information.
    
    Args:
        request: HTTP request.
    
    Returns:
        User information if authenticated.
    
    Raises:
        HTTPException: If not authenticated.
    """
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
        )
    
    token = auth_header[7:]
    context = _sessions.get(token)
    
    if not context:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )
    
    if context.is_expired():
        del _sessions[token]
        raise HTTPException(
            status_code=401,
            detail="Token expired",
        )
    
    return {
        "user_id": context.user_id,
        "auth_type": context.auth_type.value,
        "scopes": context.scopes,
        "authenticated_at": context.authenticated_at.isoformat() if context.authenticated_at else None,
        "expires_at": context.expires_at.isoformat() if context.expires_at else None,
    }
