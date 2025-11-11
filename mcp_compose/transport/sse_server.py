"""
SSE (Server-Sent Events) transport for MCP.

This module implements an SSE-based transport for MCP protocol communication.
"""

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict, Optional
from queue import Queue
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
import uvicorn

from .base import Transport, TransportType

logger = logging.getLogger(__name__)


class SSETransport(Transport):
    """
    SSE transport implementation for MCP.
    
    This transport exposes an HTTP endpoint that clients can connect to via SSE.
    Messages are sent to clients via SSE, and received from clients via POST requests.
    """
    
    def __init__(
        self,
        name: str = "sse-transport",
        host: str = "0.0.0.0",
        port: int = 8000,
        cors_origins: Optional[list[str]] = None,
    ):
        """
        Initialize SSE transport.
        
        Args:
            name: Name of this transport.
            host: Host to bind to.
            port: Port to bind to.
            cors_origins: List of allowed CORS origins (default: ["*"]).
        """
        super().__init__(name, TransportType.SSE)
        self.host = host
        self.port = port
        self.cors_origins = cors_origins or ["*"]
        
        # FastAPI app
        self.app = FastAPI(title=f"MCP SSE Transport - {name}")
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Message queues for each connected client
        self._client_queues: Dict[str, asyncio.Queue] = {}
        
        # Queue for incoming messages from clients
        self._incoming_messages: asyncio.Queue = asyncio.Queue()
        
        # Server task
        self._server_task: Optional[asyncio.Task] = None
        self._server: Optional[uvicorn.Server] = None
        
        # Setup routes
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup FastAPI routes."""
        
        @self.app.get("/health")
        async def health():
            """Health check endpoint."""
            return {"status": "healthy", "transport": self.name}
        
        @self.app.get("/sse")
        async def sse_endpoint(request: Request):
            """
            SSE endpoint for streaming messages to clients.
            
            Each client gets a unique queue for receiving messages.
            """
            # Create unique client ID
            client_id = str(uuid.uuid4())
            
            # Create queue for this client
            queue = asyncio.Queue()
            self._client_queues[client_id] = queue
            
            logger.info(f"Client {client_id} connected to SSE endpoint")
            
            async def event_generator():
                """Generate SSE events from the client's queue."""
                try:
                    # Send connection established message
                    yield {
                        "event": "connected",
                        "data": json.dumps({"client_id": client_id})
                    }
                    
                    # Stream messages from queue
                    while True:
                        message = await queue.get()
                        if message is None:  # Shutdown signal
                            break
                        
                        yield {
                            "event": "message",
                            "data": json.dumps(message)
                        }
                        
                except asyncio.CancelledError:
                    logger.info(f"Client {client_id} SSE stream cancelled")
                finally:
                    # Cleanup
                    if client_id in self._client_queues:
                        del self._client_queues[client_id]
                    logger.info(f"Client {client_id} disconnected from SSE endpoint")
            
            return EventSourceResponse(event_generator())
        
        @self.app.post("/message")
        async def receive_message(request: Request):
            """
            Endpoint for clients to send messages to the server.
            
            Expects JSON-RPC formatted messages.
            """
            try:
                message = await request.json()
                await self._incoming_messages.put(message)
                return {"status": "received"}
            except Exception as e:
                logger.error(f"Error receiving message: {e}")
                return Response(
                    content=json.dumps({"error": str(e)}),
                    status_code=400,
                    media_type="application/json"
                )
        
        @self.app.get("/clients")
        async def list_clients():
            """List connected clients (for debugging)."""
            return {
                "count": len(self._client_queues),
                "clients": list(self._client_queues.keys())
            }
    
    async def connect(self) -> None:
        """Start the SSE server."""
        if self._connected:
            logger.warning(f"SSE transport {self.name} already connected")
            return
        
        logger.info(f"Starting SSE server on {self.host}:{self.port}")
        
        # Configure uvicorn server
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
            access_log=False,
        )
        self._server = uvicorn.Server(config)
        
        # Start server in background task
        self._server_task = asyncio.create_task(self._server.serve())
        
        # Wait a bit for server to start
        await asyncio.sleep(0.5)
        
        self._connected = True
        logger.info(f"SSE server started at http://{self.host}:{self.port}")
    
    async def disconnect(self) -> None:
        """Stop the SSE server."""
        if not self._connected:
            return
        
        logger.info(f"Stopping SSE server {self.name}")
        
        # Send shutdown signal to all clients
        for queue in self._client_queues.values():
            try:
                await queue.put(None)
            except:
                pass
        
        # Stop server gracefully
        if self._server:
            self._server.should_exit = True
            
            # Wait a bit for graceful shutdown
            await asyncio.sleep(0.1)
        
        if self._server_task and not self._server_task.done():
            self._server_task.cancel()
            try:
                await asyncio.wait_for(self._server_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        
        self._client_queues.clear()
        self._connected = False
        logger.info(f"SSE server {self.name} stopped")
    
    async def send(self, message: Dict[str, Any]) -> None:
        """
        Send a message to all connected clients.
        
        Args:
            message: JSON-RPC message to send.
        
        Raises:
            ConnectionError: If not connected.
        """
        if not self._connected:
            raise ConnectionError(f"SSE transport {self.name} not connected")
        
        # Broadcast to all connected clients
        logger.debug(f"Broadcasting message to {len(self._client_queues)} clients")
        
        for client_id, queue in self._client_queues.items():
            try:
                await queue.put(message)
            except Exception as e:
                logger.error(f"Error sending to client {client_id}: {e}")
    
    async def receive(self) -> Dict[str, Any]:
        """
        Receive a message from any connected client.
        
        Returns:
            JSON-RPC message received.
        
        Raises:
            ConnectionError: If not connected.
        """
        if not self._connected:
            raise ConnectionError(f"SSE transport {self.name} not connected")
        
        message = await self._incoming_messages.get()
        logger.debug(f"Received message: {message}")
        return message
    
    async def messages(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream messages from connected clients.
        
        Yields:
            JSON-RPC messages as they arrive.
        """
        while self._connected:
            try:
                message = await asyncio.wait_for(
                    self._incoming_messages.get(),
                    timeout=1.0
                )
                yield message
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in message stream: {e}")
                break
    
    def get_endpoint_url(self) -> str:
        """Get the SSE endpoint URL."""
        return f"http://{self.host}:{self.port}/sse"
    
    def get_message_url(self) -> str:
        """Get the message POST endpoint URL."""
        return f"http://{self.host}:{self.port}/message"
    
    @property
    def client_count(self) -> int:
        """Get number of connected clients."""
        return len(self._client_queues)


async def create_sse_server(
    name: str = "mcp-sse-server",
    host: str = "0.0.0.0",
    port: int = 8000,
    cors_origins: Optional[list[str]] = None,
) -> SSETransport:
    """
    Create and start an SSE transport server.
    
    Args:
        name: Name of the server.
        host: Host to bind to.
        port: Port to bind to.
        cors_origins: List of allowed CORS origins.
    
    Returns:
        Connected SSE transport instance.
    """
    transport = SSETransport(name, host, port, cors_origins)
    await transport.connect()
    return transport
