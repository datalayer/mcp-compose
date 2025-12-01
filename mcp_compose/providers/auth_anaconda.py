"""
Anaconda authentication for MCP Compose.

This module provides authentication using Anaconda bearer tokens.
"""

import logging
from typing import Any, Dict

from ..auth import (
    AuthContext,
    AuthType,
    Authenticator,
    InvalidCredentialsError,
)

logger = logging.getLogger(__name__)


class AnacondaAuthenticator(Authenticator):
    """
    Anaconda authentication using anaconda-auth library.
    
    Validates bearer tokens by calling the Anaconda API.
    """
    
    def __init__(self, domain: str = "anaconda.com"):
        """
        Initialize Anaconda authenticator.
        
        Args:
            domain: Anaconda domain (default: "anaconda.com").
                For enterprise, use your custom domain.
        """
        super().__init__(AuthType.API_KEY)  # Using API_KEY type for bearer tokens
        self.domain = domain
        
        # Try to import anaconda_auth
        try:
            from anaconda_auth.token import TokenInfo
            self._token_info_class = TokenInfo
        except ImportError:
            raise ImportError(
                "anaconda-auth is required for Anaconda authentication. "
                "Install with: pip install anaconda-auth"
            )
    
    async def authenticate(self, credentials: Dict[str, Any]) -> AuthContext:
        """
        Authenticate using Anaconda bearer token.
        
        Args:
            credentials: Must contain "api_key" or "token" field with the bearer token.
        
        Returns:
            AuthContext for the authenticated user.
        
        Raises:
            InvalidCredentialsError: If token is invalid or authentication fails.
        """
        # Extract token from credentials
        token = credentials.get("api_key") or credentials.get("token")
        if not token:
            logger.warning("Anaconda token not provided in credentials")
            raise InvalidCredentialsError("Anaconda token not provided")
        
        try:
            # Validate with anaconda-auth
            logger.info(f"Validating Anaconda token with domain: {self.domain}")
            token_info = self._token_info_class(
                domain=self.domain,
                api_key=token
            )
            
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
        if hasattr(token_info, 'username') and token_info.username:
            return token_info.username
        elif hasattr(token_info, 'user_id') and token_info.user_id:
            return str(token_info.user_id)
        elif hasattr(token_info, 'email') and token_info.email:
            return token_info.email
        else:
            # Fallback to a generic user ID
            return "anaconda_user"


def create_anaconda_authenticator(
    domain: str = "anaconda.com",
    **kwargs
) -> AnacondaAuthenticator:
    """
    Factory function to create Anaconda authenticator.
    
    Args:
        domain: Anaconda domain (default: "anaconda.com").
        **kwargs: Additional arguments (for compatibility).
    
    Returns:
        AnacondaAuthenticator instance.
    """
    return AnacondaAuthenticator(domain=domain)
