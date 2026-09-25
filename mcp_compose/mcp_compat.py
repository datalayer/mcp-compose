# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Compatibility layer over the MCP Python SDK 1.x and 2.x.

mcp 2.x renamed ``mcp.server.fastmcp`` to ``mcp.server.mcpserver`` (``FastMCP``
became ``MCPServer``), moved its HTTP transports from ``httpx`` to ``httpx2``,
and exposes the protocol types with snake_case attributes (``input_schema``,
``client_info``) while keeping the camelCase wire aliases. Everything in
mcp-compose that depends on those differences goes through this module.
"""

from typing import Any

try:
    import httpx2 as httpx_module
    from mcp.server.mcpserver import Context
    from mcp.server.mcpserver import MCPServer as MCPServer
    from mcp.server.mcpserver.tools import ToolManager as SDKToolManager
    from mcp.server.mcpserver.tools.base import Tool
    from mcp.server.mcpserver.utilities.func_metadata import ArgModelBase

    MCP_V2 = True
except ImportError:
    import httpx as httpx_module  # type: ignore
    from mcp.server.fastmcp import Context  # type: ignore
    from mcp.server.fastmcp import FastMCP as MCPServer  # type: ignore
    from mcp.server.fastmcp.tools import ToolManager as SDKToolManager  # type: ignore
    from mcp.server.fastmcp.tools.base import Tool  # type: ignore
    from mcp.server.fastmcp.utilities.func_metadata import (  # type: ignore
        ArgModelBase,
    )

    MCP_V2 = False

__all__ = [
    "MCP_V2",
    "ArgModelBase",
    "Context",
    "MCPServer",
    "SDKToolManager",
    "Tool",
    "client_info_of",
    "httpx_module",
    "tool_input_schema",
]


def tool_input_schema(tool: Any) -> dict[str, Any]:
    """Return the input schema of an ``mcp.types.Tool`` (``input_schema`` in 2.x)."""
    schema = getattr(tool, "input_schema", None)
    if schema is None:
        schema = getattr(tool, "inputSchema", None)
    return schema or {}


def client_info_of(client_params: Any) -> Any:
    """Return the clientInfo of ``InitializeRequestParams`` (``client_info`` in 2.x)."""
    info = getattr(client_params, "client_info", None)
    if info is None:
        info = getattr(client_params, "clientInfo", None)
    return info
