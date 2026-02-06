#!/usr/bin/env python3
# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
OAuth Client for MCP Compose

This module provides OAuth clients for obtaining access tokens from various
OAuth2/OIDC providers. It supports the authorization code flow with PKCE.

Supported Providers:
- GitHub
- Anaconda (via anaconda-auth library)
- Generic OIDC providers

Usage:
    from mcp_compose.oauth_client import GitHubOAuthClient, AnacondaOAuthClient

    # GitHub OAuth
    client = GitHubOAuthClient(
        client_id="your-client-id",
        client_secret="your-client-secret",
    )
    token = client.get_token_interactive()

    # Anaconda OAuth
    client = AnacondaOAuthClient()
    token = client.get_token_interactive()
"""

import hashlib
import http.server
import logging
import secrets
import socketserver
import urllib.parse
import webbrowser
from abc import ABC, abstractmethod
from typing import Any

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logger = logging.getLogger(__name__)


class OAuthClient(ABC):
    """
    Abstract base class for OAuth clients.

    Provides common functionality for OAuth2 authorization code flow.
    """

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str = "http://localhost:8888/callback",
        scopes: list | None = None,
    ):
        """
        Initialize the OAuth client.

        Args:
            client_id: OAuth client ID (optional for some providers)
            client_secret: OAuth client secret (optional for some providers)
            redirect_uri: Callback URL for OAuth flow
            scopes: List of OAuth scopes to request
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes or []

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the provider name."""
        pass

    @abstractmethod
    def get_token_interactive(self) -> str:
        """
        Get access token via interactive OAuth flow.

        Returns:
            Access token string
        """
        pass

    @abstractmethod
    def get_user_info(self, access_token: str) -> dict[str, Any]:
        """
        Get user information using the access token.

        Args:
            access_token: OAuth access token

        Returns:
            User information dictionary
        """
        pass

    def generate_state(self) -> str:
        """Generate a random state parameter for CSRF protection."""
        return secrets.token_urlsafe(16)

    def generate_pkce_pair(self) -> tuple[str, str]:
        """
        Generate PKCE code verifier and challenge.

        Returns:
            Tuple of (code_verifier, code_challenge)
        """
        code_verifier = secrets.token_urlsafe(32)
        # SHA256 hash and base64url encode
        code_challenge_bytes = hashlib.sha256(code_verifier.encode()).digest()
        import base64

        code_challenge = base64.urlsafe_b64encode(code_challenge_bytes).rstrip(b"=").decode()
        return code_verifier, code_challenge


class GitHubOAuthClient(OAuthClient):
    """
    GitHub OAuth2 client.

    Implements the authorization code flow for GitHub OAuth Apps.

    Example:
        client = GitHubOAuthClient(
            client_id="your-client-id",
            client_secret="your-client-secret",
        )
        token = client.get_token_interactive()
        user = client.get_user_info(token)
        print(f"Authenticated as: {user['login']}")
    """

    AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    USER_URL = "https://api.github.com/user"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str = "http://localhost:8888/callback",
        scopes: list | None = None,
    ):
        """
        Initialize the GitHub OAuth client.

        Args:
            client_id: GitHub OAuth App client ID
            client_secret: GitHub OAuth App client secret
            redirect_uri: Callback URL (must match OAuth App settings)
            scopes: List of GitHub OAuth scopes (default: ["read:user"])
        """
        if not REQUESTS_AVAILABLE:
            raise ImportError(
                "requests is required for GitHub OAuth. Install with: pip install requests"
            )

        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scopes=scopes or ["read:user"],
        )

    @property
    def provider_name(self) -> str:
        return "github"

    def get_authorization_url(self, state: str | None = None) -> tuple[str, str]:
        """
        Build the GitHub authorization URL.

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            Tuple of (authorization_url, state)
        """
        state = state or self.generate_state()

        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.scopes),
            "state": state,
        }

        url = f"{self.AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"
        return url, state

    def exchange_code(self, code: str) -> str:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code from callback

        Returns:
            Access token string

        Raises:
            Exception: If token exchange fails
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
        }

        response = requests.post(
            self.TOKEN_URL,
            data=data,
            headers={"Accept": "application/json"},
            timeout=10,
        )

        if response.status_code != 200:
            raise Exception(f"Token exchange failed: {response.text}")

        result = response.json()

        if "error" in result:
            error_desc = result.get("error_description", result.get("error", "Unknown error"))
            raise Exception(f"Token exchange error: {error_desc}")

        access_token = result.get("access_token")
        if not access_token:
            raise Exception("No access_token in response")

        return access_token

    def get_user_info(self, access_token: str) -> dict[str, Any]:
        """
        Get user information from GitHub API.

        Args:
            access_token: GitHub access token

        Returns:
            User information dictionary
        """
        response = requests.get(
            self.USER_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            },
            timeout=10,
        )

        if response.status_code != 200:
            raise Exception(f"Failed to get user info: {response.text}")

        return response.json()

    def get_token_interactive(self) -> str:
        """
        Get access token via interactive browser-based OAuth flow.

        Opens the browser for user authentication, starts a local server
        to receive the callback, and exchanges the code for a token.

        Returns:
            Access token string
        """
        # Parse redirect URI to get port
        parsed = urllib.parse.urlparse(self.redirect_uri)
        port = parsed.port or 8080
        callback_path = parsed.path or "/callback"

        # Generate authorization URL
        auth_url, state = self.get_authorization_url()

        # Storage for the authorization code
        auth_code = None
        received_state = None

        class CallbackHandler(http.server.BaseHTTPRequestHandler):
            """HTTP handler for OAuth callback"""

            def log_message(self, format, *args):
                pass  # Suppress logging

            def do_GET(self):
                nonlocal auth_code, received_state

                # Parse query parameters
                query = urllib.parse.urlparse(self.path).query
                params = urllib.parse.parse_qs(query)

                if self.path.startswith(callback_path):
                    if "code" in params:
                        auth_code = params["code"][0]
                        received_state = params.get("state", [None])[0]

                        # Send success response
                        self.send_response(200)
                        self.send_header("Content-Type", "text/html")
                        self.end_headers()
                        self.wfile.write(b"""
                        <html>
                        <head><title>Authentication Successful</title></head>
                        <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                            <h1 style="color: green;">&#10004; Authentication Successful!</h1>
                            <p>You can close this window and return to the terminal.</p>
                        </body>
                        </html>
                        """)
                    elif "error" in params:
                        error = params.get("error", ["unknown"])[0]
                        error_desc = params.get("error_description", [""])[0]

                        self.send_response(400)
                        self.send_header("Content-Type", "text/html")
                        self.end_headers()
                        self.wfile.write(
                            f"""
                        <html>
                        <head><title>Authentication Failed</title></head>
                        <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                            <h1 style="color: red;">&#10008; Authentication Failed</h1>
                            <p>Error: {error}</p>
                            <p>{error_desc}</p>
                        </body>
                        </html>
                        """.encode()
                        )
                else:
                    self.send_response(404)
                    self.end_headers()

        # Start local server
        print(f"\n🌐 Starting local server on port {port}...")
        print("📋 Opening browser for GitHub authentication...")
        print(f"   URL: {auth_url[:80]}...")

        # Open browser
        webbrowser.open(auth_url)

        # Wait for callback
        with socketserver.TCPServer(("", port), CallbackHandler) as httpd:
            httpd.timeout = 120  # 2 minute timeout
            httpd.handle_request()

        # Verify we got a code
        if not auth_code:
            raise Exception("No authorization code received")

        # Verify state
        if received_state != state:
            raise Exception("State mismatch - possible CSRF attack")

        print("✅ Authorization code received")
        print("🔄 Exchanging code for access token...")

        # Exchange code for token
        access_token = self.exchange_code(auth_code)

        # Get user info to verify token
        user_info = self.get_user_info(access_token)
        print(f"✅ Authenticated as: {user_info.get('login', 'unknown')}")

        return access_token


class AnacondaOAuthClient(OAuthClient):
    """
    Anaconda OAuth client.

    Uses the anaconda-auth library for authentication. This provides
    a seamless experience for Anaconda Cloud users.

    Example:
        client = AnacondaOAuthClient()
        token = client.get_token_interactive()
        # Use token with MCP Compose
    """

    def __init__(
        self,
        domain: str = "anaconda.com",
        redirect_uri: str = "http://localhost:8888/callback",
    ):
        """
        Initialize the Anaconda OAuth client.

        Args:
            domain: Anaconda domain (default: "anaconda.com")
            redirect_uri: Callback URL (used for consistency, not actually used by anaconda-auth)
        """
        super().__init__(redirect_uri=redirect_uri)
        self.domain = domain

        # Try to import anaconda_auth
        try:
            from anaconda_auth import login
            from anaconda_auth.token import TokenInfo

            self._login = login
            self._token_info_class = TokenInfo
        except ImportError:
            raise ImportError(
                "anaconda-auth is required for Anaconda OAuth. "
                "Install with: pip install anaconda-auth"
            )

    @property
    def provider_name(self) -> str:
        return "anaconda"

    def get_user_info(self, access_token: str) -> dict[str, Any]:
        """
        Get user information from Anaconda.

        Note: This is limited compared to other providers since
        anaconda-auth doesn't expose a standard userinfo endpoint.

        Args:
            access_token: Anaconda access token

        Returns:
            User information dictionary (may be minimal)
        """
        # anaconda-auth doesn't provide a standard way to get user info
        # We return what we can from the token
        try:
            token_info = self._token_info_class(domain=self.domain, api_key=access_token)

            user_info = {}
            if hasattr(token_info, "username") and token_info.username:
                user_info["username"] = token_info.username
            if hasattr(token_info, "email") and token_info.email:
                user_info["email"] = token_info.email
            if hasattr(token_info, "user_id") and token_info.user_id:
                user_info["id"] = token_info.user_id

            return user_info or {"provider": "anaconda"}
        except Exception as e:
            logger.debug(f"Could not get user info from token: {e}")
            return {"provider": "anaconda"}

    def get_token_interactive(self) -> str:
        """
        Get access token via interactive Anaconda OAuth flow.

        Uses anaconda-auth's login() function which handles
        the OAuth flow including browser authentication.

        Returns:
            Access token string
        """
        print(f"\n🔐 Authenticating with Anaconda ({self.domain})...")

        # Use interactive login (opens browser)
        self._login()

        # Get access token
        token_info = self._token_info_class(domain=self.domain)
        access_token = token_info.get_access_token()

        if not access_token:
            raise Exception("Failed to get access token after login")

        print("✅ Successfully authenticated with Anaconda")

        return access_token

    def get_token_from_api_key(self, api_key: str) -> str:
        """
        Get access token using an existing API key.

        Args:
            api_key: Anaconda API key

        Returns:
            Access token string
        """
        token_info = self._token_info_class(domain=self.domain, api_key=api_key)
        access_token = token_info.get_access_token()

        if not access_token:
            raise Exception("Failed to get access token from API key")

        return access_token


class GenericOIDCClient(OAuthClient):
    """
    Generic OIDC client for any OAuth2/OIDC provider.

    Supports OIDC discovery to automatically configure endpoints.

    Example:
        client = GenericOIDCClient(
            issuer_url="https://id.example.com",
            client_id="your-client-id",
            client_secret="your-client-secret",
        )
        token = client.get_token_interactive()
    """

    def __init__(
        self,
        issuer_url: str | None = None,
        authorization_endpoint: str | None = None,
        token_endpoint: str | None = None,
        userinfo_endpoint: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str = "http://localhost:8888/callback",
        scopes: list | None = None,
    ):
        """
        Initialize the generic OIDC client.

        Args:
            issuer_url: OIDC issuer URL for auto-discovery
            authorization_endpoint: Direct authorization endpoint URL
            token_endpoint: Direct token endpoint URL
            userinfo_endpoint: Direct userinfo endpoint URL
            client_id: OAuth client ID
            client_secret: OAuth client secret
            redirect_uri: Callback URL
            scopes: List of OAuth scopes (default: ["openid", "profile"])
        """
        if not REQUESTS_AVAILABLE:
            raise ImportError(
                "requests is required for OIDC OAuth. Install with: pip install requests"
            )

        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scopes=scopes or ["openid", "profile"],
        )

        self.issuer_url = issuer_url.rstrip("/") if issuer_url else None
        self._authorization_endpoint = authorization_endpoint
        self._token_endpoint = token_endpoint
        self._userinfo_endpoint = userinfo_endpoint
        self._discovery_cache: dict[str, Any] | None = None

    @property
    def provider_name(self) -> str:
        return "oidc"

    def _discover_metadata(self) -> dict[str, Any]:
        """Fetch OIDC discovery metadata."""
        if self._discovery_cache:
            return self._discovery_cache

        if not self.issuer_url:
            return {}

        discovery_url = f"{self.issuer_url}/.well-known/openid-configuration"

        try:
            response = requests.get(discovery_url, timeout=10)
            response.raise_for_status()
            self._discovery_cache = response.json()
            logger.info(f"Discovered OIDC metadata from {discovery_url}")
            return self._discovery_cache
        except Exception as e:
            logger.warning(f"Failed to discover OIDC metadata: {e}")
            return {}

    @property
    def authorization_endpoint(self) -> str:
        if self._authorization_endpoint:
            return self._authorization_endpoint
        metadata = self._discover_metadata()
        endpoint = metadata.get("authorization_endpoint")
        if not endpoint:
            raise ValueError("No authorization_endpoint configured or discovered")
        return endpoint

    @property
    def token_endpoint(self) -> str:
        if self._token_endpoint:
            return self._token_endpoint
        metadata = self._discover_metadata()
        endpoint = metadata.get("token_endpoint")
        if not endpoint:
            raise ValueError("No token_endpoint configured or discovered")
        return endpoint

    @property
    def userinfo_endpoint(self) -> str | None:
        if self._userinfo_endpoint:
            return self._userinfo_endpoint
        metadata = self._discover_metadata()
        return metadata.get("userinfo_endpoint")

    def get_authorization_url(
        self,
        state: str | None = None,
        use_pkce: bool = True,
    ) -> tuple[str, str, str | None]:
        """
        Build the authorization URL.

        Args:
            state: Optional state parameter
            use_pkce: Whether to use PKCE

        Returns:
            Tuple of (authorization_url, state, code_verifier)
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

        url = f"{self.authorization_endpoint}?{urllib.parse.urlencode(params)}"
        return url, state, code_verifier

    def exchange_code(self, code: str, code_verifier: str | None = None) -> str:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code
            code_verifier: PKCE code verifier (if using PKCE)

        Returns:
            Access token string
        """
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
        }

        if self.client_secret:
            data["client_secret"] = self.client_secret

        if code_verifier:
            data["code_verifier"] = code_verifier

        response = requests.post(
            self.token_endpoint,
            data=data,
            headers={"Accept": "application/json"},
            timeout=10,
        )

        if response.status_code != 200:
            raise Exception(f"Token exchange failed: {response.text}")

        result = response.json()

        if "error" in result:
            error_desc = result.get("error_description", result.get("error", "Unknown error"))
            raise Exception(f"Token exchange error: {error_desc}")

        access_token = result.get("access_token")
        if not access_token:
            raise Exception("No access_token in response")

        return access_token

    def get_user_info(self, access_token: str) -> dict[str, Any]:
        """
        Get user information from the userinfo endpoint.

        Args:
            access_token: OAuth access token

        Returns:
            User information dictionary
        """
        endpoint = self.userinfo_endpoint
        if not endpoint:
            return {"provider": "oidc"}

        response = requests.get(
            endpoint,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=10,
        )

        if response.status_code != 200:
            raise Exception(f"Failed to get user info: {response.text}")

        return response.json()

    def get_token_interactive(self) -> str:
        """
        Get access token via interactive browser-based OAuth flow.

        Returns:
            Access token string
        """
        # Parse redirect URI to get port
        parsed = urllib.parse.urlparse(self.redirect_uri)
        port = parsed.port or 8080
        callback_path = parsed.path or "/callback"

        # Generate authorization URL with PKCE
        auth_url, state, code_verifier = self.get_authorization_url(use_pkce=True)

        # Storage for the authorization code
        auth_code = None
        received_state = None

        class CallbackHandler(http.server.BaseHTTPRequestHandler):
            """HTTP handler for OAuth callback"""

            def log_message(self, format, *args):
                pass

            def do_GET(self):
                nonlocal auth_code, received_state

                query = urllib.parse.urlparse(self.path).query
                params = urllib.parse.parse_qs(query)

                if self.path.startswith(callback_path):
                    if "code" in params:
                        auth_code = params["code"][0]
                        received_state = params.get("state", [None])[0]

                        self.send_response(200)
                        self.send_header("Content-Type", "text/html")
                        self.end_headers()
                        self.wfile.write(b"""
                        <html>
                        <head><title>Authentication Successful</title></head>
                        <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                            <h1 style="color: green;">&#10004; Authentication Successful!</h1>
                            <p>You can close this window and return to the terminal.</p>
                        </body>
                        </html>
                        """)
                    elif "error" in params:
                        error = params.get("error", ["unknown"])[0]
                        error_desc = params.get("error_description", [""])[0]

                        self.send_response(400)
                        self.send_header("Content-Type", "text/html")
                        self.end_headers()
                        self.wfile.write(
                            f"""
                        <html>
                        <head><title>Authentication Failed</title></head>
                        <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                            <h1 style="color: red;">&#10008; Authentication Failed</h1>
                            <p>Error: {error}</p>
                            <p>{error_desc}</p>
                        </body>
                        </html>
                        """.encode()
                        )
                else:
                    self.send_response(404)
                    self.end_headers()

        print(f"\n🌐 Starting local server on port {port}...")
        print("📋 Opening browser for authentication...")
        print(f"   URL: {auth_url[:80]}...")

        webbrowser.open(auth_url)

        with socketserver.TCPServer(("", port), CallbackHandler) as httpd:
            httpd.timeout = 120
            httpd.handle_request()

        if not auth_code:
            raise Exception("No authorization code received")

        if received_state != state:
            raise Exception("State mismatch - possible CSRF attack")

        print("✅ Authorization code received")
        print("🔄 Exchanging code for access token...")

        access_token = self.exchange_code(auth_code, code_verifier)

        # Try to get user info
        try:
            user_info = self.get_user_info(access_token)
            user_id = (
                user_info.get("sub") or user_info.get("email") or user_info.get("name", "unknown")
            )
            print(f"✅ Authenticated as: {user_id}")
        except Exception:
            print("✅ Authentication successful")

        return access_token


def get_oauth_client(
    provider: str,
    client_id: str | None = None,
    client_secret: str | None = None,
    redirect_uri: str = "http://localhost:8888/callback",
    **kwargs,
) -> OAuthClient:
    """
    Factory function to create an OAuth client.

    Args:
        provider: Provider name ("github", "anaconda", "oidc")
        client_id: OAuth client ID
        client_secret: OAuth client secret
        redirect_uri: Callback URL
        **kwargs: Additional provider-specific arguments

    Returns:
        OAuthClient instance

    Raises:
        ValueError: If provider is not supported
    """
    provider_lower = provider.lower()

    if provider_lower == "github":
        if not client_id or not client_secret:
            raise ValueError("GitHub OAuth requires client_id and client_secret")
        return GitHubOAuthClient(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scopes=kwargs.get("scopes"),
        )
    elif provider_lower == "anaconda":
        return AnacondaOAuthClient(
            domain=kwargs.get("domain", "anaconda.com"),
            redirect_uri=redirect_uri,
        )
    elif provider_lower in ("oidc", "generic"):
        return GenericOIDCClient(
            issuer_url=kwargs.get("issuer_url"),
            authorization_endpoint=kwargs.get("authorization_endpoint"),
            token_endpoint=kwargs.get("token_endpoint"),
            userinfo_endpoint=kwargs.get("userinfo_endpoint"),
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scopes=kwargs.get("scopes"),
        )
    else:
        raise ValueError(f"Unsupported OAuth provider: {provider}")


def get_github_token(
    client_id: str | None = None,
    client_secret: str | None = None,
    redirect_uri: str = "http://localhost:8888/callback",
    scopes: list | None = None,
) -> str:
    """
    Get a GitHub OAuth access token via interactive browser flow.

    This is a convenience function that creates a GitHubOAuthClient
    and performs the interactive OAuth flow.

    Args:
        client_id: GitHub OAuth App client ID (or set GITHUB_CLIENT_ID env var)
        client_secret: GitHub OAuth App client secret (or set GITHUB_CLIENT_SECRET env var)
        redirect_uri: OAuth callback URL
        scopes: List of GitHub scopes (default: ["user"])

    Returns:
        Access token string

    Raises:
        ValueError: If client_id or client_secret are not provided
    """
    import os

    client_id = client_id or os.environ.get("GITHUB_CLIENT_ID")
    client_secret = client_secret or os.environ.get("GITHUB_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise ValueError(
            "GitHub OAuth requires client_id and client_secret. "
            "Either pass them as arguments or set GITHUB_CLIENT_ID "
            "and GITHUB_CLIENT_SECRET environment variables."
        )

    client = GitHubOAuthClient(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scopes=scopes,
    )

    return client.get_token_interactive()


def get_anaconda_token(
    domain: str = "anaconda.com",
    redirect_uri: str = "http://localhost:8888/callback",
) -> str:
    """
    Get an Anaconda OAuth access token via interactive browser flow.

    This is a convenience function that creates an AnacondaOAuthClient
    and performs the interactive OAuth flow. If anaconda-auth is installed,
    it will use the native TokenInfo method.

    Args:
        domain: Anaconda domain (default: "anaconda.com")
        redirect_uri: OAuth callback URL

    Returns:
        Access token string
    """
    client = AnacondaOAuthClient(
        domain=domain,
        redirect_uri=redirect_uri,
    )

    return client.get_token_interactive()
