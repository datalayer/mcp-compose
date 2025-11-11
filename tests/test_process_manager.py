"""
Tests for process management.
"""

import asyncio
import pytest
import sys
from mcp_compose.process import Process, ProcessState
from mcp_compose.process_manager import ProcessManager
from mcp_compose.config import StdioProxiedServerConfig


class TestProcess:
    """Tests for Process class."""
    
    @pytest.mark.asyncio
    async def test_process_init(self):
        """Test process initialization."""
        process = Process("test", ["echo", "hello"])
        
        assert process.name == "test"
        assert process.command == ["echo", "hello"]
        assert process.state == ProcessState.STOPPED
        assert process.pid is None
        assert process.started_at is None
        assert process.stopped_at is None
        assert process.restart_count == 0
    
    @pytest.mark.asyncio
    async def test_process_start_stop(self):
        """Test starting and stopping a process."""
        # Use a long-running process
        process = Process("test", ["cat"])
        
        # Start process
        await process.start()
        assert process.state == ProcessState.RUNNING
        assert process.pid is not None
        assert process.started_at is not None
        
        # Stop process
        await process.stop()
        assert process.state == ProcessState.STOPPED
        assert process.stopped_at is not None
        assert process.exit_code is not None
    
    @pytest.mark.asyncio
    async def test_process_write_read(self):
        """Test writing to and reading from process."""
        process = Process("test", ["cat"])
        await process.start()
        
        # Write data
        test_data = b"hello world\n"
        await process.write(test_data)
        
        # Read data back (cat echoes stdin to stdout)
        output = await process.readline_stdout()
        assert output == test_data
        
        await process.stop()
    
    @pytest.mark.asyncio
    async def test_process_restart(self):
        """Test restarting a process."""
        process = Process("test", ["cat"])
        
        await process.start()
        first_pid = process.pid
        
        await process.restart()
        second_pid = process.pid
        
        assert second_pid != first_pid
        assert process.restart_count == 1
        assert process.state == ProcessState.RUNNING
        
        await process.stop()
    
    @pytest.mark.asyncio
    async def test_process_exit_code(self):
        """Test process exit code."""
        # Process that exits with code 0
        process = Process("test", ["sh", "-c", "exit 0"])
        await process.start()
        await asyncio.sleep(0.1)  # Let process exit
        await process.stop()
        
        assert process.exit_code == 0
    
    @pytest.mark.asyncio
    async def test_process_crash_detection(self):
        """Test detection of crashed process."""
        # Process that exits immediately with error
        process = Process("test", ["sh", "-c", "exit 1"])
        await process.start()
        await asyncio.sleep(0.1)  # Let process exit
        
        # Check that process exited
        assert process._process.returncode == 1
        
        await process.stop()
    
    @pytest.mark.asyncio
    async def test_process_info(self):
        """Test getting process information."""
        process = Process("test", ["cat"])
        
        # Before start
        info = process.get_info()
        assert info["name"] == "test"
        assert info["state"] == ProcessState.STOPPED.value
        assert info["pid"] is None
        
        # After start
        await process.start()
        info = process.get_info()
        assert info["state"] == ProcessState.RUNNING.value
        assert info["pid"] is not None
        assert info["started_at"] is not None
        
        await process.stop()
    
    @pytest.mark.asyncio
    async def test_process_double_start_error(self):
        """Test that starting an already running process raises error."""
        process = Process("test", ["cat"])
        await process.start()
        
        with pytest.raises(RuntimeError, match="already"):
            await process.start()
        
        await process.stop()
    
    @pytest.mark.asyncio
    async def test_process_stop_not_running_error(self):
        """Test that stopping a non-running process raises error."""
        process = Process("test", ["cat"])
        
        with pytest.raises(RuntimeError, match="not running"):
            await process.stop()
    
    @pytest.mark.asyncio
    async def test_process_with_env(self):
        """Test process with environment variables."""
        # Use printenv to verify environment variable
        process = Process(
            "test",
            ["sh", "-c", "echo $TEST_VAR"],
            env={"TEST_VAR": "test_value"}
        )
        
        await process.start()
        output = await process.readline_stdout()
        await process.stop()
        
        assert output.strip() == b"test_value"
    
    @pytest.mark.asyncio
    async def test_process_stderr(self):
        """Test reading from stderr."""
        process = Process("test", ["sh", "-c", "echo error >&2"])
        
        await process.start()
        await asyncio.sleep(0.1)  # Let command execute
        
        # Read stderr
        stderr = await process.read_stderr(100)
        
        await process.stop()
        
        assert b"error" in stderr


class TestProcessManager:
    """Tests for ProcessManager class."""
    
    @pytest.mark.asyncio
    async def test_manager_init(self):
        """Test process manager initialization."""
        manager = ProcessManager()
        await manager.start()
        
        assert len(manager.processes) == 0
        assert manager.auto_restart is False
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_manager_add_process(self):
        """Test adding a process to the manager."""
        manager = ProcessManager()
        await manager.start()
        
        process = await manager.add_process("test", ["cat"])
        
        assert "test" in manager.processes
        assert process.state == ProcessState.RUNNING
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_manager_add_process_no_auto_start(self):
        """Test adding a process without auto-starting."""
        manager = ProcessManager()
        await manager.start()
        
        process = await manager.add_process("test", ["cat"], auto_start=False)
        
        assert "test" in manager.processes
        assert process.state == ProcessState.STOPPED
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_manager_remove_process(self):
        """Test removing a process from the manager."""
        manager = ProcessManager()
        await manager.start()
        
        await manager.add_process("test", ["cat"])
        assert "test" in manager.processes
        
        await manager.remove_process("test")
        assert "test" not in manager.processes
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_manager_start_stop_process(self):
        """Test starting and stopping a managed process."""
        manager = ProcessManager()
        await manager.start()
        
        await manager.add_process("test", ["cat"], auto_start=False)
        
        # Start
        await manager.start_process("test")
        process = manager.get_process("test")
        assert process.state == ProcessState.RUNNING
        
        # Stop
        await manager.stop_process("test")
        assert process.state == ProcessState.STOPPED
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_manager_restart_process(self):
        """Test restarting a managed process."""
        manager = ProcessManager()
        await manager.start()
        
        await manager.add_process("test", ["cat"])
        process = manager.get_process("test")
        first_pid = process.pid
        
        await manager.restart_process("test")
        second_pid = process.pid
        
        assert second_pid != first_pid
        assert process.restart_count == 1
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_manager_get_process(self):
        """Test getting a process from the manager."""
        manager = ProcessManager()
        await manager.start()
        
        await manager.add_process("test", ["cat"])
        
        process = manager.get_process("test")
        assert process is not None
        assert process.name == "test"
        
        assert manager.get_process("nonexistent") is None
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_manager_list_processes(self):
        """Test listing all processes."""
        manager = ProcessManager()
        await manager.start()
        
        await manager.add_process("test1", ["cat"])
        await manager.add_process("test2", ["cat"])
        
        names = manager.list_processes()
        assert set(names) == {"test1", "test2"}
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_manager_get_process_info(self):
        """Test getting process information."""
        manager = ProcessManager()
        await manager.start()
        
        await manager.add_process("test", ["cat"])
        
        info = manager.get_process_info("test")
        assert info is not None
        assert info["name"] == "test"
        assert info["state"] == ProcessState.RUNNING.value
        
        assert manager.get_process_info("nonexistent") is None
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_manager_get_all_process_info(self):
        """Test getting all process information."""
        manager = ProcessManager()
        await manager.start()
        
        await manager.add_process("test1", ["cat"])
        await manager.add_process("test2", ["cat"])
        
        all_info = manager.get_all_process_info()
        assert len(all_info) == 2
        assert "test1" in all_info
        assert "test2" in all_info
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_manager_context_manager(self):
        """Test using ProcessManager as context manager."""
        async with ProcessManager() as manager:
            await manager.add_process("test", ["cat"])
            assert "test" in manager.processes
        
        # Manager should be stopped after context exit
        assert manager._shutdown is True
    
    @pytest.mark.asyncio
    async def test_manager_add_from_config(self):
        """Test adding a process from configuration."""
        manager = ProcessManager()
        await manager.start()
        
        config = StdioProxiedServerConfig(
            name="test_server",
            command=["cat"]
        )
        
        process = await manager.add_from_config(config)
        
        assert process.name == "test_server"
        assert process.state == ProcessState.RUNNING
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_manager_add_from_config_no_auto_start(self):
        """Test adding a process from configuration without auto-start."""
        manager = ProcessManager()
        await manager.start()
        
        config = StdioProxiedServerConfig(
            name="test_server",
            command=["cat"]
        )
        
        process = await manager.add_from_config(config, auto_start=False)
        
        assert process.name == "test_server"
        assert process.state == ProcessState.STOPPED
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_manager_duplicate_process_error(self):
        """Test that adding duplicate process raises error."""
        manager = ProcessManager()
        await manager.start()
        
        await manager.add_process("test", ["cat"])
        
        with pytest.raises(ValueError, match="already exists"):
            await manager.add_process("test", ["cat"])
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_manager_auto_restart(self):
        """Test auto-restart functionality."""
        manager = ProcessManager(auto_restart=True)
        await manager.start()
        
        # Add process that exits immediately
        await manager.add_process("test", ["sh", "-c", "exit 1"])
        process = manager.get_process("test")
        
        # Wait for process to exit and auto-restart
        await asyncio.sleep(2.0)
        
        # Should have been restarted
        assert process.restart_count >= 1
        
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_manager_stop_all_processes(self):
        """Test that stopping manager stops all processes."""
        manager = ProcessManager()
        await manager.start()
        
        await manager.add_process("test1", ["cat"])
        await manager.add_process("test2", ["cat"])
        
        await manager.stop()
        
        # All processes should be stopped
        for process in manager.processes.values():
            assert process.state == ProcessState.STOPPED
