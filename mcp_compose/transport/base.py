"""
Base transport interface for MCP communication.

This module defines the abstract base class for all transport implementations.
"""

import asyncio
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, AsyncIterator, Dict, Optional


class TransportType(str, Enum):
    """Types of MCP transports."""
    STDIO = "stdio"
    SSE = "sse"  # Deprecated: Use STREAMABLE_HTTP instead
    STREAMABLE_HTTP = "streamable-http"  # Recommended modern transport
    WEBSOCKET = "websocket"


class Transport(ABC):
    """
    Abstract base class for MCP transports.
    
    A transport handles the low-level communication with an MCP server,
    abstracting away the underlying protocol (STDIO, SSE, WebSocket, etc.).
    """
    
    def __init__(self, name: str, transport_type: TransportType):
        """
        Initialize the transport.
        
        Args:
            name: Name of this transport instance.
            transport_type: Type of transport.
        """
        self.name = name
        self.transport_type = transport_type
        self._connected = False
    
    @abstractmethod
    async def connect(self) -> None:
        """
        Establish connection to the MCP server.
        
        Raises:
            ConnectionError: If connection fails.
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """
        Close connection to the MCP server.
        """
        pass
    
    @abstractmethod
    async def send(self, message: Dict[str, Any]) -> None:
        """
        Send a message to the MCP server.
        
        Args:
            message: JSON-RPC message to send.
        
        Raises:
            ConnectionError: If not connected.
        """
        pass
    
    @abstractmethod
    async def receive(self) -> Dict[str, Any]:
        """
        Receive a message from the MCP server.
        
        Returns:
            JSON-RPC message received.
        
        Raises:
            ConnectionError: If not connected.
        """
        pass
    
    @abstractmethod
    def messages(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream messages from the MCP server.
        
        Yields:
            JSON-RPC messages as they arrive.
        """
        pass
    
    @property
    def is_connected(self) -> bool:
        """Check if transport is connected."""
        return self._connected
    
    async def __aenter__(self):
        """Context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.disconnect()
