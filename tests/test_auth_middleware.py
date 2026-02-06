# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""Tests for authentication middleware."""

from datetime import datetime, timedelta

import pytest

from mcp_compose.auth import (
    APIKeyAuthenticator,
    AuthContext,
    AuthenticationError,
    AuthType,
    InsufficientScopesError,
    NoAuthenticator,
)
from mcp_compose.auth_jwt import JWTAuthenticator
from mcp_compose.auth_middleware import AuthMiddleware


class TestAuthMiddleware:
    """Test authentication middleware."""

    @pytest.mark.asyncio
    async def test_create_middleware(self):
        """Test creating authentication middleware."""
        auth = NoAuthenticator()
        middleware = AuthMiddleware(auth)

        assert middleware.authenticator == auth
        assert len(middleware._contexts) == 0

    @pytest.mark.asyncio
    async def test_authenticate_request(self):
        """Test authenticating a request."""
        authenticator = APIKeyAuthenticator()
        api_key = authenticator.generate_api_key()
        authenticator.add_api_key(api_key, "user123", scopes=["read", "write"])

        middleware = AuthMiddleware(authenticator)

        credentials = {"api_key": api_key}
        context = await middleware.authenticate_request(credentials)

        assert context.user_id == "user123"
        assert context.auth_type == AuthType.API_KEY
        assert "read" in context.scopes
        assert "write" in context.scopes

    @pytest.mark.asyncio
    async def test_authenticate_request_with_session(self):
        """Test that authenticated requests create sessions."""
        auth = NoAuthenticator()
        middleware = AuthMiddleware(auth)

        credentials = {"user_id": "user123"}
        session_id = "test_session"
        context1 = await middleware.authenticate_request(credentials, session_id)

        assert len(middleware._contexts) == 1

        # Validate the session exists
        context2 = await middleware.validate_session(session_id)

        # Should have the same user
        assert context1.user_id == context2.user_id

    @pytest.mark.asyncio
    async def test_authenticate_jwt_request(self):
        """Test authenticating with JWT tokens."""
        jwt_auth = JWTAuthenticator(secret_key="test_secret")
        middleware = AuthMiddleware(jwt_auth)

        # Create a token
        token = jwt_auth.create_access_token(
            user_id="user456",
            scopes=["admin"],
        )

        credentials = {"token": token}
        context = await middleware.authenticate_request(credentials)

        assert context.user_id == "user456"
        assert context.auth_type == AuthType.JWT
        assert "admin" in context.scopes

    @pytest.mark.asyncio
    async def test_validate_session(self):
        """Test validating an active session."""
        auth = NoAuthenticator()
        middleware = AuthMiddleware(auth)

        # Create a session
        credentials = {"user_id": "user123"}
        session_id = "test_session"
        context = await middleware.authenticate_request(credentials, session_id)

        # Validate the session
        validated_context = await middleware.validate_session(session_id)
        assert validated_context is not None
        # NoAuthenticator always returns "anonymous"
        assert validated_context.user_id == "anonymous"

    @pytest.mark.asyncio
    async def test_validate_nonexistent_session(self):
        """Test validating a non-existent session."""
        auth = NoAuthenticator()
        middleware = AuthMiddleware(auth)

        validated = await middleware.validate_session("nonexistent_session_id")
        assert validated is None

    @pytest.mark.asyncio
    async def test_validate_expired_session(self):
        """Test validating an expired session."""
        auth = NoAuthenticator()
        middleware = AuthMiddleware(auth)

        # Create a session with past expiration
        expires_at = datetime.utcnow() - timedelta(hours=1)
        context = AuthContext(
            user_id="user123",
            auth_type=AuthType.NONE,
            token="",
            expires_at=expires_at,
        )

        # Manually add expired session
        session_id = "expired_session"
        middleware._contexts[session_id] = context

        # Should be invalid
        validated = await middleware.validate_session(session_id)
        assert validated is None

        # Session should be removed
        assert session_id not in middleware._contexts

    @pytest.mark.asyncio
    async def test_invalidate_session(self):
        """Test invalidating a session."""
        auth = NoAuthenticator()
        middleware = AuthMiddleware(auth)

        # Create a session
        credentials = {"user_id": "user123"}
        session_id = "test_session"
        await middleware.authenticate_request(credentials, session_id)

        # Invalidate
        result = await middleware.invalidate_session(session_id)

        # Should return True
        assert result is True

        # Should be gone
        assert session_id not in middleware._contexts

    @pytest.mark.asyncio
    async def test_invalidate_nonexistent_session(self):
        """Test invalidating a non-existent session."""
        auth = NoAuthenticator()
        middleware = AuthMiddleware(auth)

        result = await middleware.invalidate_session("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_clear_expired_sessions(self):
        """Test clearing expired sessions."""
        auth = NoAuthenticator()
        middleware = AuthMiddleware(auth)

        # Add valid session
        valid_context = AuthContext(
            user_id="valid_user",
            auth_type=AuthType.NONE,
            token="",
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        middleware._contexts["valid_session"] = valid_context

        # Add expired session
        expired_context = AuthContext(
            user_id="expired_user",
            auth_type=AuthType.NONE,
            token="",
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        middleware._contexts["expired_session"] = expired_context

        # Clear expired
        cleared = middleware.clear_expired_sessions()

        assert cleared == 1
        assert "valid_session" in middleware._contexts
        assert "expired_session" not in middleware._contexts

    @pytest.mark.asyncio
    async def test_list_sessions(self):
        """Test listing active sessions."""
        auth = NoAuthenticator()
        middleware = AuthMiddleware(auth)

        # Create multiple sessions
        await middleware.authenticate_request({"user_id": "user1"}, "session1")
        await middleware.authenticate_request({"user_id": "user2"}, "session2")

        sessions = middleware.list_sessions()

        assert len(sessions) == 2
        # NoAuthenticator always returns "anonymous"
        user_ids = [s["user_id"] for s in sessions]
        assert all(uid == "anonymous" for uid in user_ids)

    @pytest.mark.asyncio
    async def test_wrap_handler(self):
        """Test wrapping a handler with authentication."""
        auth = NoAuthenticator()
        middleware = AuthMiddleware(auth, allow_anonymous=False)

        # Create a simple handler
        async def test_handler(request, **kwargs):
            auth_context = request.get("auth_context")
            return {
                "user_id": auth_context.user_id if auth_context else None,
                "scopes": auth_context.scopes if auth_context else [],
            }

        # Wrap the handler
        wrapped = middleware.wrap_handler(test_handler)

        # Call with credentials
        request = {"credentials": {"user_id": "user123"}}
        result = await wrapped(request)

        # NoAuthenticator always returns "anonymous"
        assert result["user_id"] == "anonymous"
        assert "*" in result["scopes"]

    @pytest.mark.asyncio
    async def test_wrap_handler_with_session(self):
        """Test wrap handler reuses sessions."""
        auth = NoAuthenticator()
        middleware = AuthMiddleware(auth)

        async def test_handler(request, **kwargs):
            return {"user_id": request["auth_context"].user_id}

        wrapped = middleware.wrap_handler(test_handler)

        # First call creates session
        request1 = {
            "session_id": "test_session",
            "credentials": {"user_id": "user123"},
        }
        result1 = await wrapped(request1)
        # NoAuthenticator always returns "anonymous"
        assert result1["user_id"] == "anonymous"

        # Second call with same session ID should reuse context
        request2 = {
            "session_id": "test_session",
            "credentials": {"user_id": "different_user"},  # Should be ignored
        }
        result2 = await wrapped(request2)
        assert result2["user_id"] == "anonymous"  # Still anonymous

    @pytest.mark.asyncio
    async def test_require_scope_decorator(self):
        """Test the require_scope decorator."""
        authenticator = APIKeyAuthenticator()
        api_key = authenticator.generate_api_key()
        authenticator.add_api_key(api_key, "user123", scopes=["read"])

        middleware = AuthMiddleware(authenticator)

        # Create handler with scope requirement
        @middleware.require_scope("read")
        async def read_handler(request, **kwargs):
            return {"data": "sensitive"}

        # First authenticate to get context in request
        context = await middleware.authenticate_request({"api_key": api_key})
        request = {"auth_context": context}

        result = await read_handler(request)
        assert result["data"] == "sensitive"

    @pytest.mark.asyncio
    async def test_require_scope_insufficient(self):
        """Test require_scope with insufficient permissions."""
        authenticator = APIKeyAuthenticator()
        api_key = authenticator.generate_api_key()
        authenticator.add_api_key(api_key, "user123", scopes=["read"])

        middleware = AuthMiddleware(authenticator)

        # Create handler requiring 'admin' scope
        @middleware.require_scope("admin")
        async def admin_handler(request, **kwargs):
            return {"data": "admin_only"}

        # Authenticate with only 'read' scope
        context = await middleware.authenticate_request({"api_key": api_key})
        request = {"auth_context": context}

        # Should raise InsufficientScopesError
        with pytest.raises(InsufficientScopesError):
            await admin_handler(request)

    @pytest.mark.asyncio
    async def test_require_scope_no_context(self):
        """Test require_scope without auth context."""
        auth = NoAuthenticator()
        middleware = AuthMiddleware(auth)

        @middleware.require_scope("read")
        async def handler(request, **kwargs):
            return {"data": "test"}

        request = {}  # No auth_context

        with pytest.raises(AuthenticationError):
            await handler(request)

    @pytest.mark.asyncio
    async def test_required_scopes_at_middleware_level(self):
        """Test required scopes set at middleware level."""
        authenticator = APIKeyAuthenticator()
        api_key = authenticator.generate_api_key()
        authenticator.add_api_key(api_key, "user123", scopes=["read"])

        # Middleware requires 'write' scope
        middleware = AuthMiddleware(authenticator, required_scopes=["write"])

        credentials = {"api_key": api_key}

        # Should fail because user only has 'read' scope
        with pytest.raises(InsufficientScopesError):
            await middleware.authenticate_request(credentials)


class TestAuthMiddlewareIntegration:
    """Integration tests for authentication middleware."""

    @pytest.mark.asyncio
    async def test_full_authentication_flow(self):
        """Test complete authentication flow through middleware."""
        # Setup JWT authenticator
        jwt_auth = JWTAuthenticator(
            secret_key="integration_secret",
            access_token_expire_minutes=30,
        )
        middleware = AuthMiddleware(jwt_auth)

        # Create token
        token = jwt_auth.create_access_token(
            user_id="integration_user",
            scopes=["read", "write", "admin"],
        )

        # Authenticate via middleware
        session_id = "integration_session"
        context = await middleware.authenticate_request({"token": token}, session_id)

        assert context.user_id == "integration_user"
        assert set(context.scopes) == {"read", "write", "admin"}

        # Validate session exists
        sessions = middleware.list_sessions()
        assert len(sessions) == 1

        # Validate session
        validated = await middleware.validate_session(session_id)
        assert validated is not None
        assert validated.user_id == "integration_user"

        # Invalidate session
        result = await middleware.invalidate_session(session_id)
        assert result is True

        # Should be gone
        assert len(middleware._contexts) == 0

    @pytest.mark.asyncio
    async def test_multi_user_sessions(self):
        """Test multiple users with separate sessions."""
        authenticator = APIKeyAuthenticator()

        # Create keys for different users
        key1 = authenticator.generate_api_key()
        key2 = authenticator.generate_api_key()

        authenticator.add_api_key(key1, "user1", scopes=["read"])
        authenticator.add_api_key(key2, "user2", scopes=["write"])

        middleware = AuthMiddleware(authenticator)

        # Authenticate both users
        context1 = await middleware.authenticate_request({"api_key": key1}, "session1")
        context2 = await middleware.authenticate_request({"api_key": key2}, "session2")

        assert context1.user_id == "user1"
        assert context2.user_id == "user2"

        # Should have 2 sessions
        assert len(middleware._contexts) == 2

        # List sessions
        sessions = middleware.list_sessions()
        assert len(sessions) == 2

        user_ids = [s["user_id"] for s in sessions]
        assert "user1" in user_ids
        assert "user2" in user_ids


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
