"""
Tests for Composer integration with Process Manager and Tool Manager.
"""

import asyncio
import pytest
from mcp_compose.composer import MCPServerComposer, ConflictResolution
from mcp_compose.config import (
    MCPComposerConfig,
    ServersConfig,
    ProxiedServersConfig,
    EmbeddedServersConfig,
    EmbeddedServerConfig,
    StdioProxiedServerConfig,
    ToolManagerConfig,
    ConflictResolutionStrategy,
)
from mcp_compose.process import ProcessState


class TestComposerIntegration:
    """Tests for Composer integration with managers."""
    
    @pytest.mark.asyncio
    async def test_composer_init_default(self):
        """Test default composer initialization."""
        composer = MCPServerComposer()
        
        assert composer.composed_server_name == "composed-mcp-server"
        assert composer.conflict_resolution == ConflictResolution.PREFIX
        assert composer.tool_manager is None
        assert composer.process_manager is None
    
    @pytest.mark.asyncio
    async def test_composer_with_tool_manager(self):
        """Test composer with ToolManager enabled."""
        composer = MCPServerComposer(use_tool_manager=True)
        
        assert composer.tool_manager is not None
    
    @pytest.mark.asyncio
    async def test_composer_with_process_manager(self):
        """Test composer with ProcessManager enabled."""
        composer = MCPServerComposer(use_process_manager=True)
        
        assert composer.process_manager is not None
    
    @pytest.mark.asyncio
    async def test_composer_lifecycle(self):
        """Test composer start/stop lifecycle."""
        composer = MCPServerComposer(use_process_manager=True)
        
        await composer.start()
        assert composer.process_manager is not None
        
        await composer.stop()
    
    @pytest.mark.asyncio
    async def test_composer_context_manager(self):
        """Test composer as context manager."""
        async with MCPServerComposer(use_process_manager=True) as composer:
            assert composer.process_manager is not None
    
    @pytest.mark.asyncio
    async def test_compose_proxied_server(self):
        """Test composing a proxied server."""
        config = MCPComposerConfig(
            servers=ServersConfig(
                proxied=ProxiedServersConfig(
                    stdio=[
                        StdioProxiedServerConfig(
                            name="test_server",
                            command=["cat"]
                        )
                    ]
                )
            )
        )
        
        composer = MCPServerComposer(
            config=config,
            use_process_manager=True
        )
        
        await composer.compose_from_config()
        
        # Check that process was started
        processes = composer.process_manager.list_processes()
        assert "test_server" in processes
        
        # Check that process is running
        process = composer.process_manager.get_process("test_server")
        assert process.state == ProcessState.RUNNING
        
        # Check that placeholder tool was registered
        assert len(composer.composed_tools) > 0
        
        await composer.stop()
    
    @pytest.mark.asyncio
    async def test_compose_multiple_proxied_servers(self):
        """Test composing multiple proxied servers."""
        config = MCPComposerConfig(
            servers=ServersConfig(
                proxied=ProxiedServersConfig(
                    stdio=[
                        StdioProxiedServerConfig(
                            name="server1",
                            command=["cat"]
                        ),
                        StdioProxiedServerConfig(
                            name="server2",
                            command=["cat"]
                        )
                    ]
                )
            )
        )
        
        composer = MCPServerComposer(
            config=config,
            use_process_manager=True
        )
        
        await composer.compose_from_config()
        
        # Check that both processes were started
        processes = composer.process_manager.list_processes()
        assert len(processes) == 2
        assert "server1" in processes
        assert "server2" in processes
        
        await composer.stop()
    
    @pytest.mark.asyncio
    async def test_compose_with_tool_manager_integration(self):
        """Test composition with ToolManager for conflict resolution."""
        config = MCPComposerConfig(
            tool_manager=ToolManagerConfig(
                conflict_resolution=ConflictResolutionStrategy.PREFIX
            ),
            servers=ServersConfig(
                proxied=ProxiedServersConfig(
                    stdio=[
                        StdioProxiedServerConfig(
                            name="server1",
                            command=["cat"]
                        )
                    ]
                )
            )
        )
        
        composer = MCPServerComposer(
            config=config,
            use_tool_manager=True,
            use_process_manager=True
        )
        
        await composer.compose_from_config()
        
        # Tool manager should be used
        assert composer.tool_manager is not None
        assert len(composer.tool_manager.tools) > 0
        
        await composer.stop()
    
    @pytest.mark.asyncio
    async def test_restart_proxied_server(self):
        """Test restarting a proxied server."""
        config = MCPComposerConfig(
            servers=ServersConfig(
                proxied=ProxiedServersConfig(
                    stdio=[
                        StdioProxiedServerConfig(
                            name="test_server",
                            command=["cat"]
                        )
                    ]
                )
            )
        )
        
        composer = MCPServerComposer(
            config=config,
            use_process_manager=True
        )
        
        await composer.compose_from_config()
        
        process = composer.process_manager.get_process("test_server")
        first_pid = process.pid
        
        # Restart the server
        await composer.restart_proxied_server("test_server")
        
        second_pid = process.pid
        assert second_pid != first_pid
        assert process.restart_count == 1
        
        await composer.stop()
    
    @pytest.mark.asyncio
    async def test_get_proxied_servers_info(self):
        """Test getting info about proxied servers."""
        config = MCPComposerConfig(
            servers=ServersConfig(
                proxied=ProxiedServersConfig(
                    stdio=[
                        StdioProxiedServerConfig(
                            name="test_server",
                            command=["cat"]
                        )
                    ]
                )
            )
        )
        
        composer = MCPServerComposer(
            config=config,
            use_process_manager=True
        )
        
        await composer.compose_from_config()
        
        info = composer.get_proxied_servers_info()
        assert "test_server" in info
        assert info["test_server"]["state"] == ProcessState.RUNNING.value
        assert info["test_server"]["pid"] is not None
        
        await composer.stop()
    
    @pytest.mark.asyncio
    async def test_compose_without_process_manager_error(self):
        """Test that composing proxied servers without ProcessManager raises error."""
        config = MCPComposerConfig(
            servers=ServersConfig(
                proxied=ProxiedServersConfig(
                    stdio=[
                        StdioProxiedServerConfig(
                            name="test_server",
                            command=["cat"]
                        )
                    ]
                )
            )
        )
        
        composer = MCPServerComposer(config=config, use_process_manager=False)
        
        with pytest.raises(Exception):  # Should raise MCPCompositionError
            await composer.compose_from_config()
    
    @pytest.mark.asyncio
    async def test_compose_disabled_proxied_server(self):
        """Test that disabled proxied servers are skipped."""
        # Note: Current StdioProxiedServerConfig doesn't have enabled field
        # This test documents expected future behavior
        pass
    
    @pytest.mark.asyncio
    async def test_composition_summary_with_proxied_servers(self):
        """Test composition summary includes proxied server info."""
        config = MCPComposerConfig(
            servers=ServersConfig(
                proxied=ProxiedServersConfig(
                    stdio=[
                        StdioProxiedServerConfig(
                            name="test_server",
                            command=["cat"]
                        )
                    ]
                )
            )
        )
        
        composer = MCPServerComposer(
            config=config,
            use_process_manager=True
        )
        
        await composer.compose_from_config()
        
        summary = composer.get_composition_summary()
        assert summary["total_tools"] > 0
        assert summary["composed_server_name"] == "composed-mcp-server"
        
        await composer.stop()
    
    @pytest.mark.asyncio
    async def test_compose_mixed_embedded_and_proxied(self):
        """Test composing both embedded and proxied servers."""
        # This test requires actual embedded servers to be available
        # For now, we'll just test with proxied servers
        config = MCPComposerConfig(
            servers=ServersConfig(
                embedded=EmbeddedServersConfig(servers=[]),  # Would need actual embedded servers
                proxied=ProxiedServersConfig(
                    stdio=[
                        StdioProxiedServerConfig(
                            name="proxied1",
                            command=["cat"]
                        )
                    ]
                )
            )
        )
        
        composer = MCPServerComposer(
            config=config,
            use_process_manager=True
        )
        
        await composer.compose_from_config()
        
        # Check proxied server
        processes = composer.process_manager.list_processes()
        assert "proxied1" in processes
        
        await composer.stop()
    
    @pytest.mark.asyncio
    async def test_composer_error_handling(self):
        """Test composer error handling with invalid configuration."""
        config = MCPComposerConfig(
            servers=ServersConfig(
                proxied=ProxiedServersConfig(
                    stdio=[
                        StdioProxiedServerConfig(
                            name="invalid_server",
                            command=["nonexistent_command_xyz"]
                        )
                    ]
                )
            )
        )
        
        composer = MCPServerComposer(
            config=config,
            use_process_manager=True
        )
        
        # Should raise composition error due to invalid command
        with pytest.raises(Exception):  # MCPCompositionError
            await composer.compose_from_config()
        
        await composer.stop()
    
    @pytest.mark.asyncio
    async def test_stop_all_proxied_servers(self):
        """Test that stopping composer stops all proxied servers."""
        config = MCPComposerConfig(
            servers=ServersConfig(
                proxied=ProxiedServersConfig(
                    stdio=[
                        StdioProxiedServerConfig(
                            name="server1",
                            command=["cat"]
                        ),
                        StdioProxiedServerConfig(
                            name="server2",
                            command=["cat"]
                        )
                    ]
                )
            )
        )
        
        composer = MCPServerComposer(
            config=config,
            use_process_manager=True
        )
        
        await composer.compose_from_config()
        
        # Both processes should be running
        for name in ["server1", "server2"]:
            process = composer.process_manager.get_process(name)
            assert process.state == ProcessState.RUNNING
        
        # Stop composer
        await composer.stop()
        
        # All processes should be stopped
        for name in ["server1", "server2"]:
            process = composer.process_manager.get_process(name)
            assert process.state == ProcessState.STOPPED
