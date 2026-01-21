# Copyright (c) 2023-2025 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""Tests for protocol translator."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mcp_compose.proxy.translator import (
    ProtocolTranslator,
    SseToStdioTranslator,
    StdioToSseTranslator,
    TranslatorManager,
)


class MockProtocolTranslator(ProtocolTranslator):
    """Mock translator for testing abstract base."""
    
    async def translate(self, message):
        return message
    
    async def start(self):
        pass
    
    async def stop(self):
        pass


@pytest.mark.asyncio
class TestProtocolTranslator:
    """Test ProtocolTranslator abstract base class."""
    
    async def test_abstract_methods(self):
        """Test that abstract methods must be implemented."""
        translator = MockProtocolTranslator()
        
        message = {"jsonrpc": "2.0", "method": "test", "id": 1}
        result = await translator.translate(message)
        assert result == message
        
        await translator.start()
        await translator.stop()


@pytest.mark.asyncio
class TestStdioToSseTranslator:
    """Test STDIO to SSE translator."""
    
    async def test_initialization(self):
        """Test translator initialization."""
        translator = StdioToSseTranslator(
            sse_url="http://localhost:8000/sse",
            headers={"Authorization": "Bearer test"},
            timeout=60.0,
        )
        
        assert translator.sse_url == "http://localhost:8000/sse"
        assert translator.headers == {"Authorization": "Bearer test"}
        assert translator.timeout == 60.0
        assert translator.client is None
        assert not translator.running
    
    async def test_start_stop(self):
        """Test starting and stopping translator."""
        translator = StdioToSseTranslator(
            sse_url="http://localhost:8000/sse",
        )
        
        await translator.start()
        assert translator.running
        assert translator.client is not None
        
        await translator.stop()
        assert not translator.running
    
    async def test_send_to_sse_success(self):
        """Test successful message sending to SSE server."""
        translator = StdioToSseTranslator(
            sse_url="http://localhost:8000/sse",
        )
        await translator.start()
        
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"status": "ok"}
        }
        mock_response.raise_for_status = MagicMock()
        
        with patch.object(translator.client, "post", return_value=mock_response) as mock_post:
            mock_post.return_value = mock_response
            
            message = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 1
            }
            
            response = await translator.translate(message)
            
            assert response["id"] == 1
            assert response["result"]["status"] == "ok"
            mock_post.assert_called_once()
        
        await translator.stop()
    
    async def test_send_to_sse_http_error(self):
        """Test handling HTTP errors from SSE server."""
        translator = StdioToSseTranslator(
            sse_url="http://localhost:8000/sse",
        )
        await translator.start()
        
        with patch.object(
            translator.client,
            "post",
            side_effect=httpx.HTTPError("Connection failed")
        ):
            message = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 1
            }
            
            response = await translator.translate(message)
            
            assert "error" in response
            assert response["error"]["code"] == -32000
            assert "HTTP error" in response["error"]["message"]
        
        await translator.stop()
    
    async def test_send_to_sse_general_error(self):
        """Test handling general errors."""
        translator = StdioToSseTranslator(
            sse_url="http://localhost:8000/sse",
        )
        await translator.start()
        
        with patch.object(
            translator.client,
            "post",
            side_effect=Exception("Unexpected error")
        ):
            message = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 1
            }
            
            response = await translator.translate(message)
            
            assert "error" in response
            assert response["error"]["code"] == -32603
            assert "Internal error" in response["error"]["message"]
        
        await translator.stop()


@pytest.mark.asyncio
class TestSseToStdioTranslator:
    """Test SSE to STDIO translator."""
    
    async def test_initialization(self):
        """Test translator initialization."""
        translator = SseToStdioTranslator(
            command="python",
            args=["-m", "mcp_server"],
            env={"DEBUG": "1"},
            cwd="/tmp",
        )
        
        assert translator.command == "python"
        assert translator.args == ["-m", "mcp_server"]
        assert translator.env == {"DEBUG": "1"}
        assert translator.cwd == "/tmp"
        assert translator.process is None
        assert not translator.running
    
    async def test_start_stop(self):
        """Test starting and stopping translator."""
        # Use a simple command that exists
        translator = SseToStdioTranslator(
            command="cat",  # Simple command for testing
        )
        
        try:
            await translator.start()
            assert translator.running
            assert translator.process is not None
            
            await translator.stop()
            assert not translator.running
        except Exception:
            # Clean up if test fails
            if translator.running:
                await translator.stop()
            raise
    
    async def test_translate_with_timeout(self):
        """Test message translation with timeout."""
        translator = SseToStdioTranslator(
            command="cat",  # Won't respond properly, will timeout
        )
        
        try:
            await translator.start()
            
            # Mock the timeout to be shorter
            with patch.object(asyncio, "wait_for", side_effect=asyncio.TimeoutError):
                message = {
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "id": 1
                }
                
                response = await translator.translate(message)
                
                assert "error" in response
                assert response["error"]["code"] == -32000
                assert "timeout" in response["error"]["message"].lower()
        finally:
            await translator.stop()
    
    async def test_translate_with_error(self):
        """Test message translation with error."""
        translator = SseToStdioTranslator(
            command="cat",
        )
        
        try:
            await translator.start()
            
            # Force an error by closing stdin
            if translator.process and translator.process.stdin:
                translator.process.stdin.close()
            
            message = {
                "jsonrpc": "2.0",
                "method": "tools/list",
            }
            
            response = await translator.translate(message)
            
            # Should return an error response
            assert "error" in response or "id" in response
        finally:
            await translator.stop()
    
    async def test_id_generation(self):
        """Test automatic ID generation."""
        translator = SseToStdioTranslator(
            command="cat",
        )
        
        try:
            await translator.start()
            
            message1 = {
                "jsonrpc": "2.0",
                "method": "tools/list",
            }
            message2 = {
                "jsonrpc": "2.0",
                "method": "tools/list",
            }
            
            # Mock the future to complete quickly
            with patch.object(asyncio, "wait_for", side_effect=asyncio.TimeoutError):
                await translator.translate(message1)
                await translator.translate(message2)
                
                # IDs should be different
                assert translator._next_id > 1
        finally:
            await translator.stop()


@pytest.mark.asyncio
class TestTranslatorManager:
    """Test TranslatorManager."""
    
    async def test_initialization(self):
        """Test manager initialization."""
        manager = TranslatorManager()
        assert len(manager.translators) == 0
    
    async def test_add_stdio_to_sse(self):
        """Test adding STDIO→SSE translator."""
        manager = TranslatorManager()
        
        translator = await manager.add_stdio_to_sse(
            name="test-translator",
            sse_url="http://localhost:8000/sse",
            headers={"Authorization": "Bearer test"},
        )
        
        assert isinstance(translator, StdioToSseTranslator)
        assert "test-translator" in manager.translators
        assert translator.running
        
        await manager.stop_all()
    
    async def test_add_sse_to_stdio(self):
        """Test adding SSE→STDIO translator."""
        manager = TranslatorManager()
        
        try:
            translator = await manager.add_sse_to_stdio(
                name="test-translator",
                command="cat",
                args=[],
            )
            
            assert isinstance(translator, SseToStdioTranslator)
            assert "test-translator" in manager.translators
            assert translator.running
        finally:
            await manager.stop_all()
    
    async def test_remove_translator(self):
        """Test removing translator."""
        manager = TranslatorManager()
        
        await manager.add_stdio_to_sse(
            name="test-translator",
            sse_url="http://localhost:8000/sse",
        )
        
        assert "test-translator" in manager.translators
        
        await manager.remove_translator("test-translator")
        
        assert "test-translator" not in manager.translators
    
    async def test_stop_all(self):
        """Test stopping all translators."""
        manager = TranslatorManager()
        
        await manager.add_stdio_to_sse(
            name="translator1",
            sse_url="http://localhost:8000/sse",
        )
        
        try:
            await manager.add_sse_to_stdio(
                name="translator2",
                command="cat",
            )
        except Exception:
            pass  # May fail but that's okay for this test
        
        assert len(manager.translators) > 0
        
        await manager.stop_all()
        
        assert len(manager.translators) == 0
    
    async def test_get_translator(self):
        """Test getting translator by name."""
        manager = TranslatorManager()
        
        await manager.add_stdio_to_sse(
            name="test-translator",
            sse_url="http://localhost:8000/sse",
        )
        
        translator = manager.get_translator("test-translator")
        assert translator is not None
        assert isinstance(translator, StdioToSseTranslator)
        
        missing = manager.get_translator("nonexistent")
        assert missing is None
        
        await manager.stop_all()


@pytest.mark.asyncio
class TestIntegration:
    """Integration tests for translators."""
    
    async def test_stdio_to_sse_full_flow(self):
        """Test full STDIO→SSE translation flow."""
        # This would require a real SSE server running
        # For now, just test the setup and teardown
        translator = StdioToSseTranslator(
            sse_url="http://localhost:8000/sse",
        )
        
        await translator.start()
        assert translator.running
        
        await translator.stop()
        assert not translator.running
    
    async def test_manager_lifecycle(self):
        """Test manager full lifecycle."""
        manager = TranslatorManager()
        
        # Add multiple translators
        await manager.add_stdio_to_sse(
            name="stdio-to-sse",
            sse_url="http://localhost:8000/sse",
        )
        
        assert len(manager.translators) == 1
        
        # Stop all
        await manager.stop_all()
        assert len(manager.translators) == 0
