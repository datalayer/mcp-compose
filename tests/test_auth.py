"""
Tests for authentication system.
"""

import asyncio
from datetime import datetime, timedelta

import pytest

from mcp_compose.auth import (
    AuthContext,
    AuthType,
    APIKeyAuthenticator,
    NoAuthenticator,
    create_authenticator,
    AuthenticationError,
    InvalidCredentialsError,
    InsufficientScopesError,
)


class TestAuthContext:
    """Test AuthContext class."""
    
    def test_create_context(self):
        """Test creating authentication context."""
        context = AuthContext(
            user_id="user123",
            auth_type=AuthType.API_KEY,
            token="test_token",
            scopes=["read", "write"],
            metadata={"ip": "127.0.0.1"},
        )
        
        assert context.user_id == "user123"
        assert context.auth_type == AuthType.API_KEY
        assert context.token == "test_token"
        assert context.scopes == ["read", "write"]
        assert context.metadata == {"ip": "127.0.0.1"}
        assert context.authenticated_at is not None
        assert context.expires_at is None
    
    def test_context_with_expiry(self):
        """Test context with expiration."""
        expires_at = datetime.utcnow() + timedelta(hours=1)
        context = AuthContext(
            user_id="user123",
            auth_type=AuthType.JWT,
            expires_at=expires_at,
        )
        
        assert not context.is_expired()
        
        # Set expiry in the past
        context.expires_at = datetime.utcnow() - timedelta(hours=1)
        assert context.is_expired()
    
    def test_has_scope(self):
        """Test scope checking."""
        context = AuthContext(
            user_id="user123",
            auth_type=AuthType.API_KEY,
            scopes=["read", "write", "admin"],
        )
        
        assert context.has_scope("read")
        assert context.has_scope("write")
        assert context.has_scope("admin")
        assert not context.has_scope("delete")
    
    def test_to_dict(self):
        """Test converting context to dictionary."""
        expires_at = datetime.utcnow() + timedelta(hours=1)
        context = AuthContext(
            user_id="user123",
            auth_type=AuthType.JWT,
            token="token",
            scopes=["read"],
            expires_at=expires_at,
        )
        
        data = context.to_dict()
        
        assert data["user_id"] == "user123"
        assert data["auth_type"] == "jwt"
        assert data["token"] == "token"
        assert data["scopes"] == ["read"]
        assert data["expires_at"] is not None


class TestAPIKeyAuthenticator:
    """Test API Key authentication."""
    
    def test_generate_api_key(self):
        """Test API key generation."""
        key1 = APIKeyAuthenticator.generate_api_key()
        key2 = APIKeyAuthenticator.generate_api_key()
        
        assert len(key1) > 20
        assert len(key2) > 20
        assert key1 != key2
    
    def test_hash_api_key(self):
        """Test API key hashing."""
        key = "test_api_key_12345"
        hash1 = APIKeyAuthenticator.hash_api_key(key)
        hash2 = APIKeyAuthenticator.hash_api_key(key)
        
        assert hash1 == hash2
        assert hash1 != key
        assert len(hash1) == 64  # SHA-256 hex digest
    
    def test_add_and_remove_api_key(self):
        """Test adding and removing API keys."""
        auth = APIKeyAuthenticator()
        
        # Add key
        api_key = "test_key_123"
        key_hash = auth.add_api_key(
            api_key=api_key,
            user_id="user1",
            scopes=["read", "write"],
            metadata={"created": "2025-01-01"}
        )
        
        assert key_hash in auth.api_keys
        assert auth.api_keys[key_hash]["user_id"] == "user1"
        assert auth.api_keys[key_hash]["scopes"] == ["read", "write"]
        
        # Remove key
        removed = auth.remove_api_key(api_key)
        assert removed
        assert key_hash not in auth.api_keys
        
        # Try removing again
        removed = auth.remove_api_key(api_key)
        assert not removed
    
    @pytest.mark.asyncio
    async def test_authenticate_valid_key(self):
        """Test authentication with valid API key."""
        auth = APIKeyAuthenticator()
        api_key = "valid_key_123"
        
        auth.add_api_key(
            api_key=api_key,
            user_id="user1",
            scopes=["read", "write"],
        )
        
        context = await auth.authenticate({"api_key": api_key})
        
        assert context.user_id == "user1"
        assert context.auth_type == AuthType.API_KEY
        assert context.token == api_key
        assert context.scopes == ["read", "write"]
    
    @pytest.mark.asyncio
    async def test_authenticate_invalid_key(self):
        """Test authentication with invalid API key."""
        auth = APIKeyAuthenticator()
        
        with pytest.raises(InvalidCredentialsError, match="Invalid API key"):
            await auth.authenticate({"api_key": "invalid_key"})
    
    @pytest.mark.asyncio
    async def test_authenticate_missing_key(self):
        """Test authentication without API key."""
        auth = APIKeyAuthenticator()
        
        with pytest.raises(InvalidCredentialsError, match="API key not provided"):
            await auth.authenticate({})
    
    @pytest.mark.asyncio
    async def test_validate_context(self):
        """Test validating authentication context."""
        auth = APIKeyAuthenticator()
        api_key = "test_key"
        
        auth.add_api_key(api_key=api_key, user_id="user1")
        
        # Valid context
        context = AuthContext(
            user_id="user1",
            auth_type=AuthType.API_KEY,
            token=api_key,
        )
        
        is_valid = await auth.validate(context)
        assert is_valid
        
        # Invalid context (wrong token)
        context.token = "wrong_key"
        is_valid = await auth.validate(context)
        assert not is_valid
        
        # Invalid context (no token)
        context.token = None
        is_valid = await auth.validate(context)
        assert not is_valid


class TestNoAuthenticator:
    """Test no-auth authenticator."""
    
    @pytest.mark.asyncio
    async def test_authenticate_always_succeeds(self):
        """Test that no-auth always allows requests."""
        auth = NoAuthenticator()
        
        context = await auth.authenticate({})
        
        assert context.user_id == "anonymous"
        assert context.auth_type == AuthType.NONE
        assert context.scopes == ["*"]
    
    @pytest.mark.asyncio
    async def test_validate_always_succeeds(self):
        """Test that validation always succeeds."""
        auth = NoAuthenticator()
        
        context = AuthContext(
            user_id="anyone",
            auth_type=AuthType.NONE,
        )
        
        is_valid = await auth.validate(context)
        assert is_valid


class TestAuthenticatorFactory:
    """Test authenticator factory."""
    
    def test_create_api_key_authenticator(self):
        """Test creating API key authenticator."""
        api_keys = {"hash1": {"user_id": "user1", "scopes": [], "metadata": {}}}
        
        auth = create_authenticator(AuthType.API_KEY, api_keys=api_keys)
        
        assert isinstance(auth, APIKeyAuthenticator)
        assert auth.api_keys == api_keys
    
    def test_create_no_authenticator(self):
        """Test creating no-auth authenticator."""
        auth = create_authenticator(AuthType.NONE)
        
        assert isinstance(auth, NoAuthenticator)
    
    def test_create_unsupported_authenticator(self):
        """Test creating unsupported authenticator type."""
        with pytest.raises(ValueError, match="Unsupported auth type"):
            create_authenticator(AuthType.JWT)


class TestAuthenticationErrors:
    """Test authentication error classes."""
    
    def test_authentication_error(self):
        """Test base authentication error."""
        error = AuthenticationError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)
    
    def test_invalid_credentials_error(self):
        """Test invalid credentials error."""
        error = InvalidCredentialsError("Bad credentials")
        assert str(error) == "Bad credentials"
        assert isinstance(error, AuthenticationError)
    
    def test_insufficient_scopes_error(self):
        """Test insufficient scopes error."""
        error = InsufficientScopesError("Missing scope: admin")
        assert str(error) == "Missing scope: admin"
        assert isinstance(error, AuthenticationError)


class TestAuthContextIntegration:
    """Integration tests for auth context."""
    
    @pytest.mark.asyncio
    async def test_full_authentication_flow(self):
        """Test complete authentication flow."""
        # Setup authenticator
        auth = APIKeyAuthenticator()
        api_key = APIKeyAuthenticator.generate_api_key()
        
        auth.add_api_key(
            api_key=api_key,
            user_id="user123",
            scopes=["read", "write", "admin"],
            metadata={"email": "user@example.com"}
        )
        
        # Authenticate
        context = await auth.authenticate({"api_key": api_key})
        
        # Verify context
        assert context.user_id == "user123"
        assert context.has_scope("read")
        assert context.has_scope("write")
        assert context.has_scope("admin")
        assert not context.is_expired()
        
        # Validate
        is_valid = await auth.validate(context)
        assert is_valid
        
        # Remove key
        auth.remove_api_key(api_key)
        
        # Should no longer be valid
        is_valid = await auth.validate(context)
        assert not is_valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
