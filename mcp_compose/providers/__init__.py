"""
Authentication providers for MCP Compose.

This package contains authentication provider implementations.
"""

from .auth_anaconda import AnacondaAuthenticator, create_anaconda_authenticator

__all__ = [
    "AnacondaAuthenticator",
    "create_anaconda_authenticator",
]
