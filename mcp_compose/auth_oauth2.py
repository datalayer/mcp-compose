"""
OAuth2 authentication for MCP Compose.

This module provides OAuth2 authentication with support for multiple providers.
"""

import hashlib
import secrets
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from urllib.parse import urlencode, parse_qs, urlparse

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from .auth import (
    AuthContext,
    AuthType,
    Authenticator,
    AuthenticationError,
    InvalidCredentialsError,
    ExpiredTokenError,
)

logger = logging.getLogger(__name__)


class OAuth2Provider(ABC):
    """
    Abstract base class for OAuth2 providers.
    
    Providers must implement authorization URL generation, token exchange,
    and token refresh logic.
    """
    
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scopes: Optional[list[str]] = None,
    ):
        """
        Initialize OAuth2 provider.
        
        Args:
            client_id: OAuth2 client ID.
            client_secret: OAuth2 client secret.
            redirect_uri: Redirect URI for OAuth2 flow.
            scopes: List of OAuth2 scopes to request.
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes or []
        
        if not HTTPX_AVAILABLE:
            raise ImportError(
                "httpx is required for OAuth2 authentication. "
                "Install with: pip install httpx"
            )
    
    @property
    @abstractmethod
    def authorization_endpoint(self) -> str:
        """Get the authorization endpoint URL."""
        pass
    
    @property
    @abstractmethod
    def token_endpoint(self) -> str:
        """Get the token endpoint URL."""
        pass
    
    @property
    @abstractmethod
    def userinfo_endpoint(self) -> str:
        """Get the user info endpoint URL."""
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the provider name."""
        pass
    
    def generate_state(self) -> str:
        """
        Generate a random state parameter for CSRF protection.
        
        Returns:
            Random state string.
        """
        return secrets.token_urlsafe(32)
    
    def generate_pkce_pair(self) -> tuple[str, str]:
        """
        Generate PKCE code verifier and challenge.
        
        Returns:
            Tuple of (code_verifier, code_challenge).
        """
        code_verifier = secrets.token_urlsafe(32)
        code_challenge = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge_b64 = secrets.token_urlsafe(32)  # Base64URL encode
        return code_verifier, code_challenge_b64
    
    def build_authorization_url(
        self,
        state: Optional[str] = None,
        use_pkce: bool = True,
        extra_params: Optional[Dict[str, str]] = None,
    ) -> tuple[str, Optional[str], Optional[str]]:
        """
        Build OAuth2 authorization URL.
        
        Args:
            state: State parameter (generated if not provided).
            use_pkce: Whether to use PKCE flow.
            extra_params: Additional query parameters.
        
        Returns:
            Tuple of (authorization_url, state, code_verifier).
        """
        state = state or self.generate_state()
        code_verifier = None
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": state,
        }
        
        if self.scopes:
            params["scope"] = " ".join(self.scopes)
        
        if use_pkce:
            code_verifier, code_challenge = self.generate_pkce_pair()
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
        
        if extra_params:
            params.update(extra_params)
        
        url = f"{self.authorization_endpoint}?{urlencode(params)}"
        return url, state, code_verifier
    
    async def exchange_code_for_token(
        self,
        code: str,
        code_verifier: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        
        Args:
            code: Authorization code from callback.
            code_verifier: PKCE code verifier (if using PKCE).
        
        Returns:
            Token response dictionary.
        
        Raises:
            AuthenticationError: If token exchange fails.
        """
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        
        if code_verifier:
            data["code_verifier"] = code_verifier
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.token_endpoint,
                    data=data,
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Token exchange failed: {e}")
            raise AuthenticationError(f"Failed to exchange code for token: {e}")
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh an access token using a refresh token.
        
        Args:
            refresh_token: Refresh token.
        
        Returns:
            Token response dictionary.
        
        Raises:
            AuthenticationError: If token refresh fails.
        """
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.token_endpoint,
                    data=data,
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            raise AuthenticationError(f"Failed to refresh token: {e}")
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get user information using access token.
        
        Args:
            access_token: OAuth2 access token.
        
        Returns:
            User information dictionary.
        
        Raises:
            AuthenticationError: If user info request fails.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.userinfo_endpoint,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/json",
                    },
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"User info request failed: {e}")
            raise AuthenticationError(f"Failed to get user info: {e}")
    
    @abstractmethod
    def extract_user_id(self, user_info: Dict[str, Any]) -> str:
        """
        Extract user ID from user info response.
        
        Args:
            user_info: User info dictionary from provider.
        
        Returns:
            User ID string.
        """
        pass
    
    def extract_scopes(self, token_response: Dict[str, Any]) -> list[str]:
        """
        Extract scopes from token response.
        
        Args:
            token_response: Token response dictionary.
        
        Returns:
            List of scopes.
        """
        scope_str = token_response.get("scope", "")
        if isinstance(scope_str, str):
            return scope_str.split() if scope_str else []
        return scope_str if isinstance(scope_str, list) else []


class GoogleOAuth2Provider(OAuth2Provider):
    """Google OAuth2 provider implementation."""
    
    @property
    def authorization_endpoint(self) -> str:
        return "https://accounts.google.com/o/oauth2/v2/auth"
    
    @property
    def token_endpoint(self) -> str:
        return "https://oauth2.googleapis.com/token"
    
    @property
    def userinfo_endpoint(self) -> str:
        return "https://www.googleapis.com/oauth2/v2/userinfo"
    
    @property
    def provider_name(self) -> str:
        return "google"
    
    def extract_user_id(self, user_info: Dict[str, Any]) -> str:
        """Extract user ID from Google user info."""
        return user_info.get("id") or user_info.get("sub", "")


class GitHubOAuth2Provider(OAuth2Provider):
    """GitHub OAuth2 provider implementation."""
    
    @property
    def authorization_endpoint(self) -> str:
        return "https://github.com/login/oauth/authorize"
    
    @property
    def token_endpoint(self) -> str:
        return "https://github.com/login/oauth/access_token"
    
    @property
    def userinfo_endpoint(self) -> str:
        return "https://api.github.com/user"
    
    @property
    def provider_name(self) -> str:
        return "github"
    
    def extract_user_id(self, user_info: Dict[str, Any]) -> str:
        """Extract user ID from GitHub user info."""
        return str(user_info.get("id", ""))


class MicrosoftOAuth2Provider(OAuth2Provider):
    """Microsoft/Azure AD OAuth2 provider implementation."""
    
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        tenant: str = "common",
        scopes: Optional[list[str]] = None,
    ):
        """
        Initialize Microsoft OAuth2 provider.
        
        Args:
            client_id: OAuth2 client ID.
            client_secret: OAuth2 client secret.
            redirect_uri: Redirect URI.
            tenant: Azure AD tenant (default: "common").
            scopes: List of scopes.
        """
        super().__init__(client_id, client_secret, redirect_uri, scopes)
        self.tenant = tenant
    
    @property
    def authorization_endpoint(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0/authorize"
    
    @property
    def token_endpoint(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant}/oauth2/v2.0/token"
    
    @property
    def userinfo_endpoint(self) -> str:
        return "https://graph.microsoft.com/v1.0/me"
    
    @property
    def provider_name(self) -> str:
        return "microsoft"
    
    def extract_user_id(self, user_info: Dict[str, Any]) -> str:
        """Extract user ID from Microsoft user info."""
        return user_info.get("id", "")


class OAuth2Authenticator(Authenticator):
    """
    OAuth2 authenticator for MCP Compose.
    
    Supports multiple OAuth2 providers with PKCE flow.
    """
    
    def __init__(
        self,
        provider: OAuth2Provider,
        default_scopes: Optional[list[str]] = None,
    ):
        """
        Initialize OAuth2 authenticator.
        
        Args:
            provider: OAuth2 provider instance.
            default_scopes: Default scopes to grant to authenticated users.
        """
        super().__init__(AuthType.OAUTH2)
        self.provider = provider
        self.default_scopes = default_scopes or []
        self._pending_auth: Dict[str, Dict[str, Any]] = {}  # state -> auth data
    
    def start_authentication(
        self,
        use_pkce: bool = True,
        extra_params: Optional[Dict[str, str]] = None,
    ) -> tuple[str, str]:
        """
        Start OAuth2 authentication flow.
        
        Args:
            use_pkce: Whether to use PKCE.
            extra_params: Additional authorization parameters.
        
        Returns:
            Tuple of (authorization_url, state).
        """
        auth_url, state, code_verifier = self.provider.build_authorization_url(
            use_pkce=use_pkce,
            extra_params=extra_params,
        )
        
        # Store pending auth data
        self._pending_auth[state] = {
            "code_verifier": code_verifier,
            "timestamp": datetime.utcnow(),
        }
        
        logger.info(f"Started OAuth2 flow with {self.provider.provider_name}")
        return auth_url, state
    
    async def authenticate(self, credentials: Dict[str, Any]) -> AuthContext:
        """
        Complete OAuth2 authentication.
        
        Args:
            credentials: Must contain "code" and "state" from callback.
        
        Returns:
            AuthContext for authenticated user.
        
        Raises:
            AuthenticationError: If authentication fails.
        """
        code = credentials.get("code")
        state = credentials.get("state")
        
        if not code:
            raise InvalidCredentialsError("Authorization code not provided")
        if not state:
            raise InvalidCredentialsError("State parameter not provided")
        
        # Verify state and get code verifier
        auth_data = self._pending_auth.pop(state, None)
        if not auth_data:
            raise AuthenticationError("Invalid or expired state parameter")
        
        code_verifier = auth_data.get("code_verifier")
        
        # Exchange code for token
        token_response = await self.provider.exchange_code_for_token(
            code, code_verifier
        )
        
        access_token = token_response.get("access_token")
        if not access_token:
            raise AuthenticationError("No access token in response")
        
        # Get user info
        user_info = await self.provider.get_user_info(access_token)
        user_id = self.provider.extract_user_id(user_info)
        
        if not user_id:
            raise AuthenticationError("Could not extract user ID from user info")
        
        # Extract scopes
        provider_scopes = self.provider.extract_scopes(token_response)
        scopes = list(set(self.default_scopes + provider_scopes))
        
        # Calculate expiration
        expires_in = token_response.get("expires_in")
        expires_at = None
        if expires_in:
            expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in))
        
        # Build metadata
        metadata = {
            "provider": self.provider.provider_name,
            "access_token": access_token,
            "user_info": user_info,
        }
        
        refresh_token = token_response.get("refresh_token")
        if refresh_token:
            metadata["refresh_token"] = refresh_token
        
        logger.info(
            f"OAuth2 authentication successful for user {user_id} "
            f"via {self.provider.provider_name}"
        )
        
        return AuthContext(
            user_id=user_id,
            auth_type=AuthType.OAUTH2,
            token=access_token,
            scopes=scopes,
            metadata=metadata,
            expires_at=expires_at,
        )
    
    async def validate(self, context: AuthContext) -> bool:
        """
        Validate OAuth2 authentication context.
        
        Args:
            context: Authentication context to validate.
        
        Returns:
            True if valid, False otherwise.
        """
        if context.auth_type != AuthType.OAUTH2:
            return False
        
        if context.is_expired():
            return False
        
        # Could optionally verify token with provider
        # For now, just check expiration
        return True
    
    async def refresh(self, context: AuthContext) -> AuthContext:
        """
        Refresh OAuth2 access token.
        
        Args:
            context: Current authentication context.
        
        Returns:
            New AuthContext with refreshed token.
        
        Raises:
            AuthenticationError: If refresh fails.
        """
        if context.auth_type != AuthType.OAUTH2:
            raise AuthenticationError("Not an OAuth2 context")
        
        refresh_token = context.metadata.get("refresh_token")
        if not refresh_token:
            raise AuthenticationError("No refresh token available")
        
        # Refresh the token
        token_response = await self.provider.refresh_access_token(refresh_token)
        
        access_token = token_response.get("access_token")
        if not access_token:
            raise AuthenticationError("No access token in refresh response")
        
        # Calculate new expiration
        expires_in = token_response.get("expires_in")
        expires_at = None
        if expires_in:
            expires_at = datetime.utcnow() + timedelta(seconds=int(expires_in))
        
        # Update metadata
        new_metadata = context.metadata.copy()
        new_metadata["access_token"] = access_token
        
        new_refresh_token = token_response.get("refresh_token")
        if new_refresh_token:
            new_metadata["refresh_token"] = new_refresh_token
        
        logger.info(f"Refreshed OAuth2 token for user {context.user_id}")
        
        return AuthContext(
            user_id=context.user_id,
            auth_type=AuthType.OAUTH2,
            token=access_token,
            scopes=context.scopes,
            metadata=new_metadata,
            expires_at=expires_at,
        )
    
    def cleanup_expired_pending_auth(self, max_age_minutes: int = 10) -> int:
        """
        Clean up expired pending authentication requests.
        
        Args:
            max_age_minutes: Maximum age for pending auth requests.
        
        Returns:
            Number of expired requests removed.
        """
        cutoff = datetime.utcnow() - timedelta(minutes=max_age_minutes)
        expired = [
            state for state, data in self._pending_auth.items()
            if data["timestamp"] < cutoff
        ]
        
        for state in expired:
            del self._pending_auth[state]
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired pending auth requests")
        
        return len(expired)


def create_oauth2_authenticator(
    provider: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    scopes: Optional[list[str]] = None,
    **kwargs
) -> OAuth2Authenticator:
    """
    Factory function to create OAuth2 authenticator.
    
    Args:
        provider: Provider name ("google", "github", "microsoft").
        client_id: OAuth2 client ID.
        client_secret: OAuth2 client secret.
        redirect_uri: Redirect URI.
        scopes: OAuth2 scopes to request.
        **kwargs: Additional provider-specific arguments.
    
    Returns:
        OAuth2Authenticator instance.
    
    Raises:
        ValueError: If provider is not supported.
    """
    provider_lower = provider.lower()
    
    if provider_lower == "google":
        provider_instance = GoogleOAuth2Provider(
            client_id, client_secret, redirect_uri, scopes
        )
    elif provider_lower == "github":
        provider_instance = GitHubOAuth2Provider(
            client_id, client_secret, redirect_uri, scopes
        )
    elif provider_lower == "microsoft":
        tenant = kwargs.get("tenant", "common")
        provider_instance = MicrosoftOAuth2Provider(
            client_id, client_secret, redirect_uri, tenant, scopes
        )
    else:
        raise ValueError(f"Unsupported OAuth2 provider: {provider}")
    
    return OAuth2Authenticator(provider_instance)
