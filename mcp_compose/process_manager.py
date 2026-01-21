# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Process manager for MCP servers.

This module provides a ProcessManager class for managing multiple MCP server processes.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from .process import Process, ProcessState
from .config import StdioProxiedServerConfig

logger = logging.getLogger(__name__)


class ProcessManager:
    """
    Manages multiple MCP server processes.
    
    Features:
    - Start/stop processes
    - Track process state
    - Auto-restart crashed processes (optional)
    - Health monitoring
    """
    
    def __init__(self, auto_restart: bool = False):
        """
        Initialize the ProcessManager.
        
        Args:
            auto_restart: Whether to automatically restart crashed processes.
        """
        self.auto_restart = auto_restart
        self.processes: Dict[str, Process] = {}
        self._monitor_task: Optional[asyncio.Task] = None
        self._shutdown = False
    
    async def start(self) -> None:
        """Start the process manager and monitoring."""
        logger.info("Starting ProcessManager")
        self._shutdown = False
        
        if self.auto_restart:
            self._monitor_task = asyncio.create_task(self._monitor_processes())
    
    async def stop(self) -> None:
        """Stop the process manager and all processes."""
        logger.info("Stopping ProcessManager")
        self._shutdown = True
        
        # Stop monitoring
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        # Stop all processes
        stop_tasks = []
        for process in self.processes.values():
            if process.is_running():
                stop_tasks.append(process.stop())
        
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)
        
        logger.info("ProcessManager stopped")
    
    async def add_process(
        self,
        name: str,
        command: List[str],
        env: Optional[Dict[str, str]] = None,
        working_dir: Optional[str] = None,
        auto_start: bool = True
    ) -> Process:
        """
        Add a process to manage.
        
        Args:
            name: Unique name for the process.
            command: Command and arguments to execute.
            env: Environment variables for the process.
            working_dir: Working directory for the process.
            auto_start: Whether to start the process immediately.
        
        Returns:
            The created Process instance.
        
        Raises:
            ValueError: If a process with the same name already exists.
        """
        if name in self.processes:
            raise ValueError(f"Process {name} already exists")
        
        logger.info(f"Adding process {name}")
        
        process = Process(name, command, env, working_dir)
        self.processes[name] = process
        
        if auto_start:
            await process.start()
        
        return process
    
    async def add_from_config(
        self,
        config: StdioProxiedServerConfig,
        auto_start: bool = True
    ) -> Process:
        """
        Add a process from configuration.
        
        Args:
            config: Proxied server configuration.
            auto_start: Whether to start the process immediately.
        
        Returns:
            The created Process instance.
        """
        # Command is already a list in the config
        command = config.command
        
        return await self.add_process(
            name=config.name,
            command=command,
            env=config.env,
            working_dir=config.working_dir,
            auto_start=auto_start
        )
    
    async def remove_process(self, name: str) -> None:
        """
        Remove a process from management.
        
        Args:
            name: Name of the process to remove.
        
        Raises:
            KeyError: If process does not exist.
        """
        if name not in self.processes:
            raise KeyError(f"Process {name} not found")
        
        logger.info(f"Removing process {name}")
        
        process = self.processes[name]
        
        # Stop if running
        if process.is_running():
            await process.stop()
        
        del self.processes[name]
    
    async def start_process(self, name: str) -> None:
        """
        Start a specific process.
        
        Args:
            name: Name of the process to start.
        
        Raises:
            KeyError: If process does not exist.
        """
        if name not in self.processes:
            raise KeyError(f"Process {name} not found")
        
        await self.processes[name].start()
    
    async def stop_process(self, name: str, timeout: float = 5.0) -> None:
        """
        Stop a specific process.
        
        Args:
            name: Name of the process to stop.
            timeout: Seconds to wait for graceful shutdown.
        
        Raises:
            KeyError: If process does not exist.
        """
        if name not in self.processes:
            raise KeyError(f"Process {name} not found")
        
        await self.processes[name].stop(timeout)
    
    async def restart_process(self, name: str) -> None:
        """
        Restart a specific process.
        
        Args:
            name: Name of the process to restart.
        
        Raises:
            KeyError: If process does not exist.
        """
        if name not in self.processes:
            raise KeyError(f"Process {name} not found")
        
        await self.processes[name].restart()
    
    def get_process(self, name: str) -> Optional[Process]:
        """
        Get a process by name.
        
        Args:
            name: Name of the process.
        
        Returns:
            Process instance or None if not found.
        """
        return self.processes.get(name)
    
    def list_processes(self) -> List[str]:
        """
        List all managed process names.
        
        Returns:
            List of process names.
        """
        return list(self.processes.keys())
    
    def get_process_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get process information.
        
        Args:
            name: Name of the process.
        
        Returns:
            Process information dictionary or None if not found.
        """
        process = self.get_process(name)
        return process.get_info() if process else None
    
    def get_all_process_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information for all processes.
        
        Returns:
            Dictionary mapping process names to their info.
        """
        return {
            name: process.get_info()
            for name, process in self.processes.items()
        }
    
    async def _monitor_processes(self) -> None:
        """
        Monitor processes and restart crashed ones if auto_restart is enabled.
        
        This runs in a background task.
        """
        logger.info("Process monitoring started")
        
        while not self._shutdown:
            try:
                for name, process in list(self.processes.items()):
                    # Check if process has crashed
                    if process.state == ProcessState.CRASHED:
                        logger.warning(f"Process {name} has crashed")
                        
                        if self.auto_restart:
                            logger.info(f"Auto-restarting process {name}")
                            try:
                                await process.restart()
                            except Exception as e:
                                logger.error(f"Failed to auto-restart process {name}: {e}")
                    
                    # Check if running process has exited
                    elif process.state == ProcessState.RUNNING:
                        if process._process and process._process.returncode is not None:
                            logger.warning(
                                f"Process {name} exited unexpectedly with code {process._process.returncode}"
                            )
                            process.state = ProcessState.CRASHED
                            process._exit_code = process._process.returncode
                            
                            if self.auto_restart:
                                logger.info(f"Auto-restarting process {name}")
                                try:
                                    await process.restart()
                                except Exception as e:
                                    logger.error(f"Failed to auto-restart process {name}: {e}")
                
                # Sleep before next check
                await asyncio.sleep(1.0)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in process monitoring: {e}")
                await asyncio.sleep(1.0)
        
        logger.info("Process monitoring stopped")
    
    async def __aenter__(self):
        """Context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.stop()
