# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Tests for downstream process shutdown on composer exit.

Verifies that all downstream MCP servers (STDIO, SSE, Streamable HTTP)
are properly killed when the composer stops.
"""

import asyncio
import subprocess
import signal
import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from mcp_compose.composer import MCPServerComposer, ConflictResolution
from mcp_compose.process import Process, ProcessState
from mcp_compose.process_manager import ProcessManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_popen_mock(*, alive: bool = True, pid: int = 12345) -> MagicMock:
    """Create a mock subprocess.Popen object.
    
    Args:
        alive: If True, poll() returns None (running). Otherwise returns 0.
        pid: Process ID to assign.
    """
    proc = MagicMock(spec=subprocess.Popen)
    proc.pid = pid
    proc.returncode = None if alive else 0
    proc.poll.return_value = None if alive else 0
    proc.terminate.return_value = None
    proc.kill.return_value = None
    proc.wait.return_value = 0
    return proc


# ---------------------------------------------------------------------------
# Tests for _kill_process
# ---------------------------------------------------------------------------

class TestKillProcess:
    """Tests for MCPServerComposer._kill_process."""

    @pytest.mark.asyncio
    async def test_kill_running_process_graceful(self):
        """Terminate sends SIGTERM and process exits gracefully."""
        composer = MCPServerComposer()
        proc = _make_popen_mock(alive=True, pid=100)

        await composer._kill_process("server-a", proc, timeout=5.0)

        proc.terminate.assert_called_once()
        proc.wait.assert_called_once_with(timeout=5.0)
        # kill() should NOT have been called
        proc.kill.assert_not_called()

    @pytest.mark.asyncio
    async def test_kill_process_escalates_to_sigkill(self):
        """If SIGTERM times out, SIGKILL is sent."""
        composer = MCPServerComposer()
        proc = _make_popen_mock(alive=True, pid=200)
        # First wait (after terminate) raises TimeoutExpired, second wait succeeds
        proc.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="test", timeout=5.0),
            0,
        ]

        await composer._kill_process("server-b", proc, timeout=5.0)

        proc.terminate.assert_called_once()
        proc.kill.assert_called_once()
        assert proc.wait.call_count == 2

    @pytest.mark.asyncio
    async def test_kill_already_exited_process(self):
        """Process that already exited should be skipped (no terminate)."""
        composer = MCPServerComposer()
        proc = _make_popen_mock(alive=False, pid=300)

        await composer._kill_process("server-c", proc, timeout=5.0)

        proc.terminate.assert_not_called()
        proc.kill.assert_not_called()

    @pytest.mark.asyncio
    async def test_kill_non_popen_object(self):
        """Objects without poll() should be skipped gracefully."""
        composer = MCPServerComposer()
        not_a_process = {"pid": 999}  # dict, not Popen

        # Should not raise
        await composer._kill_process("bad-obj", not_a_process, timeout=5.0)

    @pytest.mark.asyncio
    async def test_kill_process_handles_os_error(self):
        """OSError during terminate should be caught."""
        composer = MCPServerComposer()
        proc = _make_popen_mock(alive=True, pid=400)
        proc.terminate.side_effect = OSError("Permission denied")

        # Should not raise
        await composer._kill_process("server-d", proc, timeout=5.0)


# ---------------------------------------------------------------------------
# Tests for shutdown_all_processes
# ---------------------------------------------------------------------------

class TestShutdownAllProcesses:
    """Tests for MCPServerComposer.shutdown_all_processes."""

    @pytest.mark.asyncio
    async def test_shutdown_kills_all_auto_started(self):
        """All auto-started processes in composer.processes are terminated."""
        composer = MCPServerComposer()
        proc1 = _make_popen_mock(alive=True, pid=1001)
        proc2 = _make_popen_mock(alive=True, pid=1002)
        composer.processes = {"sse-server": proc1, "http-server": proc2}

        await composer.shutdown_all_processes()

        proc1.terminate.assert_called_once()
        proc2.terminate.assert_called_once()
        assert len(composer.processes) == 0

    @pytest.mark.asyncio
    async def test_shutdown_stops_process_manager(self):
        """ProcessManager.stop() is called during shutdown."""
        composer = MCPServerComposer(use_process_manager=True)
        composer.process_manager = AsyncMock(spec=ProcessManager)

        await composer.shutdown_all_processes()

        composer.process_manager.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_shutdown_without_process_manager(self):
        """Shutdown works when no process_manager is set."""
        composer = MCPServerComposer()
        assert composer.process_manager is None
        proc = _make_popen_mock(alive=True, pid=2000)
        composer.processes = {"standalone": proc}

        # Should not raise
        await composer.shutdown_all_processes()
        proc.terminate.assert_called_once()
        assert len(composer.processes) == 0

    @pytest.mark.asyncio
    async def test_shutdown_empty_processes(self):
        """Shutdown with no processes is a no-op and does not raise."""
        composer = MCPServerComposer()
        assert len(composer.processes) == 0

        # Should not raise
        await composer.shutdown_all_processes()

    @pytest.mark.asyncio
    async def test_shutdown_mixed_alive_and_exited(self):
        """Only alive processes are terminated; already-exited are skipped."""
        composer = MCPServerComposer()
        alive = _make_popen_mock(alive=True, pid=3001)
        exited = _make_popen_mock(alive=False, pid=3002)
        composer.processes = {"alive-server": alive, "exited-server": exited}

        await composer.shutdown_all_processes()

        alive.terminate.assert_called_once()
        exited.terminate.assert_not_called()
        assert len(composer.processes) == 0

    @pytest.mark.asyncio
    async def test_shutdown_with_custom_timeout(self):
        """Custom timeout is forwarded to wait()."""
        composer = MCPServerComposer()
        proc = _make_popen_mock(alive=True, pid=4000)
        composer.processes = {"custom-timeout": proc}

        await composer.shutdown_all_processes(timeout=10.0)

        proc.wait.assert_called_once_with(timeout=10.0)


# ---------------------------------------------------------------------------
# Tests for composer stop() / context manager
# ---------------------------------------------------------------------------

class TestComposerStop:
    """Tests for MCPServerComposer.stop and context manager."""

    @pytest.mark.asyncio
    async def test_stop_calls_shutdown_all_processes(self):
        """stop() delegates to shutdown_all_processes."""
        composer = MCPServerComposer()
        composer.shutdown_all_processes = AsyncMock()

        await composer.stop()

        composer.shutdown_all_processes.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_context_manager_calls_stop(self):
        """__aexit__ calls stop() which triggers full shutdown."""
        composer = MCPServerComposer()
        proc = _make_popen_mock(alive=True, pid=5000)
        composer.processes = {"ctx-server": proc}

        async with composer:
            assert "ctx-server" in composer.processes

        # After context manager exit, processes should be cleaned up
        proc.terminate.assert_called_once()
        assert len(composer.processes) == 0

    @pytest.mark.asyncio
    async def test_stop_both_process_manager_and_auto_started(self):
        """stop() cleans up both ProcessManager processes and auto-started processes."""
        composer = MCPServerComposer(use_process_manager=True)
        composer.process_manager = AsyncMock(spec=ProcessManager)
        proc = _make_popen_mock(alive=True, pid=6000)
        composer.processes = {"sse-downstream": proc}

        await composer.stop()

        # ProcessManager should be stopped
        composer.process_manager.stop.assert_awaited_once()
        # Auto-started process should be terminated
        proc.terminate.assert_called_once()
        assert len(composer.processes) == 0


# ---------------------------------------------------------------------------
# Integration test with real subprocesses
# ---------------------------------------------------------------------------

class TestShutdownIntegration:
    """Integration tests using real subprocesses."""

    @pytest.mark.asyncio
    async def test_real_subprocess_killed_on_shutdown(self):
        """A real subprocess.Popen process is killed when composer shuts down."""
        composer = MCPServerComposer()

        # Start a real long-running process
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(300)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        composer.processes["long-running"] = proc

        # Verify process is running
        assert proc.poll() is None

        # Shutdown
        await composer.shutdown_all_processes(timeout=3.0)

        # Verify process is dead
        assert proc.poll() is not None
        assert len(composer.processes) == 0

    @pytest.mark.asyncio
    async def test_multiple_real_subprocesses_killed(self):
        """Multiple real subprocesses are all killed on shutdown."""
        composer = MCPServerComposer()

        procs = {}
        for i in range(3):
            p = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(300)"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            name = f"server-{i}"
            procs[name] = p
            composer.processes[name] = p

        # Verify all running
        for p in procs.values():
            assert p.poll() is None

        await composer.shutdown_all_processes(timeout=3.0)

        # Verify all dead
        for p in procs.values():
            assert p.poll() is not None
        assert len(composer.processes) == 0

    @pytest.mark.asyncio
    async def test_stdio_proxied_servers_killed_on_shutdown(self):
        """STDIO proxied servers managed by ProcessManager are killed."""
        composer = MCPServerComposer(use_process_manager=True)
        composer.process_manager = ProcessManager(auto_restart=False)
        await composer.process_manager.start()

        # Add two STDIO proxied servers
        await composer.process_manager.add_process("stdio-server-1", ["cat"])
        await composer.process_manager.add_process("stdio-server-2", ["cat"])
        proc1 = composer.process_manager.get_process("stdio-server-1")
        proc2 = composer.process_manager.get_process("stdio-server-2")
        assert proc1.is_running()
        assert proc2.is_running()

        await composer.shutdown_all_processes(timeout=3.0)

        assert proc1.state == ProcessState.STOPPED
        assert proc2.state == ProcessState.STOPPED

    @pytest.mark.asyncio
    async def test_streamable_http_auto_started_killed_on_shutdown(self):
        """Auto-started Streamable HTTP servers (subprocess.Popen) are killed."""
        composer = MCPServerComposer()

        # Simulate two auto-started Streamable HTTP downstream servers
        http_proc_1 = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(300)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        http_proc_2 = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(300)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        composer.processes["streamable-http-server-1"] = http_proc_1
        composer.processes["streamable-http-server-2"] = http_proc_2

        assert http_proc_1.poll() is None
        assert http_proc_2.poll() is None

        await composer.shutdown_all_processes(timeout=3.0)

        assert http_proc_1.poll() is not None
        assert http_proc_2.poll() is not None
        assert len(composer.processes) == 0

    @pytest.mark.asyncio
    async def test_stdio_and_streamable_http_both_killed_on_shutdown(self):
        """Both STDIO (ProcessManager) and Streamable HTTP (Popen) downstreams
        are killed when the composer shuts down."""
        composer = MCPServerComposer(use_process_manager=True)
        composer.process_manager = ProcessManager(auto_restart=False)
        await composer.process_manager.start()

        # STDIO proxied server via ProcessManager
        await composer.process_manager.add_process("stdio-server", ["cat"])
        stdio_proc = composer.process_manager.get_process("stdio-server")
        assert stdio_proc.is_running()

        # Auto-started Streamable HTTP server via subprocess.Popen
        http_proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(300)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        composer.processes["streamable-http-server"] = http_proc
        assert http_proc.poll() is None

        # Shutdown everything
        await composer.shutdown_all_processes(timeout=3.0)

        # Both should be dead
        assert stdio_proc.state == ProcessState.STOPPED
        assert http_proc.poll() is not None
        assert len(composer.processes) == 0

    @pytest.mark.asyncio
    async def test_process_manager_and_auto_started_integration(self):
        """Both ProcessManager-managed and auto-started processes are killed."""
        composer = MCPServerComposer(use_process_manager=True)
        composer.process_manager = ProcessManager(auto_restart=False)
        await composer.process_manager.start()

        # Add a STDIO proxied server via ProcessManager
        await composer.process_manager.add_process("stdio-server", ["cat"])
        stdio_proc = composer.process_manager.get_process("stdio-server")
        assert stdio_proc.is_running()

        # Add an auto-started SSE server (subprocess.Popen)
        sse_proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(300)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        composer.processes["sse-server"] = sse_proc
        assert sse_proc.poll() is None

        # Shutdown everything
        await composer.shutdown_all_processes(timeout=3.0)

        # Both should be dead
        assert stdio_proc.state == ProcessState.STOPPED
        assert sse_proc.poll() is not None
        assert len(composer.processes) == 0

    @pytest.mark.asyncio
    async def test_stubborn_process_gets_sigkill(self):
        """A process that ignores SIGTERM gets escalated to SIGKILL."""
        composer = MCPServerComposer()

        # Start a process that traps SIGTERM (ignores it)
        proc = subprocess.Popen(
            [sys.executable, "-c",
             "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(300)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        composer.processes["stubborn"] = proc
        assert proc.poll() is None

        # Use a short timeout so SIGKILL is sent quickly
        await composer.shutdown_all_processes(timeout=1.0)

        # Process should be dead via SIGKILL
        assert proc.poll() is not None
        assert len(composer.processes) == 0


# ---------------------------------------------------------------------------
# Tests for signal handler registration
# ---------------------------------------------------------------------------

class TestSignalHandlers:
    """Tests for signal handler registration."""

    @pytest.mark.asyncio
    async def test_register_signal_handlers(self):
        """Signal handlers are registered for SIGTERM and SIGINT."""
        composer = MCPServerComposer()

        original_sigterm = signal.getsignal(signal.SIGTERM)
        original_sigint = signal.getsignal(signal.SIGINT)

        try:
            composer._register_signal_handlers()

            # Handlers should have changed
            new_sigterm = signal.getsignal(signal.SIGTERM)
            new_sigint = signal.getsignal(signal.SIGINT)
            assert new_sigterm != original_sigterm
            assert new_sigint != original_sigint
        finally:
            # Restore original handlers
            signal.signal(signal.SIGTERM, original_sigterm)
            signal.signal(signal.SIGINT, original_sigint)

    @pytest.mark.asyncio
    async def test_start_registers_signal_handlers(self):
        """composer.start() registers signal handlers."""
        composer = MCPServerComposer()
        composer._register_signal_handlers = Mock()

        await composer.start()

        composer._register_signal_handlers.assert_called_once()
