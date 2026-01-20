"""
Tests for JWT authentication.
"""

import asyncio
from datetime import datetime, timedelta

import pytest

from mcp_compose.auth import (
    AuthContext,
    AuthType,
    ExpiredTokenError,
    InvalidCredentialsError,
)
from mcp_compose.auth_jwt import (
    JWTAuthenticator,
    create_jwt_authenticator,
)


class TestJWTAuthenticator:
    """Test JWT authentication."""
    
    def test_create_authenticator(self):
        """Test creating JWT authenticator."""
        auth = JWTAuthenticator(
            secret_key="test_secret",
            algorithm="HS256",
            access_token_expire_minutes=30,
        )
        
        assert auth.auth_type == AuthType.JWT
        assert auth.secret_key == "test_secret"
        assert auth.algorithm == "HS256"
        assert auth.access_token_expire_minutes == 30
    
    def test_create_access_token(self):
        """Test creating access token."""
        auth = JWTAuthenticator(secret_key="test_secret")
        
        token = auth.create_access_token(
            user_id="user123",
            scopes=["read", "write"],
            metadata={"ip": "127.0.0.1"},
        )
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 50
    
    def test_create_refresh_token(self):
        """Test creating refresh token."""
        auth = JWTAuthenticator(secret_key="test_secret")
        
        token = auth.create_refresh_token(user_id="user123")
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 50
    
    def test_decode_token(self):
        """Test decoding JWT token."""
        auth = JWTAuthenticator(secret_key="test_secret")
        
        token = auth.create_access_token(
            user_id="user123",
            scopes=["read"],
            metadata={"test": "value"},
        )
        
        payload = auth.decode_token(token)
        
        assert payload["sub"] == "user123"
        assert payload["type"] == "access"
        assert payload["scopes"] == ["read"]
        assert payload["metadata"] == {"test": "value"}
        assert "iat" in payload
        assert "exp" in payload
    
    def test_decode_expired_token(self):
        """Test decoding expired token."""
        auth = JWTAuthenticator(
            secret_key="test_secret",
            access_token_expire_minutes=0,  # Expire immediately
        )
        
        token = auth.create_access_token(
            user_id="user123",
            expires_delta=timedelta(seconds=-1),  # Already expired
        )
        
        with pytest.raises(ExpiredTokenError, match="Token has expired"):
            auth.decode_token(token)
    
    def test_decode_invalid_token(self):
        """Test decoding invalid token."""
        auth = JWTAuthenticator(secret_key="test_secret")
        
        with pytest.raises(InvalidCredentialsError, match="Invalid token"):
            auth.decode_token("invalid.token.here")
    
    def test_decode_with_wrong_secret(self):
        """Test decoding token with wrong secret."""
        auth1 = JWTAuthenticator(secret_key="secret1")
        auth2 = JWTAuthenticator(secret_key="secret2")
        
        token = auth1.create_access_token(user_id="user123")
        
        with pytest.raises(InvalidCredentialsError, match="Invalid token"):
            auth2.decode_token(token)
    
    @pytest.mark.asyncio
    async def test_authenticate_valid_token(self):
        """Test authentication with valid JWT."""
        auth = JWTAuthenticator(secret_key="test_secret")
        
        token = auth.create_access_token(
            user_id="user123",
            scopes=["read", "write"],
            metadata={"ip": "127.0.0.1"},
        )
        
        context = await auth.authenticate({"token": token})
        
        assert context.user_id == "user123"
        assert context.auth_type == AuthType.JWT
        assert context.token == token
        assert context.scopes == ["read", "write"]
        assert context.metadata == {"ip": "127.0.0.1"}
        assert context.expires_at is not None
        assert not context.is_expired()
    
    @pytest.mark.asyncio
    async def test_authenticate_expired_token(self):
        """Test authentication with expired token."""
        auth = JWTAuthenticator(secret_key="test_secret")
        
        token = auth.create_access_token(
            user_id="user123",
            expires_delta=timedelta(seconds=-1),
        )
        
        with pytest.raises(ExpiredTokenError):
            await auth.authenticate({"token": token})
    
    @pytest.mark.asyncio
    async def test_authenticate_refresh_token_as_access(self):
        """Test authenticating with refresh token (should fail)."""
        auth = JWTAuthenticator(secret_key="test_secret")
        
        token = auth.create_refresh_token(user_id="user123")
        
        with pytest.raises(InvalidCredentialsError, match="Invalid token type"):
            await auth.authenticate({"token": token})
    
    @pytest.mark.asyncio
    async def test_authenticate_missing_token(self):
        """Test authentication without token."""
        auth = JWTAuthenticator(secret_key="test_secret")
        
        with pytest.raises(InvalidCredentialsError, match="Token not provided"):
            await auth.authenticate({})
    
    @pytest.mark.asyncio
    async def test_validate_context(self):
        """Test validating JWT context."""
        auth = JWTAuthenticator(secret_key="test_secret")
        
        token = auth.create_access_token(user_id="user123")
        context = await auth.authenticate({"token": token})
        
        # Valid context
        is_valid = await auth.validate(context)
        assert is_valid
        
        # Invalid context (wrong token)
        context.token = "invalid_token"
        is_valid = await auth.validate(context)
        assert not is_valid
    
    @pytest.mark.asyncio
    async def test_refresh_token(self):
        """Test refreshing JWT token."""
        auth = JWTAuthenticator(
            secret_key="test_secret",
            access_token_expire_minutes=1,
        )
        
        # Create initial access token context
        access_token = auth.create_access_token(
            user_id="user123",
            scopes=["read", "write"],
        )
        context = await auth.authenticate({"token": access_token})
        
        # Create refresh token
        refresh_token = auth.create_refresh_token(user_id="user123")
        refresh_context = AuthContext(
            user_id="user123",
            auth_type=AuthType.JWT,
            token=refresh_token,
            scopes=["read", "write"],
        )
        
        # Refresh to get new access token
        new_context = await auth.refresh(refresh_context)
        
        assert new_context.user_id == "user123"
        assert new_context.auth_type == AuthType.JWT
        assert new_context.token != refresh_token
        assert new_context.scopes == ["read", "write"]
        
        # New token should be valid
        is_valid = await auth.validate(new_context)
        assert is_valid
    
    @pytest.mark.asyncio
    async def test_refresh_with_access_token_fails(self):
        """Test that refreshing with access token fails."""
        auth = JWTAuthenticator(secret_key="test_secret")
        
        access_token = auth.create_access_token(user_id="user123")
        context = AuthContext(
            user_id="user123",
            auth_type=AuthType.JWT,
            token=access_token,
        )
        
        with pytest.raises(InvalidCredentialsError, match="Not a refresh token"):
            await auth.refresh(context)
    
    def test_token_with_issuer_and_audience(self):
        """Test token with issuer and audience."""
        auth = JWTAuthenticator(
            secret_key="test_secret",
            issuer="mcp-compose",
            audience="mcp-client",
        )
        
        token = auth.create_access_token(user_id="user123")
        payload = auth.decode_token(token)
        
        assert payload["iss"] == "mcp-compose"
        assert payload["aud"] == "mcp-client"
    
    def test_custom_expiration(self):
        """Test token with custom expiration."""
        auth = JWTAuthenticator(secret_key="test_secret")
        
        # Create token with 1 hour expiration
        token = auth.create_access_token(
            user_id="user123",
            expires_delta=timedelta(hours=1),
        )
        
        payload = auth.decode_token(token)
        exp = datetime.fromtimestamp(payload["exp"])
        iat = datetime.fromtimestamp(payload["iat"])
        
        delta = exp - iat
        # Should be approximately 1 hour (allowing small variance)
        assert 3590 < delta.total_seconds() < 3610


class TestJWTAuthenticatorFactory:
    """Test JWT authenticator factory."""
    
    def test_create_jwt_authenticator(self):
        """Test creating JWT authenticator via factory."""
        auth = create_jwt_authenticator(
            secret_key="test_secret",
            algorithm="HS256",
            access_token_expire_minutes=15,
        )
        
        assert isinstance(auth, JWTAuthenticator)
        assert auth.secret_key == "test_secret"
        assert auth.algorithm == "HS256"
        assert auth.access_token_expire_minutes == 15


class TestJWTIntegration:
    """Integration tests for JWT authentication."""
    
    @pytest.mark.asyncio
    async def test_full_jwt_flow(self):
        """Test complete JWT authentication flow."""
        auth = JWTAuthenticator(
            secret_key="integration_test_secret",
            access_token_expire_minutes=30,
            refresh_token_expire_days=7,
        )
        
        # Create access token
        access_token = auth.create_access_token(
            user_id="user123",
            scopes=["read", "write", "admin"],
            metadata={"email": "user@example.com"},
        )
        
        # Authenticate with access token
        context = await auth.authenticate({"token": access_token})
        
        assert context.user_id == "user123"
        assert context.scopes == ["read", "write", "admin"]
        assert context.metadata == {"email": "user@example.com"}
        
        # Validate
        is_valid = await auth.validate(context)
        assert is_valid
        
        # Create refresh token
        refresh_token = auth.create_refresh_token(user_id="user123")
        
        # Wait a moment to ensure different timestamp
        await asyncio.sleep(0.1)
        
        # Use refresh token to get new access token
        refresh_context = AuthContext(
            user_id="user123",
            auth_type=AuthType.JWT,
            token=refresh_token,
            scopes=context.scopes,
            metadata=context.metadata,
        )
        
        new_context = await auth.refresh(refresh_context)
        
        # New token should be different but valid
        # (will be different due to timestamp difference)
        assert new_context.token != refresh_token
        
        is_valid = await auth.validate(new_context)
        assert is_valid
    
    @pytest.mark.asyncio
    async def test_token_expiration_flow(self):
        """Test token expiration handling."""
        from datetime import datetime
        
        auth = JWTAuthenticator(
            secret_key="expiration_test_secret",
            access_token_expire_minutes=0.03,  # 1.8 seconds
        )
        
        # Create token
        token = auth.create_access_token(
            user_id="user123",
            scopes=["read"],
        )
        
        # Token should be valid initially
        context = await auth.authenticate({"token": token})
        assert not context.is_expired()
        
        is_valid = await auth.validate(context)
        assert is_valid
        
        # Wait for expiration (2.5 seconds to be safe)
        await asyncio.sleep(2.5)
        
        # Check that current time is now past expiration
        now = datetime.utcnow()
        assert now > context.expires_at, f"Current time {now} should be after expiry {context.expires_at}"
        
        # Token should now be expired
        assert context.is_expired()
        
        # Validation should fail
        is_valid = await auth.validate(context)
        assert not is_valid
        
        # Authenticating with expired token should fail
        with pytest.raises(ExpiredTokenError):
            await auth.authenticate({"token": token})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
