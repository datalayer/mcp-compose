# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Anaconda authentication for MCP Compose.

This module provides authentication using Anaconda bearer tokens.
"""

import logging
import os
from typing import Any

from ..auth import (
    AuthContext,
    Authenticator,
    AuthType,
    InvalidCredentialsError,
)

logger = logging.getLogger(__name__)


class AnacondaAuthenticator(Authenticator):
    """
    Anaconda authentication using anaconda-auth library.

    Validates bearer tokens by calling the Anaconda API.

    Supports fallback mode: If MCP_COMPOSE_ANACONDA_TOKEN="fallback",
    the authenticator will try to use a provided Bearer token first,
    and if not provided, will attempt to retrieve the token from the
    local anaconda_auth library.
    """

    def __init__(self, domain: str = "anaconda.com", fallback_mode: bool = False):
        """
        Initialize Anaconda authenticator.

        Args:
            domain: Anaconda domain (default: "anaconda.com").
                For enterprise, use your custom domain.
            fallback_mode: If True, allows fallback to local anaconda_auth
                token retrieval when no Bearer token is provided.
        """
        super().__init__(AuthType.API_KEY)  # Using API_KEY type for bearer tokens
        self.domain = domain

        # Check environment variable for fallback mode
        env_token = os.environ.get("MCP_COMPOSE_ANACONDA_TOKEN")
        self.fallback_mode = fallback_mode or (env_token == "fallback")

        if self.fallback_mode:
            logger.info("Anaconda authenticator initialized in fallback mode")

        # Try to import anaconda_auth
        try:
            from anaconda_auth.token import TokenInfo

            self._token_info_class = TokenInfo
        except ImportError:
            raise ImportError(
                "anaconda-auth is required for Anaconda authentication. "
                "Install with: pip install anaconda-auth"
            )

    async def authenticate(self, credentials: dict[str, Any]) -> AuthContext:
        """
        Authenticate using Anaconda bearer token.

        In fallback mode (MCP_COMPOSE_ANACONDA_TOKEN="fallback"):
        1. First tries to use provided Bearer token if present
        2. If no token provided, attempts to retrieve from local anaconda_auth
        3. If neither works, raises InvalidCredentialsError

        Args:
            credentials: May contain "api_key" or "token" field with the bearer token.

        Returns:
            AuthContext for the authenticated user.

        Raises:
            InvalidCredentialsError: If token is invalid or authentication fails.
        """
        # Extract token from credentials
        token = credentials.get("api_key") or credentials.get("token")

        # If no token provided and we're in fallback mode, try to get from anaconda_auth
        if not token and self.fallback_mode:
            logger.info("No token provided, attempting fallback to local anaconda_auth")
            token = self._get_local_token()
            if token:
                logger.info("Successfully retrieved token from local anaconda_auth")

        if not token:
            logger.warning("Anaconda token not provided in credentials")
            raise InvalidCredentialsError("Anaconda token not provided")

        try:
            # Validate with anaconda-auth
            logger.info(f"Validating Anaconda token with domain: {self.domain}")
            token_info = self._token_info_class(domain=self.domain, api_key=token)

            # Get access token - this validates the token with Anaconda servers
            access_token = token_info.get_access_token()

            if not access_token:
                logger.warning("Anaconda token validation returned no access token")
                raise InvalidCredentialsError("Invalid Anaconda token - validation failed")

            # Verify the access token is not empty
            if not access_token.strip():
                logger.warning("Anaconda token validation returned empty access token")
                raise InvalidCredentialsError("Invalid Anaconda token - empty access token")

            # Extract user information from token
            user_id = self._get_user_from_token(token_info)

            logger.info(f"Anaconda authentication successful for user: {user_id}")

            return AuthContext(
                user_id=user_id,
                auth_type=self.auth_type,
                token=token,
                scopes=["*"],  # Grant all scopes for valid Anaconda users
                metadata={
                    "domain": self.domain,
                    "access_token": access_token,
                },
            )
        except InvalidCredentialsError:
            # Re-raise our own exceptions
            raise
        except Exception as e:
            logger.error(f"Anaconda authentication failed: {type(e).__name__}: {e}")
            # Be more specific about the failure
            if "unauthorized" in str(e).lower() or "401" in str(e):
                raise InvalidCredentialsError("Invalid Anaconda token - unauthorized")
            elif "forbidden" in str(e).lower() or "403" in str(e):
                raise InvalidCredentialsError("Invalid Anaconda token - access forbidden")
            else:
                raise InvalidCredentialsError(f"Anaconda authentication failed: {e}")

    async def validate(self, context: AuthContext) -> bool:
        """
        Validate existing Anaconda authentication context.

        Args:
            context: Authentication context to validate.

        Returns:
            True if token is still valid, False otherwise.
        """
        if context.auth_type != self.auth_type:
            return False

        if not context.token:
            return False

        # Re-authenticate to check if token is still valid
        try:
            await self.authenticate({"token": context.token})
            return True
        except:
            logger.debug(f"Token validation failed for user: {context.user_id}")
            return False

    def _get_local_token(self) -> str | None:
        """
        Attempt to retrieve token from local anaconda_auth.

        Returns:
            Token string if found, None otherwise.
        """
        try:
            token_info = self._token_info_class(domain=self.domain)
            access_token = token_info.get_access_token()
            if access_token and access_token.strip():
                return access_token
        except Exception as e:
            logger.debug(f"Failed to retrieve local anaconda_auth token: {e}")
        return None

    def _get_user_from_token(self, token_info) -> str:
        """
        Extract user ID from token info.

        Args:
            token_info: TokenInfo instance from anaconda-auth.

        Returns:
            User ID string.
        """
        # Try to get username or user ID from token_info
        # The TokenInfo object may have different attributes depending on version
        if hasattr(token_info, "username") and token_info.username:
            return token_info.username
        elif hasattr(token_info, "user_id") and token_info.user_id:
            return str(token_info.user_id)
        elif hasattr(token_info, "email") and token_info.email:
            return token_info.email
        else:
            # Fallback to a generic user ID
            return "anaconda_user"


def create_anaconda_authenticator(
    domain: str = "anaconda.com", fallback_mode: bool = False, **kwargs
) -> AnacondaAuthenticator:
    """
    Factory function to create Anaconda authenticator.

    Args:
        domain: Anaconda domain (default: "anaconda.com").
        fallback_mode: If True, allows fallback to local anaconda_auth
            token retrieval when no Bearer token is provided.
        **kwargs: Additional arguments (for compatibility).

    Returns:
        AnacondaAuthenticator instance.
    """
    return AnacondaAuthenticator(domain=domain, fallback_mode=fallback_mode)
