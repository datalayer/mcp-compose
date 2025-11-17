"""
HTTP Streaming Transport for MCP.

This module implements HTTP-based streaming transport supporting:
- Chunked transfer encoding
- Newline-delimited JSON (NDJSON/JSON Lines)
- Long-polling
"""

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict, Optional

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from .base import Transport, TransportType

logger = logging.getLogger(__name__)


class HttpStreamProtocol:
    """HTTP streaming protocol types."""
    CHUNKED = "chunked"
    LINES = "lines"
    POLL = "poll"


class HttpStreamTransport(Transport):
    """
    HTTP streaming transport for MCP communication.
    
    Supports multiple streaming protocols:
    - chunked: HTTP chunked transfer encoding
    - lines: Newline-delimited JSON (JSON Lines/NDJSON)
    - poll: Long-polling
    """
    
    def __init__(
        self,
        name: str,
        url: str,
        protocol: str = HttpStreamProtocol.LINES,
        auth_token: Optional[str] = None,
        auth_type: str = "bearer",
        timeout: int = 30,
        retry_interval: int = 5,
        keep_alive: bool = True,
        reconnect_on_failure: bool = True,
        max_reconnect_attempts: int = 10,
        poll_interval: int = 2,
    ):
        """
        Initialize HTTP streaming transport.
        
        Args:
            name: Transport instance name.
            url: HTTP endpoint URL.
            protocol: Streaming protocol (chunked, lines, poll).
            auth_token: Authentication token.
            auth_type: Authentication type (bearer, basic).
            timeout: Request timeout in seconds.
            retry_interval: Retry interval in seconds.
            keep_alive: Keep connection alive.
            reconnect_on_failure: Reconnect on failure.
            max_reconnect_attempts: Maximum reconnection attempts.
            poll_interval: Polling interval for poll protocol.
        """
        if not HTTPX_AVAILABLE:
            raise RuntimeError(
                "httpx is required for HTTP streaming transport. "
                "Install with: pip install httpx"
            )
        
        super().__init__(name, TransportType.WEBSOCKET)  # Reusing WEBSOCKET for HTTP streaming
        
        self.url = url
        self.protocol = protocol
        self.auth_token = auth_token
        self.auth_type = auth_type
        self.timeout = timeout
        self.retry_interval = retry_interval
        self.keep_alive = keep_alive
        self.reconnect_on_failure = reconnect_on_failure
        self.max_reconnect_attempts = max_reconnect_attempts
        self.poll_interval = poll_interval
        
        self.client: Optional[httpx.AsyncClient] = None
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._stream_task: Optional[asyncio.Task] = None
        self._reconnect_count = 0
        self._buffer = ""
        self._client_id: Optional[str] = None
    
    async def connect(self) -> None:
        """
        Establish HTTP connection.
        
        Raises:
            ConnectionError: If connection fails.
        """
        if self._connected:
            logger.warning(f"Transport {self.name} already connected")
            return
        
        try:
            # Create HTTP client
            headers = self._build_headers()
            self.client = httpx.AsyncClient(
                headers=headers,
                timeout=self.timeout,
                follow_redirects=True,
            )
            
            # Test connection
            await self._test_connection()
            
            self._connected = True
            self._reconnect_count = 0
            
            # Start streaming task immediately for lines and chunked protocols
            if self.protocol in [HttpStreamProtocol.LINES, HttpStreamProtocol.CHUNKED]:
                self._stream_task = asyncio.create_task(self._stream_messages())
                # Give it a moment to establish the stream and capture client ID
                await asyncio.sleep(0.2)
            
            logger.info(f"HTTP streaming transport {self.name} connected to {self.url}")
            
        except Exception as e:
            logger.error(f"Failed to connect to {self.url}: {e}")
            if self.client:
                await self.client.aclose()
                self.client = None
            raise ConnectionError(f"Failed to connect: {e}")
    
    async def disconnect(self) -> None:
        """Close HTTP connection."""
        if not self._connected:
            return
        
        self._connected = False
        
        # Cancel streaming task
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                pass
        
        # Close HTTP client
        if self.client:
            await self.client.aclose()
            self.client = None
        
        logger.info(f"HTTP streaming transport {self.name} disconnected")
    
    async def send(self, message: Dict[str, Any]) -> None:
        """
        Send a message to the MCP server.
        
        Args:
            message: JSON-RPC message to send.
        
        Raises:
            ConnectionError: If not connected.
        """
        if not self._connected or not self.client:
            raise ConnectionError("Not connected")
        
        try:
            # Include client ID in headers if we have one
            headers = {}
            if self._client_id:
                headers["X-Client-Id"] = self._client_id
            
            # Send message via POST
            response = await self.client.post(
                self.url,
                json=message,
                timeout=self.timeout,
                headers=headers,
            )
            response.raise_for_status()
            
            logger.debug(f"Sent message to {self.url}: {message}")
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise ConnectionError(f"Failed to send message: {e}")
    
    async def receive(self) -> Dict[str, Any]:
        """
        Receive a message from the MCP server.
        
        Returns:
            JSON-RPC message received.
        
        Raises:
            ConnectionError: If not connected.
        """
        if not self._connected:
            raise ConnectionError("Not connected")
        
        return await self._message_queue.get()
    
    async def messages(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream messages from the MCP server.
        
        Yields:
            JSON-RPC messages as they arrive.
        """
        while self._connected:
            try:
                message = await asyncio.wait_for(
                    self._message_queue.get(),
                    timeout=1.0
                )
                yield message
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error receiving message: {e}")
                break
    
    async def _stream_messages(self) -> None:
        """Background task to stream messages from HTTP endpoint."""
        while self._connected:
            try:
                if self.protocol == HttpStreamProtocol.POLL:
                    await self._poll_messages()
                elif self.protocol == HttpStreamProtocol.LINES:
                    await self._stream_lines()
                elif self.protocol == HttpStreamProtocol.CHUNKED:
                    await self._stream_chunked()
                else:
                    logger.error(f"Unknown protocol: {self.protocol}")
                    break
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in streaming task: {e}")
                
                if self.reconnect_on_failure and self._reconnect_count < self.max_reconnect_attempts:
                    self._reconnect_count += 1
                    logger.info(f"Reconnecting... (attempt {self._reconnect_count}/{self.max_reconnect_attempts})")
                    await asyncio.sleep(self.retry_interval)
                else:
                    logger.error("Max reconnection attempts reached")
                    break
    
    async def _poll_messages(self) -> None:
        """Poll for messages using long-polling."""
        if not self.client:
            return
        
        try:
            response = await self.client.get(
                self.url,
                timeout=self.timeout,
            )
            response.raise_for_status()
            
            data = response.json()
            if data:
                await self._message_queue.put(data)
            
            await asyncio.sleep(self.poll_interval)
            
        except httpx.TimeoutException:
            # Timeout is expected in long-polling
            await asyncio.sleep(self.poll_interval)
        except Exception as e:
            logger.error(f"Error polling messages: {e}")
            raise
    
    async def _stream_lines(self) -> None:
        """Stream messages using newline-delimited JSON."""
        if not self.client:
            return
        
        try:
            async with self.client.stream("GET", self.url, timeout=None) as response:
                response.raise_for_status()
                
                # Capture client ID from response headers
                if "X-Client-Id" in response.headers:
                    self._client_id = response.headers["X-Client-Id"]
                    logger.debug(f"Captured client ID: {self._client_id}")
                
                async for line in response.aiter_lines():
                    if not self._connected:
                        break
                    
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        message = json.loads(line)
                        # Skip keepalive messages
                        if message.get("type") == "keepalive":
                            continue
                        await self._message_queue.put(message)
                        logger.debug(f"Received message: {message}")
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse JSON line: {line[:100]}... Error: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"Error streaming lines: {e}")
            raise
    
    async def _stream_chunked(self) -> None:
        """Stream messages using chunked transfer encoding."""
        if not self.client:
            return
        
        try:
            async with self.client.stream("GET", self.url, timeout=None) as response:
                response.raise_for_status()
                
                async for chunk in response.aiter_bytes():
                    if not self._connected:
                        break
                    
                    # Add chunk to buffer
                    self._buffer += chunk.decode('utf-8')
                    
                    # Try to extract complete JSON objects
                    await self._process_buffer()
                        
        except Exception as e:
            logger.error(f"Error streaming chunks: {e}")
            raise
    
    async def _process_buffer(self) -> None:
        """Process buffer to extract complete JSON messages."""
        while True:
            # Try to find a complete JSON object
            try:
                # Look for newline-separated JSON
                if '\n' in self._buffer:
                    line, self._buffer = self._buffer.split('\n', 1)
                    line = line.strip()
                    if line:
                        message = json.loads(line)
                        await self._message_queue.put(message)
                        logger.debug(f"Received message: {message}")
                        continue
                
                # Try to parse the entire buffer
                if self._buffer.strip():
                    message = json.loads(self._buffer)
                    await self._message_queue.put(message)
                    logger.debug(f"Received message: {message}")
                    self._buffer = ""
                    continue
                
                break
                
            except json.JSONDecodeError:
                # Need more data
                break
    
    async def _test_connection(self) -> None:
        """Test HTTP connection."""
        if not self.client:
            raise ConnectionError("HTTP client not initialized")
        
        try:
            # Try a GET request to test connectivity (HEAD may not be supported)
            response = await self.client.get(self.url, timeout=5)
            # Accept 200 as valid, 405 means endpoint exists but wrong method
            if response.status_code not in [200, 405]:
                response.raise_for_status()
        except Exception as e:
            # Connection test is not critical - log warning and continue
            logger.debug(f"Connection test returned: {e}, continuing anyway")
    
    def _build_headers(self) -> Dict[str, str]:
        """Build HTTP headers including authentication."""
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        
        if self.auth_token:
            if self.auth_type.lower() == "bearer":
                headers["Authorization"] = f"Bearer {self.auth_token}"
            elif self.auth_type.lower() == "basic":
                headers["Authorization"] = f"Basic {self.auth_token}"
            else:
                headers["Authorization"] = self.auth_token
        
        return headers


async def create_http_stream_transport(
    name: str,
    url: str,
    protocol: str = HttpStreamProtocol.LINES,
    **kwargs,
) -> HttpStreamTransport:
    """
    Create and connect an HTTP streaming transport.
    
    Args:
        name: Transport instance name.
        url: HTTP endpoint URL.
        protocol: Streaming protocol.
        **kwargs: Additional transport configuration.
    
    Returns:
        Connected HttpStreamTransport instance.
    """
    transport = HttpStreamTransport(name, url, protocol, **kwargs)
    await transport.connect()
    return transport
