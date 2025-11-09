"""
JWT (JSON Web Token) authentication for MCP Server Composer.

This module provides JWT-based authentication with token generation,
validation, and refresh capabilities.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    jwt = None

from .auth import (
    AuthContext,
    AuthType,
    Authenticator,
    AuthenticationError,
    ExpiredTokenError,
    InvalidCredentialsError,
)

logger = logging.getLogger(__name__)


class JWTAuthenticator(Authenticator):
    """
    JWT-based authentication.
    
    Supports token generation, validation, and refresh with configurable
    expiration and signing algorithms.
    """
    
    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 30,
        refresh_token_expire_days: int = 7,
        issuer: Optional[str] = None,
        audience: Optional[str] = None,
    ):
        """
        Initialize JWT authenticator.
        
        Args:
            secret_key: Secret key for signing tokens.
            algorithm: JWT signing algorithm (HS256, RS256, etc.).
            access_token_expire_minutes: Access token expiration in minutes.
            refresh_token_expire_days: Refresh token expiration in days.
            issuer: Token issuer (optional).
            audience: Token audience (optional).
        
        Raises:
            ImportError: If PyJWT is not installed.
        """
        if not JWT_AVAILABLE:
            raise ImportError(
                "PyJWT is required for JWT authentication. "
                "Install it with: pip install PyJWT"
            )
        
        super().__init__(AuthType.JWT)
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days
        self.issuer = issuer
        self.audience = audience
    
    def create_access_token(
        self,
        user_id: str,
        scopes: Optional[list[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """
        Create a new access token.
        
        Args:
            user_id: User ID to encode in the token.
            scopes: List of scopes for this token.
            metadata: Additional metadata to include.
            expires_delta: Custom expiration time (overrides default).
        
        Returns:
            Encoded JWT token string.
        """
        if expires_delta is None:
            expires_delta = timedelta(minutes=self.access_token_expire_minutes)
        
        now = datetime.utcnow()
        expire = now + expires_delta
        
        payload = {
            "sub": user_id,
            "iat": now,
            "exp": expire,
            "type": "access",
            "scopes": scopes or [],
        }
        
        if self.issuer:
            payload["iss"] = self.issuer
        if self.audience:
            payload["aud"] = self.audience
        if metadata:
            payload["metadata"] = metadata
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token
    
    def create_refresh_token(
        self,
        user_id: str,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """
        Create a new refresh token.
        
        Args:
            user_id: User ID to encode in the token.
            expires_delta: Custom expiration time (overrides default).
        
        Returns:
            Encoded JWT refresh token string.
        """
        if expires_delta is None:
            expires_delta = timedelta(days=self.refresh_token_expire_days)
        
        now = datetime.utcnow()
        expire = now + expires_delta
        
        payload = {
            "sub": user_id,
            "iat": now,
            "exp": expire,
            "type": "refresh",
        }
        
        if self.issuer:
            payload["iss"] = self.issuer
        if self.audience:
            payload["aud"] = self.audience
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token
    
    def decode_token(self, token: str) -> Dict[str, Any]:
        """
        Decode and validate a JWT token.
        
        Args:
            token: JWT token string.
        
        Returns:
            Decoded token payload.
        
        Raises:
            ExpiredTokenError: If token has expired.
            InvalidCredentialsError: If token is invalid.
        """
        try:
            options = {}
            if self.issuer:
                options["verify_iss"] = True
            if self.audience:
                options["verify_aud"] = True
            
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                issuer=self.issuer,
                audience=self.audience,
                options=options,
            )
            return payload
            
        except jwt.ExpiredSignatureError:
            raise ExpiredTokenError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise InvalidCredentialsError(f"Invalid token: {str(e)}")
    
    async def authenticate(self, credentials: Dict[str, Any]) -> AuthContext:
        """
        Authenticate using a JWT token.
        
        Args:
            credentials: Must contain "token" field with JWT.
        
        Returns:
            AuthContext for the authenticated user.
        
        Raises:
            InvalidCredentialsError: If token is invalid.
            ExpiredTokenError: If token has expired.
        """
        token = credentials.get("token")
        if not token:
            raise InvalidCredentialsError("Token not provided")
        
        payload = self.decode_token(token)
        
        # Verify this is an access token
        if payload.get("type") != "access":
            raise InvalidCredentialsError("Invalid token type")
        
        user_id = payload.get("sub")
        if not user_id:
            raise InvalidCredentialsError("Token missing user ID")
        
        # Convert timestamp to datetime (use utcfromtimestamp to keep times in UTC)
        exp_timestamp = payload.get("exp")
        expires_at = datetime.utcfromtimestamp(exp_timestamp) if exp_timestamp else None
        
        iat_timestamp = payload.get("iat")
        authenticated_at = datetime.utcfromtimestamp(iat_timestamp) if iat_timestamp else datetime.utcnow()
        
        return AuthContext(
            user_id=user_id,
            auth_type=AuthType.JWT,
            token=token,
            scopes=payload.get("scopes", []),
            metadata=payload.get("metadata", {}),
            authenticated_at=authenticated_at,
            expires_at=expires_at,
        )
    
    async def validate(self, context: AuthContext) -> bool:
        """
        Validate a JWT authentication context.
        
        Args:
            context: Authentication context to validate.
        
        Returns:
            True if valid, False otherwise.
        """
        if context.auth_type != AuthType.JWT:
            return False
        
        if not context.token:
            return False
        
        if context.is_expired():
            return False
        
        try:
            self.decode_token(context.token)
            return True
        except AuthenticationError:
            return False
    
    async def refresh(self, context: AuthContext) -> AuthContext:
        """
        Refresh a JWT authentication context using a refresh token.
        
        Args:
            context: Existing authentication context with refresh token.
        
        Returns:
            New authentication context with fresh access token.
        
        Raises:
            InvalidCredentialsError: If refresh token is invalid.
        """
        if not context.token:
            raise InvalidCredentialsError("No token to refresh")
        
        try:
            payload = self.decode_token(context.token)
            
            # Verify this is a refresh token
            if payload.get("type") != "refresh":
                raise InvalidCredentialsError("Not a refresh token")
            
            user_id = payload.get("sub")
            if not user_id:
                raise InvalidCredentialsError("Token missing user ID")
            
            # Create new access token
            new_token = self.create_access_token(
                user_id=user_id,
                scopes=context.scopes,
                metadata=context.metadata,
            )
            
            # Decode to get new expiry
            new_payload = self.decode_token(new_token)
            exp_timestamp = new_payload.get("exp")
            expires_at = datetime.fromtimestamp(exp_timestamp) if exp_timestamp else None
            
            return AuthContext(
                user_id=user_id,
                auth_type=AuthType.JWT,
                token=new_token,
                scopes=context.scopes,
                metadata=context.metadata,
                expires_at=expires_at,
            )
            
        except AuthenticationError:
            raise
        except Exception as e:
            raise InvalidCredentialsError(f"Failed to refresh token: {str(e)}")


def create_jwt_authenticator(
    secret_key: str,
    **kwargs
) -> JWTAuthenticator:
    """
    Factory function to create a JWT authenticator.
    
    Args:
        secret_key: Secret key for signing tokens.
        **kwargs: Additional arguments for JWTAuthenticator.
    
    Returns:
        JWTAuthenticator instance.
    """
    return JWTAuthenticator(secret_key=secret_key, **kwargs)
