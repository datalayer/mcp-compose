# Copyright (c) 2023-2025 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Authentication providers for MCP Compose.

This package contains authentication provider implementations.
"""

from .auth_anaconda import AnacondaAuthenticator, create_anaconda_authenticator

__all__ = [
    "AnacondaAuthenticator",
    "create_anaconda_authenticator",
]
