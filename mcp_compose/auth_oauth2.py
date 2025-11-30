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


# ============================================================================
# Generic OAuth2 Token Validation
# ============================================================================
# The following classes support validating existing OAuth2 tokens
# (as opposed to the OAuth2 authorization flow above)


class GenericOAuth2TokenValidator:
    """
    Generic OAuth2 token validator.
    
    Validates access tokens by:
    1. Token introspection (RFC 7662) - if introspection_endpoint is configured
    2. UserInfo endpoint call - if userinfo_endpoint is configured
    3. OIDC discovery - if issuer_url is configured (auto-discovers endpoints)
    
    This is designed for server-side token validation where mcp-compose
    receives bearer tokens from clients and needs to validate them with
    the OAuth2/OIDC provider.
    """
    
    def __init__(
        self,
        issuer_url: Optional[str] = None,
        userinfo_endpoint: Optional[str] = None,
        introspection_endpoint: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        audience: Optional[str] = None,
        required_scopes: Optional[list[str]] = None,
        user_id_claim: str = "sub",
    ):
        """
        Initialize the token validator.
        
        Args:
            issuer_url: OIDC issuer URL for auto-discovery (e.g., "https://accounts.google.com").
                If provided, will fetch /.well-known/openid-configuration to discover endpoints.
            userinfo_endpoint: Direct URL to userinfo endpoint.
                Falls back to discovered endpoint if issuer_url is provided.
            introspection_endpoint: Direct URL to token introspection endpoint (RFC 7662).
                Used for validating tokens when available.
            client_id: Client ID for introspection requests (if required by provider).
            client_secret: Client secret for introspection requests (if required by provider).
            audience: Expected audience claim (for token validation).
            required_scopes: List of scopes that must be present in the token.
            user_id_claim: Claim to use for user ID extraction (default: "sub").
        """
        if not HTTPX_AVAILABLE:
            raise ImportError(
                "httpx is required for OAuth2 token validation. "
                "Install with: pip install httpx"
            )
        
        self.issuer_url = issuer_url.rstrip('/') if issuer_url else None
        self._userinfo_endpoint = userinfo_endpoint
        self._introspection_endpoint = introspection_endpoint
        self.client_id = client_id
        self.client_secret = client_secret
        self.audience = audience
        self.required_scopes = required_scopes or []
        self.user_id_claim = user_id_claim
        
        # Cache for discovered metadata
        self._discovery_cache: Optional[Dict[str, Any]] = None
        
        # Token cache for avoiding repeated validation calls
        self._token_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl_seconds = 300  # 5 minutes
    
    async def _discover_metadata(self) -> Dict[str, Any]:
        """
        Fetch OIDC discovery metadata from issuer.
        
        Returns:
            Discovery metadata dictionary.
        """
        if self._discovery_cache:
            return self._discovery_cache
        
        if not self.issuer_url:
            return {}
        
        discovery_url = f"{self.issuer_url}/.well-known/openid-configuration"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(discovery_url, timeout=10)
                response.raise_for_status()
                self._discovery_cache = response.json()
                logger.info(f"Discovered OIDC metadata from {discovery_url}")
                return self._discovery_cache
        except Exception as e:
            logger.warning(f"Failed to discover OIDC metadata from {discovery_url}: {e}")
            return {}
    
    async def get_userinfo_endpoint(self) -> Optional[str]:
        """Get the userinfo endpoint URL."""
        if self._userinfo_endpoint:
            return self._userinfo_endpoint
        
        metadata = await self._discover_metadata()
        return metadata.get("userinfo_endpoint")
    
    async def get_introspection_endpoint(self) -> Optional[str]:
        """Get the token introspection endpoint URL."""
        if self._introspection_endpoint:
            return self._introspection_endpoint
        
        metadata = await self._discover_metadata()
        return metadata.get("introspection_endpoint")
    
    async def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate an access token and return user information.
        
        Tries introspection first (if available), then falls back to userinfo.
        
        Args:
            token: The access token to validate.
        
        Returns:
            Dictionary with user information including:
            - user_id: The user identifier
            - active: Whether the token is active (for introspection)
            - scopes: Token scopes (if available)
            - raw: Raw response from the provider
        
        Raises:
            AuthenticationError: If token validation fails.
        """
        # Check cache first
        cache_key = hashlib.sha256(token.encode()).hexdigest()[:16]
        if cache_key in self._token_cache:
            cached = self._token_cache[cache_key]
            if cached.get("cached_at", 0) + self._cache_ttl_seconds > datetime.utcnow().timestamp():
                logger.debug(f"Using cached token validation for {cache_key}")
                return cached["data"]
        
        # Try introspection first
        introspection_endpoint = await self.get_introspection_endpoint()
        if introspection_endpoint:
            try:
                result = await self._introspect_token(token, introspection_endpoint)
                self._cache_result(cache_key, result)
                return result
            except Exception as e:
                logger.debug(f"Introspection failed, falling back to userinfo: {e}")
        
        # Fall back to userinfo endpoint
        userinfo_endpoint = await self.get_userinfo_endpoint()
        if userinfo_endpoint:
            result = await self._get_userinfo(token, userinfo_endpoint)
            self._cache_result(cache_key, result)
            return result
        
        raise AuthenticationError(
            "No token validation method available. "
            "Configure userinfo_endpoint, introspection_endpoint, or issuer_url."
        )
    
    async def _introspect_token(
        self, token: str, endpoint: str
    ) -> Dict[str, Any]:
        """
        Validate token using RFC 7662 introspection.
        
        Args:
            token: The access token to validate.
            endpoint: The introspection endpoint URL.
        
        Returns:
            Token information dictionary.
        """
        data = {"token": token}
        headers = {"Accept": "application/json"}
        
        # Add client credentials if available
        auth = None
        if self.client_id and self.client_secret:
            auth = httpx.BasicAuth(self.client_id, self.client_secret)
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    endpoint,
                    data=data,
                    headers=headers,
                    auth=auth,
                    timeout=10,
                )
                response.raise_for_status()
                result = response.json()
                
                # Check if token is active
                if not result.get("active", True):
                    raise InvalidCredentialsError("Token is not active")
                
                # Extract user ID
                user_id = result.get(self.user_id_claim) or result.get("username", "")
                
                # Extract scopes
                scope_str = result.get("scope", "")
                scopes = scope_str.split() if isinstance(scope_str, str) else []
                
                # Check required scopes
                self._check_required_scopes(scopes)
                
                return {
                    "user_id": user_id,
                    "active": True,
                    "scopes": scopes,
                    "raw": result,
                }
        except InvalidCredentialsError:
            raise
        except Exception as e:
            logger.error(f"Token introspection failed: {e}")
            raise AuthenticationError(f"Token introspection failed: {e}")
    
    async def _get_userinfo(self, token: str, endpoint: str) -> Dict[str, Any]:
        """
        Get user info using the access token.
        
        Args:
            token: The access token.
            endpoint: The userinfo endpoint URL.
        
        Returns:
            User information dictionary.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/json",
                    },
                    timeout=10,
                )
                
                if response.status_code == 401:
                    raise InvalidCredentialsError("Invalid or expired token")
                
                response.raise_for_status()
                result = response.json()
                
                # Extract user ID
                user_id = result.get(self.user_id_claim) or result.get("email", "")
                
                if not user_id:
                    logger.warning(f"Could not extract user ID from userinfo response: {result.keys()}")
                    user_id = "unknown"
                
                return {
                    "user_id": user_id,
                    "active": True,
                    "scopes": [],  # Userinfo doesn't return scopes
                    "raw": result,
                }
        except InvalidCredentialsError:
            raise
        except Exception as e:
            logger.error(f"Userinfo request failed: {e}")
            raise AuthenticationError(f"Userinfo request failed: {e}")
    
    def _check_required_scopes(self, scopes: list[str]) -> None:
        """Check if all required scopes are present."""
        if not self.required_scopes:
            return
        
        missing = [s for s in self.required_scopes if s not in scopes]
        if missing:
            raise InvalidCredentialsError(
                f"Token missing required scopes: {', '.join(missing)}"
            )
    
    def _cache_result(self, cache_key: str, result: Dict[str, Any]) -> None:
        """Cache a validation result."""
        self._token_cache[cache_key] = {
            "data": result,
            "cached_at": datetime.utcnow().timestamp(),
        }
        
        # Clean old entries (simple LRU-like cleanup)
        if len(self._token_cache) > 1000:
            # Remove oldest entries
            sorted_keys = sorted(
                self._token_cache.keys(),
                key=lambda k: self._token_cache[k].get("cached_at", 0)
            )
            for key in sorted_keys[:500]:
                del self._token_cache[key]
    
    def clear_cache(self) -> None:
        """Clear the token cache."""
        self._token_cache.clear()
        self._discovery_cache = None


class GenericOAuth2TokenAuthenticator(Authenticator):
    """
    Authenticator that validates OAuth2 tokens using GenericOAuth2TokenValidator.
    
    This is designed for use with mcp-compose where clients send bearer tokens
    and the composer validates them with the OAuth2 provider.
    
    Example configuration in mcp_compose.toml:
    
        [authentication]
        enabled = true
        providers = ["oauth2"]
        default_provider = "oauth2"
        
        [authentication.oauth2]
        provider = "generic"
        issuer_url = "https://id.anaconda.com"
        # Or provide explicit endpoints:
        # userinfo_endpoint = "https://id.anaconda.com/userinfo"
        # introspection_endpoint = "https://id.anaconda.com/oauth/introspect"
        client_id = "your-client-id"          # Optional, for introspection
        client_secret = "your-client-secret"  # Optional, for introspection
        user_id_claim = "sub"                 # Claim to use for user ID
    """
    
    def __init__(
        self,
        issuer_url: Optional[str] = None,
        userinfo_endpoint: Optional[str] = None,
        introspection_endpoint: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        audience: Optional[str] = None,
        required_scopes: Optional[list[str]] = None,
        user_id_claim: str = "sub",
    ):
        """
        Initialize the authenticator.
        
        See GenericOAuth2TokenValidator for parameter documentation.
        """
        super().__init__(AuthType.OAUTH2)
        
        self.validator = GenericOAuth2TokenValidator(
            issuer_url=issuer_url,
            userinfo_endpoint=userinfo_endpoint,
            introspection_endpoint=introspection_endpoint,
            client_id=client_id,
            client_secret=client_secret,
            audience=audience,
            required_scopes=required_scopes,
            user_id_claim=user_id_claim,
        )
    
    async def authenticate(self, credentials: Dict[str, Any]) -> AuthContext:
        """
        Authenticate using a bearer token.
        
        Args:
            credentials: Must contain "token" or "api_key" field with the bearer token.
        
        Returns:
            AuthContext for the authenticated user.
        
        Raises:
            InvalidCredentialsError: If token is invalid.
            AuthenticationError: If authentication fails.
        """
        # Extract token from credentials
        token = credentials.get("token") or credentials.get("api_key")
        if not token:
            raise InvalidCredentialsError("Bearer token not provided")
        
        # Validate the token
        result = await self.validator.validate_token(token)
        
        user_id = result.get("user_id", "unknown")
        scopes = result.get("scopes", [])
        
        logger.info(f"OAuth2 token validated for user: {user_id}")
        
        return AuthContext(
            user_id=user_id,
            auth_type=AuthType.OAUTH2,
            token=token,
            scopes=scopes if scopes else ["*"],  # Grant all scopes if not specified
            metadata={
                "raw_userinfo": result.get("raw", {}),
            },
        )
    
    async def validate(self, context: AuthContext) -> bool:
        """
        Validate an existing authentication context.
        
        Args:
            context: Authentication context to validate.
        
        Returns:
            True if valid, False otherwise.
        """
        if context.auth_type != AuthType.OAUTH2:
            return False
        
        if context.is_expired():
            return False
        
        if not context.token:
            return False
        
        # Re-validate the token
        try:
            await self.validator.validate_token(context.token)
            return True
        except Exception as e:
            logger.debug(f"Token re-validation failed: {e}")
            return False


def create_generic_oauth2_authenticator(
    issuer_url: Optional[str] = None,
    userinfo_endpoint: Optional[str] = None,
    introspection_endpoint: Optional[str] = None,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    audience: Optional[str] = None,
    required_scopes: Optional[list[str]] = None,
    user_id_claim: str = "sub",
    **kwargs
) -> GenericOAuth2TokenAuthenticator:
    """
    Factory function to create a generic OAuth2 token authenticator.
    
    This authenticator validates existing bearer tokens (as opposed to
    performing the OAuth2 authorization flow).
    
    Args:
        issuer_url: OIDC issuer URL for auto-discovery.
        userinfo_endpoint: Direct URL to userinfo endpoint.
        introspection_endpoint: Direct URL to token introspection endpoint.
        client_id: Client ID for introspection requests.
        client_secret: Client secret for introspection requests.
        audience: Expected audience claim.
        required_scopes: List of required scopes.
        user_id_claim: Claim to use for user ID (default: "sub").
        **kwargs: Ignored (for compatibility).
    
    Returns:
        GenericOAuth2TokenAuthenticator instance.
    """
    return GenericOAuth2TokenAuthenticator(
        issuer_url=issuer_url,
        userinfo_endpoint=userinfo_endpoint,
        introspection_endpoint=introspection_endpoint,
        client_id=client_id,
        client_secret=client_secret,
        audience=audience,
        required_scopes=required_scopes,
        user_id_claim=user_id_claim,
    )
