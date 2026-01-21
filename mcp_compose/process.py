"""
Process abstraction for MCP servers.

This module provides a Process class representing a managed MCP server process.
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Optional, Any, Dict
import signal

logger = logging.getLogger(__name__)


class ProcessState(str, Enum):
    """States of a managed process."""
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    CRASHED = "crashed"


class Process:
    """
    Represents a managed MCP server process.
    
    Attributes:
        name: Human-readable name for the process.
        command: Command used to start the process.
        state: Current state of the process.
        pid: Process ID (if running).
        started_at: Timestamp when process was started.
        stopped_at: Timestamp when process stopped.
        restart_count: Number of times process has been restarted.
    """
    
    def __init__(self, name: str, command: list[str], env: Optional[Dict[str, str]] = None, working_dir: Optional[str] = None):
        """
        Initialize a Process.
        
        Args:
            name: Human-readable name for the process.
            command: Command and arguments to execute.
            env: Environment variables for the process.
            working_dir: Working directory for the process.
        """
        self.name = name
        self.command = command
        self.env = env or {}
        self.working_dir = working_dir
        
        # State tracking
        self.state = ProcessState.STOPPED
        self.pid: Optional[int] = None
        self.started_at: Optional[datetime] = None
        self.stopped_at: Optional[datetime] = None
        self.restart_count = 0
        
        # Process handle
        self._process: Optional[asyncio.subprocess.Process] = None
        
        # I/O streams
        self._stdin_writer: Optional[asyncio.StreamWriter] = None
        self._stdout_reader: Optional[asyncio.StreamReader] = None
        self._stderr_reader: Optional[asyncio.StreamReader] = None
        
        # Exit code
        self._exit_code: Optional[int] = None
        
    async def start(self) -> None:
        """
        Start the process.
        
        Raises:
            RuntimeError: If process is already running.
        """
        if self.state in (ProcessState.STARTING, ProcessState.RUNNING):
            raise RuntimeError(f"Process {self.name} is already {self.state}")
        
        logger.info(f"Starting process {self.name}: {' '.join(self.command)}")
        self.state = ProcessState.STARTING
        
        try:
            # Start process with STDIO pipes
            self._process = await asyncio.create_subprocess_exec(
                *self.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**self.env} if self.env else None,
                cwd=self.working_dir
            )
            
            # Store streams
            self._stdin_writer = self._process.stdin
            self._stdout_reader = self._process.stdout
            self._stderr_reader = self._process.stderr
            
            # Update state
            self.pid = self._process.pid
            self.started_at = datetime.now()
            self.state = ProcessState.RUNNING
            
            logger.info(f"Process {self.name} started with PID {self.pid}")
            
        except Exception as e:
            logger.error(f"Failed to start process {self.name}: {e}")
            self.state = ProcessState.CRASHED
            raise
    
    async def stop(self, timeout: float = 5.0) -> None:
        """
        Stop the process gracefully.
        
        Args:
            timeout: Seconds to wait for graceful shutdown before forcing.
        
        Raises:
            RuntimeError: If process is not running.
        """
        if self.state not in (ProcessState.STARTING, ProcessState.RUNNING):
            raise RuntimeError(f"Process {self.name} is not running (state: {self.state})")
        
        logger.info(f"Stopping process {self.name} (PID {self.pid})")
        self.state = ProcessState.STOPPING
        
        try:
            # Close stdin to signal process to shutdown
            if self._stdin_writer:
                self._stdin_writer.close()
                await self._stdin_writer.wait_closed()
            
            # Wait for process to exit gracefully
            try:
                await asyncio.wait_for(self._process.wait(), timeout=timeout)
                logger.info(f"Process {self.name} stopped gracefully")
            except asyncio.TimeoutError:
                # Force kill if timeout exceeded
                logger.warning(f"Process {self.name} did not stop gracefully, forcing termination")
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    logger.error(f"Process {self.name} did not terminate, sending SIGKILL")
                    self._process.kill()
                    await self._process.wait()
            
            self._exit_code = self._process.returncode
            self.stopped_at = datetime.now()
            self.state = ProcessState.STOPPED
            
            logger.info(f"Process {self.name} stopped with exit code {self._exit_code}")
            
        except Exception as e:
            logger.error(f"Error stopping process {self.name}: {e}")
            self.state = ProcessState.CRASHED
            raise
    
    async def restart(self) -> None:
        """
        Restart the process.
        
        Stops the process if running, then starts it again.
        """
        logger.info(f"Restarting process {self.name}")
        
        if self.state in (ProcessState.STARTING, ProcessState.RUNNING):
            await self.stop()
        
        await self.start()
        self.restart_count += 1
        
        logger.info(f"Process {self.name} restarted (restart count: {self.restart_count})")
    
    async def write(self, data: bytes) -> None:
        """
        Write data to process stdin.
        
        Args:
            data: Bytes to write.
        
        Raises:
            RuntimeError: If process is not running.
        """
        if self.state != ProcessState.RUNNING:
            raise RuntimeError(f"Cannot write to process {self.name} in state {self.state}")
        
        if not self._stdin_writer:
            raise RuntimeError(f"Process {self.name} has no stdin writer")
        
        self._stdin_writer.write(data)
        await self._stdin_writer.drain()
    
    async def read_stdout(self, n: int = -1) -> bytes:
        """
        Read data from process stdout.
        
        Args:
            n: Number of bytes to read (-1 for all available).
        
        Returns:
            Bytes read from stdout.
        
        Raises:
            RuntimeError: If process is not running.
        """
        if self.state != ProcessState.RUNNING:
            raise RuntimeError(f"Cannot read from process {self.name} in state {self.state}")
        
        if not self._stdout_reader:
            raise RuntimeError(f"Process {self.name} has no stdout reader")
        
        if n == -1:
            return await self._stdout_reader.read()
        else:
            return await self._stdout_reader.read(n)
    
    async def read_stderr(self, n: int = -1) -> bytes:
        """
        Read data from process stderr.
        
        Args:
            n: Number of bytes to read (-1 for all available).
        
        Returns:
            Bytes read from stderr.
        
        Raises:
            RuntimeError: If process is not running.
        """
        if self.state != ProcessState.RUNNING:
            raise RuntimeError(f"Cannot read stderr from process {self.name} in state {self.state}")
        
        if not self._stderr_reader:
            raise RuntimeError(f"Process {self.name} has no stderr reader")
        
        if n == -1:
            return await self._stderr_reader.read()
        else:
            return await self._stderr_reader.read(n)
    
    async def readline_stdout(self) -> bytes:
        """
        Read a line from process stdout.
        
        Returns:
            Line read from stdout (including newline).
        
        Raises:
            RuntimeError: If process is not running.
        """
        if self.state != ProcessState.RUNNING:
            raise RuntimeError(f"Cannot read from process {self.name} in state {self.state}")
        
        if not self._stdout_reader:
            raise RuntimeError(f"Process {self.name} has no stdout reader")
        
        return await self._stdout_reader.readline()
    
    def is_running(self) -> bool:
        """Check if process is currently running."""
        return self.state == ProcessState.RUNNING
    
    @property
    def exit_code(self) -> Optional[int]:
        """Get process exit code (None if still running)."""
        return self._exit_code
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get process information.
        
        Returns:
            Dictionary with process details.
        """
        return {
            "name": self.name,
            "command": " ".join(self.command),
            "state": self.state.value,
            "pid": self.pid,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "restart_count": self.restart_count,
            "exit_code": self._exit_code,
        }
