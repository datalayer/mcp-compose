# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""Tests for OAuth2 authentication."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

from mcp_compose.auth import (
    AuthType,
    AuthenticationError,
    InvalidCredentialsError,
)
from mcp_compose.auth_oauth2 import (
    OAuth2Provider,
    GoogleOAuth2Provider,
    GitHubOAuth2Provider,
    MicrosoftOAuth2Provider,
    OAuth2Authenticator,
    create_oauth2_authenticator,
)


class TestOAuth2Provider:
    """Test OAuth2 provider base class."""
    
    def test_google_provider_endpoints(self):
        """Test Google provider endpoints."""
        provider = GoogleOAuth2Provider(
            client_id="test_client_id",
            client_secret="test_secret",
            redirect_uri="http://localhost:8000/callback",
            scopes=["email", "profile"],
        )
        
        assert provider.provider_name == "google"
        assert "accounts.google.com" in provider.authorization_endpoint
        assert "oauth2.googleapis.com" in provider.token_endpoint
        assert "googleapis.com" in provider.userinfo_endpoint
    
    def test_github_provider_endpoints(self):
        """Test GitHub provider endpoints."""
        provider = GitHubOAuth2Provider(
            client_id="test_client_id",
            client_secret="test_secret",
            redirect_uri="http://localhost:8000/callback",
            scopes=["user", "repo"],
        )
        
        assert provider.provider_name == "github"
        assert "github.com" in provider.authorization_endpoint
        assert "github.com" in provider.token_endpoint
        assert "api.github.com" in provider.userinfo_endpoint
    
    def test_microsoft_provider_endpoints(self):
        """Test Microsoft provider endpoints."""
        provider = MicrosoftOAuth2Provider(
            client_id="test_client_id",
            client_secret="test_secret",
            redirect_uri="http://localhost:8000/callback",
            tenant="common",
            scopes=["User.Read"],
        )
        
        assert provider.provider_name == "microsoft"
        assert "login.microsoftonline.com" in provider.authorization_endpoint
        assert "common" in provider.authorization_endpoint
        assert "graph.microsoft.com" in provider.userinfo_endpoint
    
    def test_generate_state(self):
        """Test state generation."""
        provider = GoogleOAuth2Provider(
            client_id="test_id",
            client_secret="test_secret",
            redirect_uri="http://localhost/callback",
        )
        
        state1 = provider.generate_state()
        state2 = provider.generate_state()
        
        # States should be different
        assert state1 != state2
        # States should be reasonably long
        assert len(state1) > 20
        assert len(state2) > 20
    
    def test_generate_pkce_pair(self):
        """Test PKCE generation."""
        provider = GoogleOAuth2Provider(
            client_id="test_id",
            client_secret="test_secret",
            redirect_uri="http://localhost/callback",
        )
        
        verifier, challenge = provider.generate_pkce_pair()
        
        assert verifier is not None
        assert challenge is not None
        assert len(verifier) > 20
        assert len(challenge) > 20
    
    def test_build_authorization_url(self):
        """Test authorization URL building."""
        provider = GoogleOAuth2Provider(
            client_id="my_client_id",
            client_secret="my_secret",
            redirect_uri="http://localhost:8000/callback",
            scopes=["email", "profile"],
        )
        
        url, state, code_verifier = provider.build_authorization_url()
        
        assert "accounts.google.com" in url
        assert "client_id=my_client_id" in url
        assert "redirect_uri=" in url
        assert "response_type=code" in url
        assert f"state={state}" in url
        assert "scope=email+profile" in url or "scope=email%20profile" in url
        assert "code_challenge=" in url
        assert code_verifier is not None
    
    def test_build_authorization_url_without_pkce(self):
        """Test authorization URL without PKCE."""
        provider = GoogleOAuth2Provider(
            client_id="my_client_id",
            client_secret="my_secret",
            redirect_uri="http://localhost:8000/callback",
        )
        
        url, state, code_verifier = provider.build_authorization_url(use_pkce=False)
        
        assert "code_challenge=" not in url
        assert code_verifier is None
    
    def test_build_authorization_url_with_extra_params(self):
        """Test authorization URL with extra parameters."""
        provider = GoogleOAuth2Provider(
            client_id="my_client_id",
            client_secret="my_secret",
            redirect_uri="http://localhost:8000/callback",
        )
        
        extra_params = {"access_type": "offline", "prompt": "consent"}
        url, state, code_verifier = provider.build_authorization_url(
            extra_params=extra_params
        )
        
        assert "access_type=offline" in url
        assert "prompt=consent" in url
    
    def test_extract_user_id_google(self):
        """Test extracting user ID from Google user info."""
        provider = GoogleOAuth2Provider(
            client_id="test_id",
            client_secret="test_secret",
            redirect_uri="http://localhost/callback",
        )
        
        user_info = {"id": "123456", "email": "user@example.com"}
        user_id = provider.extract_user_id(user_info)
        assert user_id == "123456"
        
        # Test with 'sub' field
        user_info = {"sub": "789012", "email": "user@example.com"}
        user_id = provider.extract_user_id(user_info)
        assert user_id == "789012"
    
    def test_extract_user_id_github(self):
        """Test extracting user ID from GitHub user info."""
        provider = GitHubOAuth2Provider(
            client_id="test_id",
            client_secret="test_secret",
            redirect_uri="http://localhost/callback",
        )
        
        user_info = {"id": 12345, "login": "testuser"}
        user_id = provider.extract_user_id(user_info)
        assert user_id == "12345"
    
    def test_extract_scopes(self):
        """Test extracting scopes from token response."""
        provider = GoogleOAuth2Provider(
            client_id="test_id",
            client_secret="test_secret",
            redirect_uri="http://localhost/callback",
        )
        
        # String format
        token_response = {"scope": "email profile openid"}
        scopes = provider.extract_scopes(token_response)
        assert scopes == ["email", "profile", "openid"]
        
        # List format
        token_response = {"scope": ["email", "profile"]}
        scopes = provider.extract_scopes(token_response)
        assert scopes == ["email", "profile"]
        
        # Empty
        token_response = {}
        scopes = provider.extract_scopes(token_response)
        assert scopes == []


class TestOAuth2Authenticator:
    """Test OAuth2 authenticator."""
    
    @pytest.fixture
    def google_provider(self):
        """Create a Google OAuth2 provider for testing."""
        return GoogleOAuth2Provider(
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="http://localhost:8000/callback",
            scopes=["email", "profile"],
        )
    
    @pytest.fixture
    def authenticator(self, google_provider):
        """Create an OAuth2 authenticator for testing."""
        return OAuth2Authenticator(
            provider=google_provider,
            default_scopes=["read", "write"],
        )
    
    def test_create_authenticator(self, google_provider):
        """Test creating OAuth2 authenticator."""
        auth = OAuth2Authenticator(google_provider)
        
        assert auth.auth_type == AuthType.OAUTH2
        assert auth.provider == google_provider
        assert auth.default_scopes == []
    
    def test_start_authentication(self, authenticator):
        """Test starting authentication flow."""
        url, state = authenticator.start_authentication()
        
        assert url is not None
        assert state is not None
        assert "accounts.google.com" in url
        assert state in authenticator._pending_auth
    
    def test_start_authentication_without_pkce(self, authenticator):
        """Test starting authentication without PKCE."""
        url, state = authenticator.start_authentication(use_pkce=False)
        
        assert url is not None
        assert "code_challenge=" not in url
        assert authenticator._pending_auth[state]["code_verifier"] is None
    
    @pytest.mark.asyncio
    async def test_authenticate_missing_code(self, authenticator):
        """Test authentication with missing code."""
        with pytest.raises(InvalidCredentialsError, match="code not provided"):
            await authenticator.authenticate({"state": "some_state"})
    
    @pytest.mark.asyncio
    async def test_authenticate_missing_state(self, authenticator):
        """Test authentication with missing state."""
        with pytest.raises(InvalidCredentialsError, match="State parameter"):
            await authenticator.authenticate({"code": "some_code"})
    
    @pytest.mark.asyncio
    async def test_authenticate_invalid_state(self, authenticator):
        """Test authentication with invalid state."""
        with pytest.raises(AuthenticationError, match="Invalid or expired state"):
            await authenticator.authenticate({
                "code": "some_code",
                "state": "invalid_state",
            })
    
    @pytest.mark.asyncio
    async def test_authenticate_success(self, authenticator):
        """Test successful authentication."""
        # Start auth flow to get valid state
        url, state = authenticator.start_authentication()
        
        # Mock the token exchange
        mock_token_response = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "expires_in": 3600,
            "scope": "email profile",
        }
        
        # Mock the user info
        mock_user_info = {
            "id": "123456",
            "email": "user@example.com",
            "name": "Test User",
        }
        
        with patch.object(
            authenticator.provider,
            'exchange_code_for_token',
            new=AsyncMock(return_value=mock_token_response)
        ), patch.object(
            authenticator.provider,
            'get_user_info',
            new=AsyncMock(return_value=mock_user_info)
        ):
            context = await authenticator.authenticate({
                "code": "test_code",
                "state": state,
            })
        
        assert context.user_id == "123456"
        assert context.auth_type == AuthType.OAUTH2
        assert context.token == "test_access_token"
        assert "read" in context.scopes
        assert "write" in context.scopes
        assert "email" in context.scopes
        assert "profile" in context.scopes
        assert context.metadata["provider"] == "google"
        assert context.metadata["refresh_token"] == "test_refresh_token"
        assert context.expires_at is not None
    
    @pytest.mark.asyncio
    async def test_authenticate_no_access_token(self, authenticator):
        """Test authentication with no access token in response."""
        url, state = authenticator.start_authentication()
        
        mock_token_response = {"error": "invalid_grant"}
        
        with patch.object(
            authenticator.provider,
            'exchange_code_for_token',
            new=AsyncMock(return_value=mock_token_response)
        ):
            with pytest.raises(AuthenticationError, match="No access token"):
                await authenticator.authenticate({
                    "code": "test_code",
                    "state": state,
                })
    
    @pytest.mark.asyncio
    async def test_validate_valid_context(self, authenticator):
        """Test validating a valid OAuth2 context."""
        url, state = authenticator.start_authentication()
        
        mock_token_response = {
            "access_token": "test_token",
            "expires_in": 3600,
        }
        
        mock_user_info = {"id": "123"}
        
        with patch.object(
            authenticator.provider,
            'exchange_code_for_token',
            new=AsyncMock(return_value=mock_token_response)
        ), patch.object(
            authenticator.provider,
            'get_user_info',
            new=AsyncMock(return_value=mock_user_info)
        ):
            context = await authenticator.authenticate({
                "code": "test_code",
                "state": state,
            })
        
        is_valid = await authenticator.validate(context)
        assert is_valid
    
    @pytest.mark.asyncio
    async def test_validate_expired_context(self, authenticator):
        """Test validating an expired context."""
        url, state = authenticator.start_authentication()
        
        mock_token_response = {
            "access_token": "test_token",
            "expires_in": -1,  # Already expired
        }
        
        mock_user_info = {"id": "123"}
        
        with patch.object(
            authenticator.provider,
            'exchange_code_for_token',
            new=AsyncMock(return_value=mock_token_response)
        ), patch.object(
            authenticator.provider,
            'get_user_info',
            new=AsyncMock(return_value=mock_user_info)
        ):
            context = await authenticator.authenticate({
                "code": "test_code",
                "state": state,
            })
        
        is_valid = await authenticator.validate(context)
        assert not is_valid
    
    @pytest.mark.asyncio
    async def test_refresh_token(self, authenticator):
        """Test refreshing OAuth2 token."""
        url, state = authenticator.start_authentication()
        
        mock_token_response = {
            "access_token": "old_token",
            "refresh_token": "refresh_token",
            "expires_in": 3600,
        }
        
        mock_user_info = {"id": "123"}
        
        with patch.object(
            authenticator.provider,
            'exchange_code_for_token',
            new=AsyncMock(return_value=mock_token_response)
        ), patch.object(
            authenticator.provider,
            'get_user_info',
            new=AsyncMock(return_value=mock_user_info)
        ):
            context = await authenticator.authenticate({
                "code": "test_code",
                "state": state,
            })
        
        # Mock refresh response
        mock_refresh_response = {
            "access_token": "new_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
        }
        
        with patch.object(
            authenticator.provider,
            'refresh_access_token',
            new=AsyncMock(return_value=mock_refresh_response)
        ):
            new_context = await authenticator.refresh(context)
        
        assert new_context.token == "new_token"
        assert new_context.metadata["refresh_token"] == "new_refresh_token"
        assert new_context.user_id == context.user_id
    
    @pytest.mark.asyncio
    async def test_refresh_without_refresh_token(self, authenticator):
        """Test refresh without refresh token."""
        url, state = authenticator.start_authentication()
        
        mock_token_response = {
            "access_token": "token",
            "expires_in": 3600,
            # No refresh_token
        }
        
        mock_user_info = {"id": "123"}
        
        with patch.object(
            authenticator.provider,
            'exchange_code_for_token',
            new=AsyncMock(return_value=mock_token_response)
        ), patch.object(
            authenticator.provider,
            'get_user_info',
            new=AsyncMock(return_value=mock_user_info)
        ):
            context = await authenticator.authenticate({
                "code": "test_code",
                "state": state,
            })
        
        with pytest.raises(AuthenticationError, match="No refresh token"):
            await authenticator.refresh(context)
    
    def test_cleanup_expired_pending_auth(self, authenticator):
        """Test cleaning up expired pending auth requests."""
        # Add some pending auth requests
        old_timestamp = datetime.utcnow() - timedelta(minutes=15)
        recent_timestamp = datetime.utcnow() - timedelta(minutes=5)
        
        authenticator._pending_auth["old_state"] = {
            "code_verifier": "verifier1",
            "timestamp": old_timestamp,
        }
        authenticator._pending_auth["recent_state"] = {
            "code_verifier": "verifier2",
            "timestamp": recent_timestamp,
        }
        
        # Clean up with 10 minute threshold
        removed = authenticator.cleanup_expired_pending_auth(max_age_minutes=10)
        
        assert removed == 1
        assert "old_state" not in authenticator._pending_auth
        assert "recent_state" in authenticator._pending_auth


class TestOAuth2Factory:
    """Test OAuth2 authenticator factory."""
    
    def test_create_google_authenticator(self):
        """Test creating Google authenticator."""
        auth = create_oauth2_authenticator(
            provider="google",
            client_id="test_id",
            client_secret="test_secret",
            redirect_uri="http://localhost/callback",
            scopes=["email"],
        )
        
        assert isinstance(auth, OAuth2Authenticator)
        assert isinstance(auth.provider, GoogleOAuth2Provider)
        assert auth.provider.provider_name == "google"
    
    def test_create_github_authenticator(self):
        """Test creating GitHub authenticator."""
        auth = create_oauth2_authenticator(
            provider="github",
            client_id="test_id",
            client_secret="test_secret",
            redirect_uri="http://localhost/callback",
        )
        
        assert isinstance(auth, OAuth2Authenticator)
        assert isinstance(auth.provider, GitHubOAuth2Provider)
        assert auth.provider.provider_name == "github"
    
    def test_create_microsoft_authenticator(self):
        """Test creating Microsoft authenticator."""
        auth = create_oauth2_authenticator(
            provider="microsoft",
            client_id="test_id",
            client_secret="test_secret",
            redirect_uri="http://localhost/callback",
            tenant="organizations",
        )
        
        assert isinstance(auth, OAuth2Authenticator)
        assert isinstance(auth.provider, MicrosoftOAuth2Provider)
        assert auth.provider.provider_name == "microsoft"
        assert auth.provider.tenant == "organizations"
    
    def test_create_unsupported_provider(self):
        """Test creating authenticator with unsupported provider."""
        with pytest.raises(ValueError, match="Unsupported OAuth2 provider"):
            create_oauth2_authenticator(
                provider="unsupported",
                client_id="test_id",
                client_secret="test_secret",
                redirect_uri="http://localhost/callback",
            )


class TestOAuth2Integration:
    """Integration tests for OAuth2 authentication."""
    
    @pytest.mark.asyncio
    async def test_full_oauth2_flow(self):
        """Test complete OAuth2 authentication flow."""
        # Create authenticator
        provider = GoogleOAuth2Provider(
            client_id="integration_client_id",
            client_secret="integration_secret",
            redirect_uri="http://localhost:8000/callback",
            scopes=["email", "profile"],
        )
        
        auth = OAuth2Authenticator(
            provider=provider,
            default_scopes=["read"],
        )
        
        # Start flow
        url, state = auth.start_authentication()
        assert state in auth._pending_auth
        
        # Simulate callback
        mock_token_response = {
            "access_token": "integration_token",
            "refresh_token": "integration_refresh",
            "expires_in": 3600,
            "scope": "email profile",
        }
        
        mock_user_info = {
            "id": "integration_user_123",
            "email": "integration@example.com",
            "name": "Integration User",
        }
        
        with patch.object(
            provider,
            'exchange_code_for_token',
            new=AsyncMock(return_value=mock_token_response)
        ), patch.object(
            provider,
            'get_user_info',
            new=AsyncMock(return_value=mock_user_info)
        ):
            context = await auth.authenticate({
                "code": "integration_code",
                "state": state,
            })
        
        # Verify context
        assert context.user_id == "integration_user_123"
        assert context.auth_type == AuthType.OAUTH2
        assert context.token == "integration_token"
        assert set(context.scopes) >= {"read", "email", "profile"}
        
        # Validate
        is_valid = await auth.validate(context)
        assert is_valid
        
        # Refresh
        mock_refresh_response = {
            "access_token": "new_integration_token",
            "expires_in": 3600,
        }
        
        with patch.object(
            provider,
            'refresh_access_token',
            new=AsyncMock(return_value=mock_refresh_response)
        ):
            new_context = await auth.refresh(context)
        
        assert new_context.token == "new_integration_token"
        assert new_context.user_id == "integration_user_123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
