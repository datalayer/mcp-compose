"""
Tests for SSE transport.
"""

import asyncio
import pytest
import httpx
import json
from mcp_compose.transport.sse_server import SSETransport, create_sse_server
from mcp_compose.transport.base import TransportType


class TestSSETransport:
    """Tests for SSE transport."""
    
    @pytest.mark.asyncio
    async def test_transport_init(self):
        """Test SSE transport initialization."""
        transport = SSETransport(name="test", host="127.0.0.1", port=8100)
        
        assert transport.name == "test"
        assert transport.transport_type == TransportType.SSE
        assert transport.host == "127.0.0.1"
        assert transport.port == 8100
        assert not transport.is_connected
    
    @pytest.mark.asyncio
    async def test_transport_connect_disconnect(self):
        """Test connecting and disconnecting transport."""
        transport = SSETransport(name="test", host="127.0.0.1", port=8101)
        
        await transport.connect()
        assert transport.is_connected
        
        await transport.disconnect()
        assert not transport.is_connected
    
    @pytest.mark.asyncio
    async def test_transport_context_manager(self):
        """Test using transport as context manager."""
        async with SSETransport(name="test", host="127.0.0.1", port=8102) as transport:
            assert transport.is_connected
        
        assert not transport.is_connected
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test health check endpoint."""
        transport = SSETransport(name="test", host="127.0.0.1", port=8103)
        await transport.connect()
        
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8103/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["transport"] == "test"
        
        await transport.disconnect()
    
    @pytest.mark.asyncio
    async def test_sse_endpoint_connection(self):
        """Test connecting to SSE endpoint."""
        transport = SSETransport(name="test", host="127.0.0.1", port=8104)
        await transport.connect()
        
        # Connect to SSE endpoint
        connection_verified = False
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", "http://127.0.0.1:8104/sse") as response:
                assert response.status_code == 200
                assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
                
                # Read first event (connection message)
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data = json.loads(line[5:].strip())
                        assert "client_id" in data
                        connection_verified = True
                        break
        
        assert connection_verified
        await transport.disconnect()
    
    @pytest.mark.asyncio
    async def test_receive_message_from_client(self):
        """Test receiving messages from clients via POST."""
        transport = SSETransport(name="test", host="127.0.0.1", port=8105)
        await transport.connect()
        
        # Send message from "client"
        test_message = {"jsonrpc": "2.0", "method": "test", "id": 1}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://127.0.0.1:8105/message",
                json=test_message
            )
            assert response.status_code == 200
            assert response.json()["status"] == "received"
        
        # Receive the message
        received = await transport.receive()
        assert received == test_message
        
        await transport.disconnect()
    
    @pytest.mark.asyncio
    async def test_send_message_to_clients(self):
        """Test sending messages to connected clients."""
        transport = SSETransport(name="test", host="127.0.0.1", port=8106)
        await transport.connect()
        
        test_message = {"jsonrpc": "2.0", "result": "test", "id": 1}
        
        # Start SSE client in background
        async def sse_client():
            async with httpx.AsyncClient() as client:
                async with client.stream("GET", "http://127.0.0.1:8106/sse") as response:
                    event_count = 0
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            data = json.loads(line[5:].strip())
                            event_count += 1
                            
                            # First message is connection, second is our test message
                            if event_count == 2:
                                assert data == test_message
                                return True
                    return False
        
        # Start client
        client_task = asyncio.create_task(sse_client())
        
        # Wait for client to connect
        await asyncio.sleep(0.5)
        
        # Send message
        await transport.send(test_message)
        
        # Wait for client to receive
        result = await asyncio.wait_for(client_task, timeout=5.0)
        assert result is True
        
        await transport.disconnect()
    
    @pytest.mark.asyncio
    async def test_multiple_clients(self):
        """Test handling multiple connected clients."""
        transport = SSETransport(name="test", host="127.0.0.1", port=8107)
        await transport.connect()
        
        # Connect multiple clients
        async def connect_client(client_id):
            async with httpx.AsyncClient() as client:
                async with client.stream("GET", "http://127.0.0.1:8107/sse") as response:
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            break
                    # Keep connection open
                    await asyncio.sleep(2.0)
        
        # Start 3 clients
        tasks = [
            asyncio.create_task(connect_client(i))
            for i in range(3)
        ]
        
        # Wait for clients to connect
        await asyncio.sleep(0.5)
        
        # Check client count
        assert transport.client_count == 3
        
        # Cleanup
        for task in tasks:
            task.cancel()
        
        await transport.disconnect()
    
    @pytest.mark.asyncio
    async def test_broadcast_to_multiple_clients(self):
        """Test broadcasting message to multiple clients."""
        transport = SSETransport(name="test", host="127.0.0.1", port=8108)
        await transport.connect()
        
        test_message = {"jsonrpc": "2.0", "method": "broadcast"}
        received_messages = []
        
        async def sse_client(client_id):
            async with httpx.AsyncClient() as client:
                async with client.stream("GET", "http://127.0.0.1:8108/sse") as response:
                    event_count = 0
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            data = json.loads(line[5:].strip())
                            event_count += 1
                            
                            if event_count == 2:  # Skip connection message
                                received_messages.append((client_id, data))
                                return
        
        # Start 2 clients
        client_tasks = [
            asyncio.create_task(sse_client(i))
            for i in range(2)
        ]
        
        # Wait for clients to connect
        await asyncio.sleep(0.5)
        
        # Broadcast message
        await transport.send(test_message)
        
        # Wait for clients to receive
        await asyncio.gather(*client_tasks)
        
        # Verify both clients received the message
        assert len(received_messages) == 2
        for client_id, msg in received_messages:
            assert msg == test_message
        
        await transport.disconnect()
    
    @pytest.mark.asyncio
    async def test_cors_headers(self):
        """Test CORS headers are properly set."""
        transport = SSETransport(
            name="test",
            host="127.0.0.1",
            port=8109,
            cors_origins=["http://example.com"]
        )
        await transport.connect()
        
        async with httpx.AsyncClient() as client:
            response = await client.options(
                "http://127.0.0.1:8109/health",
                headers={"Origin": "http://example.com"}
            )
            
            # Check CORS headers
            assert "access-control-allow-origin" in response.headers
        
        await transport.disconnect()
    
    @pytest.mark.asyncio
    async def test_clients_list_endpoint(self):
        """Test endpoint for listing connected clients."""
        transport = SSETransport(name="test", host="127.0.0.1", port=8110)
        await transport.connect()
        
        # Initially no clients
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8110/clients")
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 0
        
        await transport.disconnect()
    
    @pytest.mark.asyncio
    async def test_get_endpoint_urls(self):
        """Test getting endpoint URLs."""
        transport = SSETransport(name="test", host="127.0.0.1", port=8111)
        
        assert transport.get_endpoint_url() == "http://127.0.0.1:8111/sse"
        assert transport.get_message_url() == "http://127.0.0.1:8111/message"
    
    @pytest.mark.asyncio
    async def test_send_without_connection_error(self):
        """Test sending message without connection raises error."""
        transport = SSETransport(name="test", host="127.0.0.1", port=8112)
        
        with pytest.raises(ConnectionError):
            await transport.send({"test": "message"})
    
    @pytest.mark.asyncio
    async def test_receive_without_connection_error(self):
        """Test receiving message without connection raises error."""
        transport = SSETransport(name="test", host="127.0.0.1", port=8113)
        
        with pytest.raises(ConnectionError):
            await transport.receive()
    
    @pytest.mark.asyncio
    async def test_create_sse_server_helper(self):
        """Test create_sse_server helper function."""
        transport = await create_sse_server(
            name="helper-test",
            host="127.0.0.1",
            port=8114
        )
        
        assert transport.is_connected
        assert transport.name == "helper-test"
        
        await transport.disconnect()
    
    @pytest.mark.asyncio
    async def test_invalid_message_handling(self):
        """Test handling of invalid messages from clients."""
        transport = SSETransport(name="test", host="127.0.0.1", port=8115)
        await transport.connect()
        
        # Send invalid JSON
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://127.0.0.1:8115/message",
                content="invalid json"
            )
            assert response.status_code == 400
        
        await transport.disconnect()
