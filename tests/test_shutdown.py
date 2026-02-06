# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Tests for downstream process shutdown on composer exit.

Verifies that all downstream MCP servers (STDIO, SSE, Streamable HTTP)
are properly killed when the composer stops.
"""

import subprocess
import signal
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from mcp_compose.composer import (
    MCPServerComposer,
    ConflictResolution,
    _active_composers,
    _install_signal_handlers,
    _uninstall_signal_handlers,
    _register_composer,
    _unregister_composer,
    _module_signal_handler,
)
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
        proc.wait.assert_called_once_with(5.0)
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

    @pytest.mark.asyncio
    async def test_kill_process_without_pid_attribute(self):
        """Object with poll() but no pid attribute should not raise AttributeError."""
        composer = MCPServerComposer()
        # Custom object that has poll (so it passes the guard) but no pid
        fake = MagicMock(spec=[])
        fake.poll = MagicMock(return_value=0)  # already exited

        # Should not raise
        await composer._kill_process("no-pid-obj", fake, timeout=5.0)


# ---------------------------------------------------------------------------
# Tests for _close_process_pipes
# ---------------------------------------------------------------------------

class TestCloseProcessPipes:
    """Tests for MCPServerComposer._close_process_pipes."""

    def test_closes_all_three_pipes(self):
        """stdin, stdout, and stderr are all closed."""
        proc = MagicMock(spec=subprocess.Popen)
        proc.stdin = MagicMock()
        proc.stdout = MagicMock()
        proc.stderr = MagicMock()

        MCPServerComposer._close_process_pipes("server-a", proc)

        proc.stdin.close.assert_called_once()
        proc.stdout.close.assert_called_once()
        proc.stderr.close.assert_called_once()

    def test_handles_none_pipes(self):
        """Pipes that are None are silently skipped."""
        proc = MagicMock(spec=subprocess.Popen)
        proc.stdin = None
        proc.stdout = None
        proc.stderr = None

        # Should not raise
        MCPServerComposer._close_process_pipes("server-b", proc)

    def test_partial_none_pipes(self):
        """Only non-None pipes are closed."""
        proc = MagicMock(spec=subprocess.Popen)
        proc.stdin = MagicMock()
        proc.stdout = None
        proc.stderr = MagicMock()

        MCPServerComposer._close_process_pipes("server-c", proc)

        proc.stdin.close.assert_called_once()
        proc.stderr.close.assert_called_once()

    def test_exception_during_close_is_swallowed(self):
        """An exception from pipe.close() does not propagate."""
        proc = MagicMock(spec=subprocess.Popen)
        proc.stdin = MagicMock()
        proc.stdin.close.side_effect = OSError("Broken pipe")
        proc.stdout = MagicMock()
        proc.stderr = MagicMock()

        # Should not raise
        MCPServerComposer._close_process_pipes("server-d", proc)

        # stdout and stderr should still be closed despite stdin failure
        proc.stdout.close.assert_called_once()
        proc.stderr.close.assert_called_once()

    def test_all_pipes_raise_exceptions(self):
        """Even if every pipe.close() raises, no exception propagates."""
        proc = MagicMock(spec=subprocess.Popen)
        proc.stdin = MagicMock()
        proc.stdin.close.side_effect = OSError("stdin broken")
        proc.stdout = MagicMock()
        proc.stdout.close.side_effect = BrokenPipeError("stdout broken")
        proc.stderr = MagicMock()
        proc.stderr.close.side_effect = RuntimeError("stderr broken")

        # Should not raise
        MCPServerComposer._close_process_pipes("server-e", proc)

        proc.stdin.close.assert_called_once()
        proc.stdout.close.assert_called_once()
        proc.stderr.close.assert_called_once()

    def test_already_closed_pipe(self):
        """Closing an already-closed pipe (ValueError) is handled."""
        proc = MagicMock(spec=subprocess.Popen)
        proc.stdin = MagicMock()
        proc.stdin.close.side_effect = ValueError("I/O operation on closed file")
        proc.stdout = MagicMock()
        proc.stderr = MagicMock()

        # Should not raise
        MCPServerComposer._close_process_pipes("server-f", proc)

        proc.stdout.close.assert_called_once()
        proc.stderr.close.assert_called_once()

    def test_object_without_pipe_attributes(self):
        """An object missing stdin/stdout/stderr attributes is handled."""
        proc = MagicMock(spec=[])  # No attributes at all

        # Should not raise
        MCPServerComposer._close_process_pipes("bare-obj", proc)

    def test_real_subprocess_pipes_closed(self):
        """Pipes from a real subprocess.Popen are closed without error."""
        proc = subprocess.Popen(
            [sys.executable, "-c", "pass"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        proc.wait()  # Let it finish

        MCPServerComposer._close_process_pipes("real-proc", proc)

        # Pipes should be closed – writing to them should raise
        assert proc.stdin.closed
        assert proc.stdout.closed
        assert proc.stderr.closed

    def test_real_subprocess_double_close(self):
        """Closing pipes twice on a real subprocess does not raise."""
        proc = subprocess.Popen(
            [sys.executable, "-c", "pass"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        proc.wait()

        MCPServerComposer._close_process_pipes("real-proc", proc)
        # Second call – pipes already closed
        MCPServerComposer._close_process_pipes("real-proc", proc)

        assert proc.stdin.closed
        assert proc.stdout.closed
        assert proc.stderr.closed


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

        proc.wait.assert_called_once_with(10.0)


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

    @pytest.mark.asyncio
    async def test_stop_is_idempotent(self):
        """Calling stop() twice does not terminate processes twice."""
        composer = MCPServerComposer()
        proc = _make_popen_mock(alive=True, pid=7000)
        composer.processes = {"idempotent-server": proc}

        await composer.stop()
        proc.terminate.assert_called_once()
        assert len(composer.processes) == 0

        # Second call should be a no-op
        await composer.stop()
        # terminate should still have been called only once
        proc.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_stop_calls(self):
        """Two concurrent stop() calls do not both attempt shutdown."""
        composer = MCPServerComposer()
        proc = _make_popen_mock(alive=True, pid=8000)
        composer.processes = {"concurrent-server": proc}

        # Run two stop() calls concurrently
        await asyncio.gather(composer.stop(), composer.stop())

        # terminate should have been called exactly once
        proc.terminate.assert_called_once()
        assert len(composer.processes) == 0

    @pytest.mark.asyncio
    async def test_shutdown_all_processes_is_idempotent(self):
        """Calling shutdown_all_processes() twice is safe."""
        composer = MCPServerComposer()
        proc = _make_popen_mock(alive=True, pid=9000)
        composer.processes = {"idem-server": proc}

        await composer.shutdown_all_processes()
        proc.terminate.assert_called_once()
        assert len(composer.processes) == 0

        # Second call should be a no-op (flag is still set)
        await composer.shutdown_all_processes()
        proc.terminate.assert_called_once()


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
    @pytest.mark.skipif(sys.platform == "win32", reason="SIGTERM not available on Windows")
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
# Tests for module-level signal handler registry
# ---------------------------------------------------------------------------

class TestSignalHandlerRegistry:
    """Tests for the module-level composer registry and signal handlers."""

    def _cleanup_registry(self):
        """Remove all composers from the registry and restore signals."""
        _active_composers.clear()
        _uninstall_signal_handlers()

    @pytest.mark.asyncio
    async def test_init_registers_composer(self):
        """MCPServerComposer.__init__ registers the instance in the module registry."""
        self._cleanup_registry()
        try:
            composer = MCPServerComposer()
            assert composer in _active_composers
        finally:
            self._cleanup_registry()

    @pytest.mark.asyncio
    async def test_stop_unregisters_composer(self):
        """stop() removes the composer from the module registry."""
        self._cleanup_registry()
        try:
            composer = MCPServerComposer()
            assert composer in _active_composers
            await composer.stop()
            assert composer not in _active_composers
        finally:
            self._cleanup_registry()

    @pytest.mark.asyncio
    async def test_multiple_instances_all_registered(self):
        """Multiple composer instances all appear in the registry."""
        self._cleanup_registry()
        try:
            c1 = MCPServerComposer(composed_server_name="c1")
            c2 = MCPServerComposer(composed_server_name="c2")
            c3 = MCPServerComposer(composed_server_name="c3")
            assert c1 in _active_composers
            assert c2 in _active_composers
            assert c3 in _active_composers
            assert len(_active_composers) == 3
        finally:
            self._cleanup_registry()

    @pytest.mark.asyncio
    async def test_stop_one_leaves_others_registered(self):
        """Stopping one composer does not affect the others."""
        self._cleanup_registry()
        try:
            c1 = MCPServerComposer(composed_server_name="c1")
            c2 = MCPServerComposer(composed_server_name="c2")
            await c1.stop()
            assert c1 not in _active_composers
            assert c2 in _active_composers
            assert len(_active_composers) == 1
        finally:
            self._cleanup_registry()

    @pytest.mark.asyncio
    async def test_signal_handlers_installed_on_first_registration(self):
        """Signal handlers are installed when the first composer is created."""
        self._cleanup_registry()
        original_sigterm = signal.getsignal(signal.SIGTERM)
        original_sigint = signal.getsignal(signal.SIGINT)
        try:
            _composer = MCPServerComposer()
            assert signal.getsignal(signal.SIGTERM) is _module_signal_handler
            assert signal.getsignal(signal.SIGINT) is _module_signal_handler
        finally:
            self._cleanup_registry()
            signal.signal(signal.SIGTERM, original_sigterm)
            signal.signal(signal.SIGINT, original_sigint)

    @pytest.mark.asyncio
    async def test_signal_handlers_restored_on_last_unregister(self):
        """Original signal handlers are restored when the last composer stops."""
        self._cleanup_registry()
        original_sigterm = signal.getsignal(signal.SIGTERM)
        original_sigint = signal.getsignal(signal.SIGINT)
        try:
            composer = MCPServerComposer()
            # Handlers are now _module_signal_handler
            assert signal.getsignal(signal.SIGTERM) is _module_signal_handler
            await composer.stop()
            # After the last composer unregisters, originals should be restored
            assert signal.getsignal(signal.SIGTERM) is not _module_signal_handler
            assert signal.getsignal(signal.SIGINT) is not _module_signal_handler
        finally:
            self._cleanup_registry()
            signal.signal(signal.SIGTERM, original_sigterm)
            signal.signal(signal.SIGINT, original_sigint)

    @pytest.mark.asyncio
    async def test_handlers_not_registered_without_start(self):
        """Signal handlers are installed from __init__, no start() needed."""
        self._cleanup_registry()
        original_sigterm = signal.getsignal(signal.SIGTERM)
        try:
            # Just construct – never call start()
            composer = MCPServerComposer()
            assert composer in _active_composers
            assert signal.getsignal(signal.SIGTERM) is _module_signal_handler
        finally:
            self._cleanup_registry()
            signal.signal(signal.SIGTERM, original_sigterm)

    @pytest.mark.asyncio
    async def test_multiple_stops_are_safe(self):
        """Calling stop() multiple times on the same composer is a no-op."""
        self._cleanup_registry()
        try:
            composer = MCPServerComposer()
            await composer.stop()
            await composer.stop()  # Second call should not raise
            assert composer not in _active_composers
        finally:
            self._cleanup_registry()

    @pytest.mark.asyncio
    async def test_signal_handler_schedules_stop_for_all(self):
        """The module-level signal handler schedules stop() for every registered composer."""
        self._cleanup_registry()
        try:
            c1 = MCPServerComposer(composed_server_name="c1")
            c2 = MCPServerComposer(composed_server_name="c2")
            c1.stop = AsyncMock()
            c2.stop = AsyncMock()

            # Simulate signal delivery
            _module_signal_handler(signal.SIGTERM, None)

            # Let the event loop run so the scheduled futures execute
            await asyncio.sleep(0.05)

            c1.stop.assert_awaited_once()
            c2.stop.assert_awaited_once()
        finally:
            self._cleanup_registry()

    def test_signal_handler_no_running_loop(self):
        """Signal handler gracefully handles missing event loop (sync context)."""
        self._cleanup_registry()
        try:
            _composer = MCPServerComposer(composed_server_name="no-loop")

            # Called from a plain sync function — no running event loop.
            # Should not raise; just logs a warning and returns.
            _module_signal_handler(signal.SIGTERM, None)
        finally:
            self._cleanup_registry()

    @pytest.mark.asyncio
    async def test_signal_handler_closed_loop(self):
        """Signal handler gracefully handles a closed event loop."""
        self._cleanup_registry()
        try:
            _composer = MCPServerComposer(composed_server_name="closed-loop")

            # Patch get_running_loop to return a closed loop
            closed_loop = asyncio.new_event_loop()
            closed_loop.close()

            with patch("mcp_compose.composer.asyncio.get_running_loop", return_value=closed_loop):
                # Should not raise
                _module_signal_handler(signal.SIGTERM, None)
        finally:
            self._cleanup_registry()
