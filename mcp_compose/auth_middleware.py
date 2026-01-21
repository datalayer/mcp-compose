# Copyright (c) 2023-2025 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Authentication middleware for MCP Compose.

This module provides middleware to enforce authentication on MCP requests.
"""

import logging
from typing import Any, Callable, Dict, Optional

from .auth import (
    AuthContext,
    Authenticator,
    AuthenticationError,
    InsufficientScopesError,
)

logger = logging.getLogger(__name__)


class AuthMiddleware:
    """
    Middleware to enforce authentication on MCP requests.
    
    Wraps request handlers to require authentication before processing.
    """
    
    def __init__(
        self,
        authenticator: Authenticator,
        required_scopes: Optional[list[str]] = None,
        allow_anonymous: bool = False,
    ):
        """
        Initialize authentication middleware.
        
        Args:
            authenticator: Authenticator instance to use.
            required_scopes: List of scopes required for access.
            allow_anonymous: If True, allow requests without authentication.
        """
        self.authenticator = authenticator
        self.required_scopes = required_scopes or []
        self.allow_anonymous = allow_anonymous
        self._contexts: Dict[str, AuthContext] = {}  # session_id -> context
    
    async def authenticate_request(
        self,
        credentials: Dict[str, Any],
        session_id: Optional[str] = None,
    ) -> AuthContext:
        """
        Authenticate a request using provided credentials.
        
        Args:
            credentials: Authentication credentials.
            session_id: Optional session ID to cache context.
        
        Returns:
            AuthContext for the authenticated user.
        
        Raises:
            AuthenticationError: If authentication fails.
            InsufficientScopesError: If required scopes are missing.
        """
        # Authenticate
        context = await self.authenticator.authenticate(credentials)
        
        # Check required scopes
        if self.required_scopes:
            missing_scopes = [
                scope for scope in self.required_scopes
                if not context.has_scope(scope) and "*" not in context.scopes
            ]
            
            if missing_scopes:
                raise InsufficientScopesError(
                    f"Missing required scopes: {', '.join(missing_scopes)}"
                )
        
        # Cache context if session ID provided
        if session_id:
            self._contexts[session_id] = context
        
        logger.info(
            f"Authenticated user {context.user_id} "
            f"with {context.auth_type.value} (session: {session_id})"
        )
        
        return context
    
    async def validate_session(self, session_id: str) -> Optional[AuthContext]:
        """
        Validate an existing session.
        
        Args:
            session_id: Session ID to validate.
        
        Returns:
            AuthContext if session is valid, None otherwise.
        """
        context = self._contexts.get(session_id)
        if not context:
            return None
        
        # Check if context is expired
        if context.is_expired():
            del self._contexts[session_id]
            return None
        
        # Validate with authenticator
        is_valid = await self.authenticator.validate(context)
        if not is_valid:
            del self._contexts[session_id]
            return None
        
        return context
    
    async def invalidate_session(self, session_id: str) -> bool:
        """
        Invalidate a session.
        
        Args:
            session_id: Session ID to invalidate.
        
        Returns:
            True if session was found and invalidated.
        """
        if session_id in self._contexts:
            del self._contexts[session_id]
            logger.info(f"Invalidated session {session_id}")
            return True
        return False
    
    def get_session_context(self, session_id: str) -> Optional[AuthContext]:
        """
        Get authentication context for a session.
        
        Args:
            session_id: Session ID.
        
        Returns:
            AuthContext if found, None otherwise.
        """
        return self._contexts.get(session_id)
    
    def wrap_handler(
        self,
        handler: Callable,
        extract_credentials: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    ) -> Callable:
        """
        Wrap a request handler with authentication.
        
        Args:
            handler: Request handler function to wrap.
            extract_credentials: Function to extract credentials from request.
                If None, expects request to have "credentials" key.
        
        Returns:
            Wrapped handler that enforces authentication.
        """
        async def wrapped_handler(request: Dict[str, Any], **kwargs) -> Any:
            """Wrapped handler with authentication."""
            session_id = request.get("session_id")
            
            # Try to use existing session
            context = None
            if session_id:
                context = await self.validate_session(session_id)
            
            # If no valid session, authenticate
            if context is None:
                if self.allow_anonymous:
                    # Allow without authentication
                    logger.debug("Allowing anonymous request")
                else:
                    # Extract credentials
                    if extract_credentials:
                        credentials = extract_credentials(request)
                    else:
                        credentials = request.get("credentials", {})
                    
                    # Authenticate
                    context = await self.authenticate_request(credentials, session_id)
            
            # Add context to request
            request["auth_context"] = context
            
            # Call original handler
            return await handler(request, **kwargs)
        
        return wrapped_handler
    
    def require_scope(self, *scopes: str) -> Callable:
        """
        Decorator to require specific scopes for a handler.
        
        Args:
            *scopes: Required scopes.
        
        Returns:
            Decorator function.
        """
        def decorator(handler: Callable) -> Callable:
            async def wrapped_handler(request: Dict[str, Any], **kwargs) -> Any:
                context = request.get("auth_context")
                if not context:
                    raise AuthenticationError("No authentication context")
                
                # Check scopes
                missing = [
                    scope for scope in scopes
                    if not context.has_scope(scope) and "*" not in context.scopes
                ]
                
                if missing:
                    raise InsufficientScopesError(
                        f"Missing required scopes: {', '.join(missing)}"
                    )
                
                return await handler(request, **kwargs)
            
            return wrapped_handler
        
        return decorator
    
    def list_sessions(self) -> list[Dict[str, Any]]:
        """
        List all active sessions.
        
        Returns:
            List of session information dictionaries.
        """
        sessions = []
        for session_id, context in self._contexts.items():
            sessions.append({
                "session_id": session_id,
                "user_id": context.user_id,
                "auth_type": context.auth_type.value,
                "scopes": context.scopes,
                "authenticated_at": context.authenticated_at.isoformat() if context.authenticated_at else None,
                "expires_at": context.expires_at.isoformat() if context.expires_at else None,
                "is_expired": context.is_expired(),
            })
        return sessions
    
    def clear_expired_sessions(self) -> int:
        """
        Clear all expired sessions.
        
        Returns:
            Number of sessions cleared.
        """
        expired = [
            session_id for session_id, context in self._contexts.items()
            if context.is_expired()
        ]
        
        for session_id in expired:
            del self._contexts[session_id]
        
        if expired:
            logger.info(f"Cleared {len(expired)} expired sessions")
        
        return len(expired)


def create_auth_middleware(
    authenticator: Authenticator,
    **kwargs
) -> AuthMiddleware:
    """
    Factory function to create authentication middleware.
    
    Args:
        authenticator: Authenticator instance to use.
        **kwargs: Additional arguments for AuthMiddleware.
    
    Returns:
        AuthMiddleware instance.
    """
    return AuthMiddleware(authenticator=authenticator, **kwargs)
