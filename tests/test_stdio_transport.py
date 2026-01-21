# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Tests for STDIO transport implementation.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, Any

import pytest

from mcp_compose.transport import STDIOTransport, TransportType, create_stdio_transport


# Helper script for testing - acts as a simple echo server
ECHO_SERVER_SCRIPT = '''
import sys
import json

def main():
    """Simple echo server that reads JSON from stdin and writes to stdout."""
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            
            try:
                message = json.loads(line)
                
                # Echo back with response
                response = {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "result": {
                        "echoed": message,
                        "status": "ok"
                    }
                }
                
                print(json.dumps(response), flush=True)
                
            except json.JSONDecodeError as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {str(e)}"
                    }
                }
                print(json.dumps(error_response), flush=True)
                
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
'''


@pytest.fixture
def echo_script(tmp_path):
    """Create a temporary echo server script."""
    script_path = tmp_path / "echo_server.py"
    script_path.write_text(ECHO_SERVER_SCRIPT)
    return str(script_path)


@pytest.fixture
def stdio_transport_factory(echo_script):
    """Factory to create STDIO transports for testing."""
    transports = []
    
    def _create():
        transport = create_stdio_transport(
            name="test-echo",
            command=sys.executable,
            args=[echo_script],
        )
        transports.append(transport)
        return transport
    
    yield _create
    
    # Cleanup all created transports
    # Note: Cleanup happens in test's event loop, so no action needed here
    # Tests are responsible for cleaning up their transports


class TestSTDIOTransportBasics:
    """Test basic STDIO transport functionality."""
    
    def test_transport_creation(self, echo_script):
        """Test creating a STDIO transport."""
        transport = create_stdio_transport(
            name="test",
            command=sys.executable,
            args=[echo_script],
        )
        
        assert transport.name == "test"
        assert transport.transport_type == TransportType.STDIO
        assert not transport.is_connected
        assert transport.command == sys.executable
        assert transport.args == [echo_script]
        assert transport.pid is None
        assert transport.returncode is None
    
    def test_transport_with_env_and_cwd(self, echo_script, tmp_path):
        """Test creating transport with env and cwd."""
        transport = create_stdio_transport(
            name="test",
            command=sys.executable,
            args=[echo_script],
            env={"TEST_VAR": "value"},
            cwd=str(tmp_path),
        )
        
        assert transport.env == {"TEST_VAR": "value"}
        assert transport.cwd == str(tmp_path)
    
    @pytest.mark.asyncio
    async def test_connect(self, echo_script):
        """Test connecting to a STDIO process."""
        transport = create_stdio_transport(
            name="test",
            command=sys.executable,
            args=[echo_script],
        )
        
        await transport.connect()
        
        assert transport.is_connected
        assert transport.pid is not None
        assert transport.returncode is None
        
        await transport.disconnect()
    
    @pytest.mark.asyncio
    async def test_connect_twice(self, echo_script):
        """Test connecting twice logs warning but doesn't fail."""
        transport = create_stdio_transport(
            name="test",
            command=sys.executable,
            args=[echo_script],
        )
        
        await transport.connect()
        await transport.connect()  # Should log warning
        
        assert transport.is_connected
        
        await transport.disconnect()
    
    @pytest.mark.asyncio
    async def test_disconnect(self, echo_script):
        """Test disconnecting from a STDIO process."""
        transport = create_stdio_transport(
            name="test",
            command=sys.executable,
            args=[echo_script],
        )
        
        await transport.connect()
        await transport.disconnect()
        
        assert not transport.is_connected
        # returncode is checked internally but process object is cleared
        assert transport._process is None
    
    @pytest.mark.asyncio
    async def test_disconnect_without_connect(self, echo_script):
        """Test disconnecting when not connected logs warning."""
        transport = create_stdio_transport(
            name="test",
            command=sys.executable,
            args=[echo_script],
        )
        
        await transport.disconnect()  # Should log warning
        assert not transport.is_connected
    
    @pytest.mark.asyncio
    async def test_context_manager(self, echo_script):
        """Test using transport as context manager."""
        transport = create_stdio_transport(
            name="test",
            command=sys.executable,
            args=[echo_script],
        )
        
        async with transport:
            assert transport.is_connected
            assert transport.pid is not None
        
        assert not transport.is_connected


class TestSTDIOTransportCommunication:
    """Test STDIO transport communication."""
    
    @pytest.mark.asyncio
    async def test_send_message(self, stdio_transport_factory):
        """Test sending a message."""
        stdio_transport = stdio_transport_factory()
        await stdio_transport.connect()
        
        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "test/echo",
            "params": {"message": "hello"}
        }
        
        await stdio_transport.send(message)
        
        # Give server time to process
        await asyncio.sleep(0.1)
        
        await stdio_transport.disconnect()
    
    @pytest.mark.asyncio
    async def test_receive_message(self, stdio_transport_factory):
        """Test receiving a message."""
        stdio_transport = stdio_transport_factory()
        await stdio_transport.connect()
        
        # Send a message
        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "test/echo",
            "params": {"message": "hello"}
        }
        await stdio_transport.send(message)
        
        # Receive response
        response = await stdio_transport.receive()
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert response["result"]["echoed"] == message
        assert response["result"]["status"] == "ok"
        
        await stdio_transport.disconnect()
    
    @pytest.mark.asyncio
    async def test_send_receive_multiple(self, stdio_transport_factory):
        """Test sending and receiving multiple messages."""
        stdio_transport = stdio_transport_factory()
        await stdio_transport.connect()
        
        for i in range(5):
            # Send message
            message = {
                "jsonrpc": "2.0",
                "id": i,
                "method": "test/echo",
                "params": {"count": i}
            }
            await stdio_transport.send(message)
            
            # Receive response
            response = await stdio_transport.receive()
            
            assert response["id"] == i
            assert response["result"]["echoed"]["params"]["count"] == i
        
        await stdio_transport.disconnect()
    
    @pytest.mark.asyncio
    async def test_send_without_connection(self, echo_script):
        """Test sending without connection raises error."""
        transport = create_stdio_transport(
            name="test",
            command=sys.executable,
            args=[echo_script],
        )
        
        message = {"jsonrpc": "2.0", "id": 1, "method": "test"}
        
        with pytest.raises(ConnectionError, match="not connected"):
            await transport.send(message)
    
    @pytest.mark.asyncio
    async def test_receive_without_connection(self, echo_script):
        """Test receiving without connection raises error."""
        transport = create_stdio_transport(
            name="test",
            command=sys.executable,
            args=[echo_script],
        )
        
        with pytest.raises(ConnectionError, match="not connected"):
            await transport.receive()
    
    @pytest.mark.asyncio
    async def test_messages_stream(self, stdio_transport_factory):
        """Test streaming messages."""
        stdio_transport = stdio_transport_factory()
        await stdio_transport.connect()
        
        # Send multiple messages
        for i in range(3):
            message = {
                "jsonrpc": "2.0",
                "id": i,
                "method": "test/echo",
                "params": {"count": i}
            }
            await stdio_transport.send(message)
        
        # Stream responses
        count = 0
        async for response in stdio_transport.messages():
            assert response["id"] == count
            count += 1
            if count >= 3:
                break
        
        assert count == 3
        
        await stdio_transport.disconnect()
    
    @pytest.mark.asyncio
    async def test_messages_without_connection(self, echo_script):
        """Test streaming without connection raises error."""
        transport = create_stdio_transport(
            name="test",
            command=sys.executable,
            args=[echo_script],
        )
        
        with pytest.raises(ConnectionError, match="not connected"):
            async for _ in transport.messages():
                pass


class TestSTDIOTransportErrors:
    """Test STDIO transport error handling."""
    
    @pytest.mark.asyncio
    async def test_invalid_command(self):
        """Test connecting with invalid command."""
        transport = create_stdio_transport(
            name="test",
            command="nonexistent-command-12345",
            args=["arg"],
        )
        
        with pytest.raises(ConnectionError, match="Failed to connect"):
            await transport.connect()
        
        assert not transport.is_connected
    
    @pytest.mark.asyncio
    async def test_command_fails_immediately(self, tmp_path):
        """Test handling command that exits immediately."""
        # Create script that exits immediately
        script = tmp_path / "exit.py"
        script.write_text("import sys; sys.exit(1)")
        
        transport = create_stdio_transport(
            name="test",
            command=sys.executable,
            args=[str(script)],
        )
        
        await transport.connect()
        
        # Give process time to exit
        await asyncio.sleep(0.2)
        
        # Should still be "connected" but process is dead
        # Attempting to send should fail
        with pytest.raises(ConnectionError):
            await transport.send({"jsonrpc": "2.0", "id": 1, "method": "test"})
    
    @pytest.mark.asyncio
    async def test_process_termination(self, echo_script):
        """Test handling process termination."""
        transport = create_stdio_transport(
            name="test",
            command=sys.executable,
            args=[echo_script],
        )
        
        await transport.connect()
        
        # Manually kill the process
        if transport._process:
            transport._process.kill()
            await transport._process.wait()
        
        # Should not be able to send
        with pytest.raises(ConnectionError):
            await transport.send({"jsonrpc": "2.0", "id": 1, "method": "test"})


class TestSTDIOTransportCleanup:
    """Test STDIO transport cleanup and resource management."""
    
    @pytest.mark.asyncio
    async def test_cleanup_on_disconnect(self, echo_script):
        """Test cleanup when disconnecting."""
        transport = create_stdio_transport(
            name="test",
            command=sys.executable,
            args=[echo_script],
        )
        
        await transport.connect()
        pid = transport.pid
        
        await transport.disconnect()
        
        # Process should be terminated
        assert transport._process is None
        assert transport._read_task is None
        assert transport._stderr_task is None
        assert transport._message_queue.empty()
    
    @pytest.mark.asyncio
    async def test_graceful_termination(self, echo_script):
        """Test graceful process termination."""
        transport = create_stdio_transport(
            name="test",
            command=sys.executable,
            args=[echo_script],
        )
        
        await transport.connect()
        await transport.disconnect()
        
        # Should have terminated (process object cleared)
        assert transport._process is None
        assert not transport.is_connected
    
    @pytest.mark.asyncio
    async def test_forced_kill_on_timeout(self, tmp_path):
        """Test forced kill when process doesn't terminate gracefully."""
        # Create script that ignores SIGTERM
        script = tmp_path / "ignore_sigterm.py"
        script.write_text('''
import signal
import time
import sys

# Ignore SIGTERM
signal.signal(signal.SIGTERM, signal.SIG_IGN)

# Keep running
try:
    while True:
        time.sleep(0.1)
except KeyboardInterrupt:
    pass
''')
        
        transport = create_stdio_transport(
            name="test",
            command=sys.executable,
            args=[str(script)],
        )
        
        await transport.connect()
        
        # This should eventually force kill
        await transport.disconnect()
        
        # Should be cleaned up (killed)
        assert transport._process is None
        assert not transport.is_connected


class TestSTDIOTransportIntegration:
    """Integration tests for STDIO transport."""
    
    @pytest.mark.asyncio
    async def test_real_world_json_rpc(self, stdio_transport_factory):
        """Test real-world JSON-RPC communication pattern."""
        stdio_transport = stdio_transport_factory()
        await stdio_transport.connect()
        
        # Initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "1.0",
                "capabilities": {}
            }
        }
        await stdio_transport.send(init_request)
        
        init_response = await stdio_transport.receive()
        assert init_response["id"] == 1
        assert "result" in init_response
        
        # List tools request
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        await stdio_transport.send(tools_request)
        
        tools_response = await stdio_transport.receive()
        assert tools_response["id"] == 2
        assert "result" in tools_response
        
        await stdio_transport.disconnect()
    
    @pytest.mark.asyncio
    async def test_concurrent_send_receive(self, stdio_transport_factory):
        """Test concurrent sending and receiving."""
        stdio_transport = stdio_transport_factory()
        await stdio_transport.connect()
        
        async def send_messages():
            for i in range(10):
                message = {
                    "jsonrpc": "2.0",
                    "id": i,
                    "method": "test",
                    "params": {"index": i}
                }
                await stdio_transport.send(message)
                await asyncio.sleep(0.01)
        
        async def receive_messages():
            responses = []
            for _ in range(10):
                response = await stdio_transport.receive()
                responses.append(response)
            return responses
        
        # Run concurrently
        send_task = asyncio.create_task(send_messages())
        receive_task = asyncio.create_task(receive_messages())
        
        await send_task
        responses = await receive_task
        
        # Should have received all responses
        assert len(responses) == 10
        ids = [r["id"] for r in responses]
        assert sorted(ids) == list(range(10))
        
        await stdio_transport.disconnect()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
