# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
HTTP client utilities for MCP Compose.

Provides compatibility wrapper for the MCP SDK's streamable HTTP client.
"""

from contextlib import asynccontextmanager

from mcp.client.streamable_http import streamable_http_client

from .mcp_compat import httpx_module


def streamable_http_client_compat(url, headers=None, timeout=30, verify=True):
    """
    Compatibility wrapper that provides the same interface as the deprecated
    streamablehttp_client but uses the non-deprecated streamable_http_client.

    This avoids the 5-minute SSE read timeout issue that causes connection pool
    corruption when tool handlers return quickly (inline 200 OK response path).

    See: https://github.com/modelcontextprotocol/python-sdk/issues/1941

    Args:
        url: The MCP server URL (e.g., "http://localhost:8080/mcp")
        headers: Optional dict of HTTP headers (e.g., {"Authorization": "Bearer ..."})
        timeout: Request timeout in seconds (default: 30)
        verify: SSL certificate verification (default: True). Set to False for localhost dev.

    Returns:
        Async context manager yielding (read_stream, write_stream, get_session_id)

    Usage:
        async with streamable_http_client_compat(
            url="http://localhost:8080/mcp",
            headers={"Authorization": "Bearer token"},
            timeout=30,
        ) as (read_stream, write_stream, get_session_id):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool("tool_name", {"arg": "value"})
    """

    @asynccontextmanager
    async def _context():
        # mcp 2.x transports take an httpx2 client, mcp 1.x an httpx one.
        async with httpx_module.AsyncClient(
            headers=headers,
            timeout=httpx_module.Timeout(float(timeout)),
            verify=verify,
        ) as http_client:
            async with streamable_http_client(
                url=url,
                http_client=http_client,
            ) as streams:
                if len(streams) == 2:
                    # mcp 2.x no longer yields get_session_id; keep the 3-tuple interface.
                    read_stream, write_stream = streams
                    yield read_stream, write_stream, lambda: None
                else:
                    yield streams

    return _context()
