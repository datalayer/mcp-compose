# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Tests for the prune-downstreams-on-start feature.

Covers:
- Config option ``prune_downstreams_on_start``
- CLI flag ``--prune-downstreams-on-start``
- Process-matching logic in ``MCPServerComposer``
- Kill logic with SIGTERM / SIGKILL escalation
"""

import os
import signal
import subprocess
import sys
import time
from unittest.mock import patch

import pytest

from mcp_compose.cli import create_parser
from mcp_compose.composer import MCPServerComposer
from mcp_compose.config import (
    ComposerConfig,
    MCPComposerConfig,
    ProxiedServersConfig,
    ServersConfig,
    SseProxiedServerConfig,
    StdioProxiedServerConfig,
    StreamableHttpProxiedServerConfig,
)

# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestPruneConfig:
    """Test that the config model accepts the new field."""

    def test_default_is_false(self):
        config = ComposerConfig()
        assert config.prune_downstreams_on_start is False

    def test_can_enable(self):
        config = ComposerConfig(prune_downstreams_on_start=True)
        assert config.prune_downstreams_on_start is True

    def test_full_config_round_trip(self):
        cfg = MCPComposerConfig(
            composer=ComposerConfig(prune_downstreams_on_start=True),
        )
        assert cfg.composer.prune_downstreams_on_start is True


# ---------------------------------------------------------------------------
# CLI argument tests
# ---------------------------------------------------------------------------


class TestPruneCLIArg:
    """Test that the CLI parser accepts the new flag."""

    def test_flag_absent_defaults_none(self):
        parser = create_parser()
        args = parser.parse_args(["serve"])
        assert args.prune_downstreams_on_start is None

    def test_flag_present_sets_true(self):
        parser = create_parser()
        args = parser.parse_args(["serve", "--prune-downstreams-on-start"])
        assert args.prune_downstreams_on_start is True


# ---------------------------------------------------------------------------
# _find_matching_pids tests
# ---------------------------------------------------------------------------


class TestFindMatchingPids:
    """Test the static process-scanning helper."""

    def test_returns_empty_when_no_match(self):
        # A command that is extremely unlikely to be running
        pids = MCPServerComposer._find_matching_pids(
            ["__mcp_compose_test_nonexistent_binary_42__"],
            exclude_pid=os.getpid(),
        )
        assert pids == []

    def test_excludes_own_pid(self):
        """Even if our cmdline partially matches, we should be excluded."""
        pids = MCPServerComposer._find_matching_pids(
            ["python"],  # our own process is a python process
            exclude_pid=os.getpid(),
        )
        assert os.getpid() not in pids

    @pytest.mark.skipif(
        not os.path.exists("/proc"),
        reason="Requires /proc filesystem (Linux)",
    )
    def test_finds_known_process(self):
        """Start a subprocess and verify it is found."""
        proc = subprocess.Popen(
            ["sleep", "300"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            time.sleep(0.3)  # let it appear in /proc
            pids = MCPServerComposer._find_matching_pids(
                ["sleep", "300"],
                exclude_pid=os.getpid(),
            )
            assert proc.pid in pids
        finally:
            proc.kill()
            proc.wait()


# ---------------------------------------------------------------------------
# _kill_pid tests
# ---------------------------------------------------------------------------


class TestKillPid:
    """Test the static PID-killing helper."""

    def test_kill_nonexistent_pid(self):
        """Should not raise for a PID that does not exist."""
        # PID 0 is special; use a very high PID that is almost certainly unused
        MCPServerComposer._kill_pid(2**30, timeout=0.5)

    @pytest.mark.skipif(
        not os.path.exists("/proc"),
        reason="Requires /proc filesystem (Linux)",
    )
    def test_kill_real_process(self):
        """Start a sleep, kill it, verify it's gone."""
        proc = subprocess.Popen(
            ["sleep", "300"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.2)
        MCPServerComposer._kill_pid(proc.pid, timeout=2.0)
        # Process should now be dead
        ret = proc.wait(timeout=3)
        assert ret is not None  # exited


# ---------------------------------------------------------------------------
# prune_downstreams integration tests
# ---------------------------------------------------------------------------


class TestPruneDownstreams:
    """Test the full prune_downstreams() method."""

    @pytest.mark.asyncio
    async def test_no_config_returns_zero(self):
        composer = MCPServerComposer()
        result = await composer.prune_downstreams()
        assert result == 0

    @pytest.mark.asyncio
    async def test_no_servers_returns_zero(self):
        config = MCPComposerConfig()
        composer = MCPServerComposer(config=config)
        result = await composer.prune_downstreams()
        assert result == 0

    @pytest.mark.asyncio
    async def test_prune_with_no_dangling(self):
        """Config with a server whose command is not running."""
        config = MCPComposerConfig(
            servers=ServersConfig(
                proxied=ProxiedServersConfig(
                    stdio=[
                        StdioProxiedServerConfig(
                            name="ghost",
                            command=["__mcp_compose_test_nonexistent_binary_42__"],
                        )
                    ]
                )
            )
        )
        composer = MCPServerComposer(config=config)
        result = await composer.prune_downstreams()
        assert result == 0

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.path.exists("/proc"),
        reason="Requires /proc filesystem (Linux)",
    )
    async def test_prune_kills_dangling_process(self):
        """Start a real process, prune should find and kill it."""
        proc = subprocess.Popen(
            ["sleep", "7654"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            time.sleep(0.3)

            config = MCPComposerConfig(
                servers=ServersConfig(
                    proxied=ProxiedServersConfig(
                        stdio=[
                            StdioProxiedServerConfig(
                                name="dangling-sleep",
                                command=["sleep", "7654"],
                            )
                        ]
                    )
                )
            )
            composer = MCPServerComposer(config=config)
            result = await composer.prune_downstreams()

            assert result >= 1
            # Process should be dead
            ret = proc.wait(timeout=5)
            assert ret is not None
        finally:
            # Safety net
            try:
                proc.kill()
                proc.wait(timeout=2)
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_prune_collects_sse_and_streamable_http(self):
        """Verify that SSE and Streamable HTTP auto-start commands are included."""
        config = MCPComposerConfig(
            servers=ServersConfig(
                proxied=ProxiedServersConfig(
                    sse=[
                        SseProxiedServerConfig(
                            name="sse-srv",
                            url="http://localhost:9999/sse",
                            auto_start=True,
                            command=["__nonexistent_sse_42__"],
                        )
                    ],
                    **{
                        "streamable-http": [
                            StreamableHttpProxiedServerConfig(
                                name="http-srv",
                                url="http://localhost:9998/mcp",
                                auto_start=True,
                                command=["__nonexistent_http_42__"],
                            )
                        ]
                    },
                )
            )
        )
        composer = MCPServerComposer(config=config)
        # Nothing running, but we verify no crash and zero result
        result = await composer.prune_downstreams()
        assert result == 0

    @pytest.mark.asyncio
    async def test_prune_skips_non_autostart_sse(self):
        """SSE servers without auto_start should not be pruned."""
        config = MCPComposerConfig(
            servers=ServersConfig(
                proxied=ProxiedServersConfig(
                    sse=[
                        SseProxiedServerConfig(
                            name="sse-external",
                            url="http://localhost:9999/sse",
                            auto_start=False,
                            command=["sleep", "999"],
                        )
                    ],
                )
            )
        )
        composer = MCPServerComposer(config=config)
        # Should not even look for this command
        with patch.object(MCPServerComposer, "_find_matching_pids", return_value=[]) as mock_find:
            result = await composer.prune_downstreams()
            assert result == 0
            mock_find.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.path.exists("/proc"),
        reason="Requires /proc filesystem (Linux)",
    )
    async def test_prune_multiple_dangling_processes(self):
        """Prune should find and kill multiple orphans for different servers."""
        procs = []
        try:
            for tag in ("8801", "8802"):
                p = subprocess.Popen(
                    ["sleep", tag],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                procs.append((tag, p))
            time.sleep(0.3)

            config = MCPComposerConfig(
                servers=ServersConfig(
                    proxied=ProxiedServersConfig(
                        stdio=[
                            StdioProxiedServerConfig(
                                name=f"srv-{tag}",
                                command=["sleep", tag],
                            )
                            for tag, _ in procs
                        ]
                    )
                )
            )
            composer = MCPServerComposer(config=config)
            result = await composer.prune_downstreams()

            assert result >= 2
            for _, p in procs:
                ret = p.wait(timeout=5)
                assert ret is not None
        finally:
            for _, p in procs:
                try:
                    p.kill()
                    p.wait(timeout=2)
                except Exception:
                    pass

    @pytest.mark.asyncio
    async def test_prune_skips_non_autostart_streamable_http(self):
        """Streamable HTTP servers without auto_start should not be pruned."""
        config = MCPComposerConfig(
            servers=ServersConfig(
                proxied=ProxiedServersConfig(
                    **{
                        "streamable-http": [
                            StreamableHttpProxiedServerConfig(
                                name="http-external",
                                url="http://localhost:9998/mcp",
                                auto_start=False,
                                command=["sleep", "888"],
                            )
                        ]
                    },
                )
            )
        )
        composer = MCPServerComposer(config=config)
        with patch.object(MCPServerComposer, "_find_matching_pids", return_value=[]) as mock_find:
            result = await composer.prune_downstreams()
            assert result == 0
            mock_find.assert_not_called()


# ---------------------------------------------------------------------------
# TOML config loading tests
# ---------------------------------------------------------------------------


class TestPruneTomlLoading:
    """Test that prune_downstreams_on_start is loaded from TOML files."""

    def test_load_prune_enabled_from_toml(self, tmp_path):
        """Write a TOML config with prune enabled and load it."""
        from mcp_compose.config_loader import load_config

        toml_content = """\
[composer]
name = "test-server"
prune_downstreams_on_start = true
"""
        config_file = tmp_path / "mcp_compose.toml"
        config_file.write_text(toml_content)

        config = load_config(config_file)
        assert config.composer.prune_downstreams_on_start is True

    def test_load_prune_default_from_toml(self, tmp_path):
        """If omitted in TOML, prune should default to false."""
        from mcp_compose.config_loader import load_config

        toml_content = """\
[composer]
name = "test-server"
"""
        config_file = tmp_path / "mcp_compose.toml"
        config_file.write_text(toml_content)

        config = load_config(config_file)
        assert config.composer.prune_downstreams_on_start is False


# ---------------------------------------------------------------------------
# CLI flag override logic tests
# ---------------------------------------------------------------------------


class TestPruneCLIOverride:
    """Test that the CLI flag overrides the config setting."""

    def test_cli_flag_overrides_config_false(self):
        """CLI --prune-downstreams-on-start should override config=false."""
        parser = create_parser()
        args = parser.parse_args(["serve", "--prune-downstreams-on-start"])
        # Simulate config with prune disabled
        config = MCPComposerConfig(
            composer=ComposerConfig(prune_downstreams_on_start=False),
        )
        # The CLI flag (True) should win over config (False)
        prune = args.prune_downstreams_on_start
        if prune is None:
            prune = config.composer.prune_downstreams_on_start
        assert prune is True

    def test_no_flag_falls_back_to_config_true(self):
        """Without CLI flag, config=true should be used."""
        parser = create_parser()
        args = parser.parse_args(["serve"])
        config = MCPComposerConfig(
            composer=ComposerConfig(prune_downstreams_on_start=True),
        )
        prune = args.prune_downstreams_on_start
        if prune is None:
            prune = config.composer.prune_downstreams_on_start
        assert prune is True

    def test_no_flag_falls_back_to_config_false(self):
        """Without CLI flag, config=false should be used."""
        parser = create_parser()
        args = parser.parse_args(["serve"])
        config = MCPComposerConfig(
            composer=ComposerConfig(prune_downstreams_on_start=False),
        )
        prune = args.prune_downstreams_on_start
        if prune is None:
            prune = config.composer.prune_downstreams_on_start
        assert prune is False


# ---------------------------------------------------------------------------
# _kill_pid edge cases
# ---------------------------------------------------------------------------


class TestKillPidEdgeCases:
    """Additional edge-case tests for _kill_pid."""

    def test_kill_pid_permission_error(self):
        """Should handle PermissionError gracefully (e.g. PID 1)."""
        # Simulate a PermissionError from os.kill (as would happen for PID 1)
        # without actually signalling PID 1 in the test environment.
        with patch("os.kill", side_effect=PermissionError):
            # This should not raise, even when os.kill fails with PermissionError.
            MCPServerComposer._kill_pid(1, timeout=0.5)

    def test_kill_nonexistent_pid_windows_oserror(self):
        """Should handle Windows invalid-parameter OSError for non-existent PID."""
        with patch("os.kill", side_effect=OSError("[WinError 87] The parameter is incorrect")):
            # This should not raise on Windows-style invalid PID errors.
            MCPServerComposer._kill_pid(2**30, timeout=0.5)

    @pytest.mark.skipif(
        not os.path.exists("/proc"),
        reason="Requires /proc filesystem (Linux)",
    )
    def test_kill_pid_sigkill_escalation(self):
        """Process that traps SIGTERM should be escalated to SIGKILL."""
        # Start a process that ignores SIGTERM
        proc = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(300)",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            time.sleep(0.3)
            # Use a very short timeout so SIGKILL is sent quickly
            MCPServerComposer._kill_pid(proc.pid, timeout=1.0)
            ret = proc.wait(timeout=5)
            # Process was SIGKILL'd → exit code is -9
            assert ret == -signal.SIGKILL
        finally:
            try:
                proc.kill()
                proc.wait(timeout=2)
            except Exception:
                pass
