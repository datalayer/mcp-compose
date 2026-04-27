# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Tests for upstream clientInfo propagation through SSE and Streamable HTTP proxy paths.
"""

import asyncio

import pytest
import uvicorn
from mcp.server.fastmcp import Context, FastMCP
from mcp.types import Implementation


def _make_ctx(name: str = "test-agent", version: str = "2.0.0"):
    from unittest.mock import MagicMock

    info = Implementation(name=name, version=version)
    client_params = MagicMock()
    client_params.clientInfo = info
    session = MagicMock()
    session.client_params = client_params
    ctx = MagicMock()
    ctx.session = session
    return ctx


def _build_sub_server(port: int):
    received = {}
    sub = FastMCP("sub-server")

    @sub.tool()
    async def ping(ctx: Context) -> str:
        if ctx and ctx.session and ctx.session.client_params:
            received["name"] = ctx.session.client_params.clientInfo.name
            received["version"] = ctx.session.client_params.clientInfo.version
        return "pong"

    return sub, received


async def _start_uvicorn(app, port: int):
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    for _ in range(100):
        await asyncio.sleep(0.05)
        if server.started:
            break
    return server, task


class TestSseProxyClientInfo:
    @pytest.mark.asyncio
    async def test_sse_proxy_passes_upstream_client_info(self):
        port = 19201
        sub, received = _build_sub_server(port)
        userver, server_task = await _start_uvicorn(sub.sse_app(), port)

        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client

            sse_url = f"http://127.0.0.1:{port}/sse"
            ctx = _make_ctx(name="upstream-llm", version="4.2.0")

            async def sse_tool_proxy(ctx=None, **kwargs):
                from mcp_compose.client_info import resolve_client_info

                client_info = resolve_client_info(ctx)
                async with sse_client(sse_url) as (read, write):
                    async with ClientSession(read, write, client_info=client_info) as session:
                        await session.initialize()
                        result = await session.call_tool("ping", kwargs)
                        if hasattr(result, "content") and result.content:
                            for item in result.content:
                                if hasattr(item, "text"):
                                    return item.text
                        return str(result)

            result = await sse_tool_proxy(ctx=ctx)

            assert result == "pong"
            assert received["name"] == "upstream-llm"
            assert received["version"] == "4.2.0"
        finally:
            userver.should_exit = True
            await server_task

    @pytest.mark.asyncio
    async def test_sse_proxy_falls_back_without_ctx(self):
        port = 19202
        sub, received = _build_sub_server(port)
        userver, server_task = await _start_uvicorn(sub.sse_app(), port)

        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client

            sse_url = f"http://127.0.0.1:{port}/sse"

            async def sse_tool_proxy(ctx=None, **kwargs):
                from mcp_compose.client_info import resolve_client_info

                client_info = resolve_client_info(ctx)
                async with sse_client(sse_url) as (read, write):
                    async with ClientSession(read, write, client_info=client_info) as session:
                        await session.initialize()
                        result = await session.call_tool("ping", kwargs)
                        if hasattr(result, "content") and result.content:
                            for item in result.content:
                                if hasattr(item, "text"):
                                    return item.text
                        return str(result)

            await sse_tool_proxy(ctx=None)

            assert received["name"] == "mcp-compose"
        finally:
            userver.should_exit = True
            await server_task


class TestStreamableHttpProxyClientInfo:
    @pytest.mark.asyncio
    async def test_streamable_http_proxy_passes_upstream_client_info(self):
        port = 19203
        sub, received = _build_sub_server(port)
        userver, server_task = await _start_uvicorn(sub.streamable_http_app(), port)

        try:
            from mcp import ClientSession

            from mcp_compose.client_info import resolve_client_info
            from mcp_compose.http_client import streamable_http_client_compat

            http_url = f"http://127.0.0.1:{port}/mcp"
            ctx = _make_ctx(name="streaming-agent", version="1.0.0")

            async def streamable_http_tool_proxy(ctx=None, **kwargs):
                client_info = resolve_client_info(ctx)
                async with streamable_http_client_compat(url=http_url) as (
                    read_stream,
                    write_stream,
                    _get_session_id,
                ):
                    async with ClientSession(
                        read_stream, write_stream, client_info=client_info
                    ) as session:
                        await session.initialize()
                        result = await session.call_tool("ping", kwargs)
                        if hasattr(result, "content") and result.content:
                            for item in result.content:
                                if hasattr(item, "text"):
                                    return item.text
                        return str(result)

            result = await streamable_http_tool_proxy(ctx=ctx)

            assert result == "pong"
            assert received["name"] == "streaming-agent"
            assert received["version"] == "1.0.0"
        finally:
            userver.should_exit = True
            await server_task

    @pytest.mark.asyncio
    async def test_streamable_http_proxy_falls_back_without_ctx(self):
        port = 19204
        sub, received = _build_sub_server(port)
        userver, server_task = await _start_uvicorn(sub.streamable_http_app(), port)

        try:
            from mcp import ClientSession

            from mcp_compose.client_info import resolve_client_info
            from mcp_compose.http_client import streamable_http_client_compat

            http_url = f"http://127.0.0.1:{port}/mcp"

            async def streamable_http_tool_proxy(ctx=None, **kwargs):
                client_info = resolve_client_info(ctx)
                async with streamable_http_client_compat(url=http_url) as (
                    read_stream,
                    write_stream,
                    _get_session_id,
                ):
                    async with ClientSession(
                        read_stream, write_stream, client_info=client_info
                    ) as session:
                        await session.initialize()
                        result = await session.call_tool("ping", kwargs)
                        if hasattr(result, "content") and result.content:
                            for item in result.content:
                                if hasattr(item, "text"):
                                    return item.text
                        return str(result)

            await streamable_http_tool_proxy(ctx=None)

            assert received["name"] == "mcp-compose"
        finally:
            userver.should_exit = True
            await server_task


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
