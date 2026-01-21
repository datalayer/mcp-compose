# Copyright (c) 2023-2025 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
STDIO transport implementation for MCP communication.

This module implements the Transport interface for MCP servers that communicate
via standard input/output (STDIO).
"""

import asyncio
import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from .base import Transport, TransportType

logger = logging.getLogger(__name__)


class STDIOTransport(Transport):
    """
    STDIO-based transport for MCP communication.
    
    This transport communicates with an MCP server process via stdin/stdout,
    using JSON-RPC messages delimited by newlines.
    """
    
    def __init__(
        self,
        name: str,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
    ):
        """
        Initialize STDIO transport.
        
        Args:
            name: Name of this transport instance.
            command: Command to execute (e.g., "python", "node").
            args: Arguments to pass to the command.
            env: Environment variables for the process.
            cwd: Working directory for the process.
        """
        super().__init__(name, TransportType.STDIO)
        self.command = command
        self.args = args or []
        self.env = env
        self.cwd = cwd
        self._process: Optional[asyncio.subprocess.Process] = None
        self._read_task: Optional[asyncio.Task] = None
        self._message_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self._stderr_task: Optional[asyncio.Task] = None
    
    async def connect(self) -> None:
        """
        Start the MCP server process and establish STDIO connection.
        
        Raises:
            ConnectionError: If process fails to start.
        """
        if self._connected:
            logger.warning(f"Transport {self.name} already connected")
            return
        
        try:
            # Build command with arguments
            cmd = [self.command] + self.args
            
            logger.info(f"Starting STDIO process: {' '.join(cmd)}")
            
            # Start the subprocess
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self.env,
                cwd=self.cwd,
            )
            
            # Start background task to read stdout
            self._read_task = asyncio.create_task(self._read_stdout())
            
            # Start background task to read stderr (for logging)
            self._stderr_task = asyncio.create_task(self._read_stderr())
            
            self._connected = True
            logger.info(f"STDIO transport {self.name} connected (PID: {self._process.pid})")
            
        except Exception as e:
            logger.error(f"Failed to start STDIO process: {e}")
            await self._cleanup()
            raise ConnectionError(f"Failed to connect STDIO transport: {e}")
    
    async def disconnect(self) -> None:
        """
        Stop the MCP server process and close STDIO connection.
        """
        if not self._connected:
            logger.warning(f"Transport {self.name} not connected")
            return
        
        logger.info(f"Disconnecting STDIO transport {self.name}")
        
        await self._cleanup()
        
        self._connected = False
        logger.info(f"STDIO transport {self.name} disconnected")
    
    async def send(self, message: Dict[str, Any]) -> None:
        """
        Send a JSON-RPC message to the MCP server via stdin.
        
        Args:
            message: JSON-RPC message to send.
        
        Raises:
            ConnectionError: If not connected.
        """
        if not self._connected or not self._process or not self._process.stdin:
            raise ConnectionError(f"Transport {self.name} not connected")
        
        try:
            # Serialize message to JSON and add newline
            json_str = json.dumps(message) + "\n"
            
            # Write to stdin
            self._process.stdin.write(json_str.encode("utf-8"))
            await self._process.stdin.drain()
            
            logger.debug(f"Sent message to {self.name}: {message.get('method', 'response')}")
            
        except Exception as e:
            logger.error(f"Failed to send message to {self.name}: {e}")
            raise ConnectionError(f"Failed to send message: {e}")
    
    async def receive(self) -> Dict[str, Any]:
        """
        Receive a JSON-RPC message from the MCP server via stdout.
        
        Returns:
            JSON-RPC message received.
        
        Raises:
            ConnectionError: If not connected.
        """
        if not self._connected:
            raise ConnectionError(f"Transport {self.name} not connected")
        
        try:
            # Get message from queue (populated by _read_stdout)
            message = await self._message_queue.get()
            logger.debug(f"Received message from {self.name}: {message.get('method', 'response')}")
            return message
            
        except Exception as e:
            logger.error(f"Failed to receive message from {self.name}: {e}")
            raise ConnectionError(f"Failed to receive message: {e}")
    
    async def messages(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream messages from the MCP server.
        
        Yields:
            JSON-RPC messages as they arrive.
        """
        if not self._connected:
            raise ConnectionError(f"Transport {self.name} not connected")
        
        try:
            while self._connected:
                message = await self.receive()
                yield message
        except asyncio.CancelledError:
            logger.debug(f"Message stream for {self.name} cancelled")
        except Exception as e:
            logger.error(f"Error in message stream for {self.name}: {e}")
            raise
    
    async def _read_stdout(self) -> None:
        """Background task to read stdout and populate message queue."""
        if not self._process or not self._process.stdout:
            return
        
        try:
            while self._connected:
                # Read line from stdout
                line = await self._process.stdout.readline()
                
                if not line:
                    # EOF reached - process terminated
                    logger.warning(f"STDIO process {self.name} stdout closed")
                    break
                
                try:
                    # Parse JSON message
                    message = json.loads(line.decode("utf-8").strip())
                    await self._message_queue.put(message)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON from {self.name}: {line.decode('utf-8', errors='replace')}")
                    logger.error(f"JSON decode error: {e}")
                    
        except asyncio.CancelledError:
            logger.debug(f"stdout reader for {self.name} cancelled")
        except Exception as e:
            logger.error(f"Error reading stdout from {self.name}: {e}")
    
    async def _read_stderr(self) -> None:
        """Background task to read stderr for logging."""
        if not self._process or not self._process.stderr:
            return
        
        try:
            while self._connected:
                line = await self._process.stderr.readline()
                
                if not line:
                    break
                
                # Log stderr output
                stderr_msg = line.decode("utf-8", errors="replace").strip()
                if stderr_msg:
                    logger.warning(f"[{self.name} stderr]: {stderr_msg}")
                    
        except asyncio.CancelledError:
            logger.debug(f"stderr reader for {self.name} cancelled")
        except Exception as e:
            logger.error(f"Error reading stderr from {self.name}: {e}")
    
    async def _cleanup(self) -> None:
        """Clean up process and background tasks."""
        # Cancel background tasks
        if self._read_task:
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
            self._read_task = None
        
        if self._stderr_task:
            self._stderr_task.cancel()
            try:
                await self._stderr_task
            except asyncio.CancelledError:
                pass
            self._stderr_task = None
        
        # Terminate process
        if self._process:
            try:
                # Try graceful termination first
                if self._process.returncode is None:
                    self._process.terminate()
                    
                    try:
                        await asyncio.wait_for(self._process.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        # Force kill if graceful termination fails
                        logger.warning(f"Process {self.name} did not terminate gracefully, killing")
                        self._process.kill()
                        await self._process.wait()
                        
            except Exception as e:
                logger.error(f"Error cleaning up process {self.name}: {e}")
            finally:
                self._process = None
        
        # Clear message queue
        while not self._message_queue.empty():
            try:
                self._message_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
    
    @property
    def pid(self) -> Optional[int]:
        """Get process ID if running."""
        return self._process.pid if self._process else None
    
    @property
    def returncode(self) -> Optional[int]:
        """Get process return code if terminated."""
        return self._process.returncode if self._process else None


def create_stdio_transport(
    name: str,
    command: str,
    args: Optional[List[str]] = None,
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
) -> STDIOTransport:
    """
    Create a new STDIO transport instance.
    
    Args:
        name: Name of the transport.
        command: Command to execute.
        args: Arguments to pass to the command.
        env: Environment variables for the process.
        cwd: Working directory for the process.
    
    Returns:
        New STDIOTransport instance.
    """
    return STDIOTransport(name, command, args, env, cwd)
