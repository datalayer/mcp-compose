"""MCP Server Composer

A generic Python library for composing Model Context Protocol (MCP) servers
based on dependencies defined in pyproject.toml files.

This package enables automatic discovery and composition of MCP tools and prompts
from multiple MCP server packages, creating unified servers with combined capabilities.
"""

from .__version__ import __version__
from .composer import MCPServerComposer, ConflictResolution
from .discovery import MCPServerDiscovery, MCPServerInfo
from .exceptions import (
    MCPComposerError,
    MCPDiscoveryError,
    MCPImportError,
    MCPCompositionError,
    MCPToolConflictError,
    MCPPromptConflictError,
)

__all__ = [
    "MCPServerComposer",
    "ConflictResolution",
    "MCPServerDiscovery", 
    "MCPServerInfo",
    "MCPComposerError",
    "MCPDiscoveryError",
    "MCPImportError",
    "MCPCompositionError",
    "MCPToolConflictError",
    "MCPPromptConflictError",
    "__version__",
]
