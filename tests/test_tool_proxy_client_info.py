# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Tests for upstream clientInfo propagation through the STDIO ToolProxy path.
"""

import inspect
import sys

import pytest

from mcp_compose.client_info import FALLBACK_CLIENT_INFO, resolve_client_info

RECORDING_MCP_SERVER = """
import sys
import json

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        method = msg.get("method", "")

        if method == "initialize":
            client_info = msg["params"].get("clientInfo", {})
            print(json.dumps({
                "jsonrpc": "2.0",
                "id": msg["id"],
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "serverInfo": {"name": "recording-server", "version": "0.1.0"},
                    "clientInfoReceived": client_info,
                }
            }), flush=True)

        elif method == "notifications/initialized":
            pass

        elif method == "tools/list":
            print(json.dumps({
                "jsonrpc": "2.0",
                "id": msg["id"],
                "result": {"tools": []}
            }), flush=True)

        elif method == "tools/call":
            print(json.dumps({
                "jsonrpc": "2.0",
                "id": msg["id"],
                "result": {"content": [{"type": "text", "text": "ok"}]}
            }), flush=True)

if __name__ == "__main__":
    main()
"""


def _make_ctx(name: str = "test-agent", version: str = "2.0.0"):
    from unittest.mock import MagicMock

    from mcp.types import Implementation

    info = Implementation(name=name, version=version)
    client_params = MagicMock()
    client_params.clientInfo = info
    session = MagicMock()
    session.client_params = client_params
    ctx = MagicMock()
    ctx.session = session
    return ctx


@pytest.fixture
def recording_script(tmp_path):
    script = tmp_path / "recording_server.py"
    script.write_text(RECORDING_MCP_SERVER)
    return str(script)


class TestResolveClientInfo:
    def test_returns_fallback_when_ctx_is_none(self):
        result = resolve_client_info(None)
        assert result is FALLBACK_CLIENT_INFO
        assert result.name == "mcp-compose"

    def test_returns_fallback_when_client_params_is_none(self):
        from unittest.mock import MagicMock

        session = MagicMock()
        session.client_params = None
        ctx = MagicMock()
        ctx.session = session

        result = resolve_client_info(ctx)
        assert result is FALLBACK_CLIENT_INFO

    def test_returns_fallback_on_attribute_error(self):
        result = resolve_client_info(object())
        assert result is FALLBACK_CLIENT_INFO

    def test_returns_upstream_client_info(self):
        ctx = _make_ctx(name="my-llm", version="9.9.9")
        result = resolve_client_info(ctx)
        assert result.name == "my-llm"
        assert result.version == "9.9.9"


class TestToolProxyDiscoverToolsClientInfo:
    @pytest.mark.asyncio
    async def test_discover_tools_sends_upstream_client_info(self, recording_script):
        from unittest.mock import MagicMock

        from mcp_compose.composer import MCPServerComposer
        from mcp_compose.process_manager import ProcessManager
        from mcp_compose.tool_proxy import ToolProxy

        process_manager = ProcessManager()
        composer = MagicMock()
        composer.conflict_resolution = MCPServerComposer().conflict_resolution
        composer.composed_tools = {}
        composer.source_mapping = {}
        composer.composed_server = MagicMock()
        composer.composed_server._tool_manager._tools = {}

        tool_proxy = ToolProxy(process_manager, composer)
        process = await process_manager.add_process(
            name="recording",
            command=[sys.executable, recording_script],
            auto_start=True,
        )

        ctx = _make_ctx(name="upstream-agent", version="3.1.4")
        captured_init = {}

        original_send = tool_proxy._send_request

        async def capturing_send(proc, request, timeout=5.0):
            if request.get("method") == "initialize":
                captured_init.update(request["params"].get("clientInfo", {}))
            return await original_send(proc, request, timeout)

        tool_proxy._send_request = capturing_send

        await tool_proxy.discover_tools("recording", process, ctx=ctx)

        assert captured_init["name"] == "upstream-agent"
        assert captured_init["version"] == "3.1.4"

        await process_manager.stop_process("recording")

    @pytest.mark.asyncio
    async def test_discover_tools_uses_fallback_without_ctx(self, recording_script):
        from unittest.mock import MagicMock

        from mcp_compose.composer import MCPServerComposer
        from mcp_compose.process_manager import ProcessManager
        from mcp_compose.tool_proxy import ToolProxy

        process_manager = ProcessManager()
        composer = MagicMock()
        composer.conflict_resolution = MCPServerComposer().conflict_resolution
        composer.composed_tools = {}
        composer.source_mapping = {}
        composer.composed_server = MagicMock()
        composer.composed_server._tool_manager._tools = {}

        tool_proxy = ToolProxy(process_manager, composer)
        process = await process_manager.add_process(
            name="recording2",
            command=[sys.executable, recording_script],
            auto_start=True,
        )

        captured_init = {}

        original_send = tool_proxy._send_request

        async def capturing_send(proc, request, timeout=5.0):
            if request.get("method") == "initialize":
                captured_init.update(request["params"].get("clientInfo", {}))
            return await original_send(proc, request, timeout)

        tool_proxy._send_request = capturing_send

        await tool_proxy.discover_tools("recording2", process, ctx=None)

        assert captured_init["name"] == "mcp-compose"

        await process_manager.stop_process("recording2")


class TestToolProxyProxyFunctionSignature:
    def test_proxy_function_has_ctx_parameter(self, recording_script):
        from unittest.mock import MagicMock

        from mcp.server.fastmcp import Context

        from mcp_compose.composer import MCPServerComposer
        from mcp_compose.process import Process
        from mcp_compose.process_manager import ProcessManager
        from mcp_compose.tool_proxy import ToolProxy

        process_manager = ProcessManager()
        composer = MagicMock()
        composer.conflict_resolution = MCPServerComposer().conflict_resolution
        composer.composed_tools = {}
        composer.source_mapping = {}
        composer.composed_server = MagicMock()
        composer.composed_server._tool_manager._tools = {}

        tool_proxy = ToolProxy(process_manager, composer)
        mock_process = MagicMock(spec=Process)

        tool_def = {
            "name": "greet",
            "description": "Say hello",
            "inputSchema": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        }

        tool_proxy._register_tool_proxy("srv", "greet", tool_def, mock_process)

        registered = composer.composed_server._tool_manager._tools.get("srv_greet")
        assert registered is not None

        sig = inspect.signature(registered.fn)
        params = list(sig.parameters.keys())
        assert "ctx" in params
        assert sig.parameters["ctx"].annotation is Context

    def test_ctx_not_in_tool_schema(self, recording_script):
        from unittest.mock import MagicMock

        from mcp_compose.composer import MCPServerComposer
        from mcp_compose.process import Process
        from mcp_compose.process_manager import ProcessManager
        from mcp_compose.tool_proxy import ToolProxy

        process_manager = ProcessManager()
        composer = MagicMock()
        composer.conflict_resolution = MCPServerComposer().conflict_resolution
        composer.composed_tools = {}
        composer.source_mapping = {}
        composer.composed_server = MagicMock()
        composer.composed_server._tool_manager._tools = {}

        tool_proxy = ToolProxy(process_manager, composer)
        mock_process = MagicMock(spec=Process)

        tool_def = {
            "name": "greet",
            "description": "Say hello",
            "inputSchema": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        }

        tool_proxy._register_tool_proxy("srv", "greet", tool_def, mock_process)
        registered = composer.composed_server._tool_manager._tools.get("srv_greet")
        assert registered is not None
        assert "ctx" not in registered.parameters.get("properties", {})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
