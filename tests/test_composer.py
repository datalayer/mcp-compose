"""
Test suite for MCP Compose.
"""

import json
import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from mcp_compose import (
    MCPServerComposer,
    ConflictResolution,
    MCPServerDiscovery,
    MCPServerInfo,
    MCPComposerError,
    MCPToolConflictError,
)


class TestMCPServerComposer:
    """Test cases for MCPServerComposer."""

    def test_init_default(self):
        """Test composer initialization with defaults."""
        composer = MCPServerComposer()
        
        assert composer.composed_server_name == "composed-mcp-server"
        assert composer.conflict_resolution == ConflictResolution.PREFIX
        assert isinstance(composer.discovery, MCPServerDiscovery)
        assert composer.composed_server is not None

    def test_init_custom(self):
        """Test composer initialization with custom parameters."""
        custom_discovery = MCPServerDiscovery()
        composer = MCPServerComposer(
            composed_server_name="my-custom-server",
            conflict_resolution=ConflictResolution.OVERRIDE,
            discovery=custom_discovery,
        )
        
        assert composer.composed_server_name == "my-custom-server"
        assert composer.conflict_resolution == ConflictResolution.OVERRIDE
        assert composer.discovery is custom_discovery

    @patch('mcp_compose.discovery.MCPServerDiscovery.discover_from_pyproject')
    def test_compose_from_pyproject_no_servers(self, mock_discover):
        """Test composition when no servers are discovered."""
        mock_discover.return_value = {}
        
        composer = MCPServerComposer()
        result = composer.compose_from_pyproject()
        
        assert result is composer.composed_server
        assert len(composer.composed_tools) == 0

    @patch('mcp_compose.discovery.MCPServerDiscovery.discover_from_pyproject')
    def test_compose_from_pyproject_with_servers(self, mock_discover):
        """Test composition with discovered servers."""
        # Mock discovered servers
        mock_server_info = MCPServerInfo(
            package_name="test-server",
            version="1.0.0",
            tools={"test_tool": Mock()},
            prompts={"test_prompt": Mock()},
            resources={"test_resource": Mock()},
        )
        mock_discover.return_value = {"test-server": mock_server_info}
        
        composer = MCPServerComposer()
        
        # Mock the composed server's managers
        composer.composed_server._tool_manager = Mock()
        composer.composed_server._tool_manager._tools = {}
        
        result = composer.compose_from_pyproject()
        
        assert result is composer.composed_server
        assert len(composer.composed_tools) == 1
        assert "test_tool" in composer.composed_tools

    def test_filter_servers_include(self):
        """Test server filtering with include list."""
        composer = MCPServerComposer()
        
        servers = {
            "server1": Mock(),
            "server2": Mock(),
            "server3": Mock(),
        }
        
        filtered = composer._filter_servers(
            servers,
            include_servers=["server1", "server3"]
        )
        
        assert len(filtered) == 2
        assert "server1" in filtered
        assert "server3" in filtered
        assert "server2" not in filtered

    def test_filter_servers_exclude(self):
        """Test server filtering with exclude list."""
        composer = MCPServerComposer()
        
        servers = {
            "server1": Mock(),
            "server2": Mock(),
            "server3": Mock(),
        }
        
        filtered = composer._filter_servers(
            servers,
            exclude_servers=["server2"]
        )
        
        assert len(filtered) == 2
        assert "server1" in filtered
        assert "server3" in filtered
        assert "server2" not in filtered

    def test_resolve_name_conflict_no_conflict(self):
        """Test name conflict resolution when there's no conflict."""
        composer = MCPServerComposer()
        
        resolved = composer._resolve_name_conflict(
            "tool", "unique_tool", "server1", {}
        )
        
        assert resolved == "unique_tool"

    def test_resolve_name_conflict_prefix(self):
        """Test name conflict resolution with prefix strategy."""
        composer = MCPServerComposer(conflict_resolution=ConflictResolution.PREFIX)
        composer.source_mapping = {"existing_tool": "other_server"}
        
        resolved = composer._resolve_name_conflict(
            "tool", "existing_tool", "server1", {"existing_tool": Mock()}
        )
        
        assert resolved == "server1_existing_tool"
        assert len(composer.conflicts_resolved) == 1

    def test_resolve_name_conflict_suffix(self):
        """Test name conflict resolution with suffix strategy."""
        composer = MCPServerComposer(conflict_resolution=ConflictResolution.SUFFIX)
        composer.source_mapping = {"existing_tool": "other_server"}
        
        resolved = composer._resolve_name_conflict(
            "tool", "existing_tool", "server1", {"existing_tool": Mock()}
        )
        
        assert resolved == "existing_tool_server1"
        assert len(composer.conflicts_resolved) == 1

    def test_resolve_name_conflict_override(self):
        """Test name conflict resolution with override strategy."""
        composer = MCPServerComposer(conflict_resolution=ConflictResolution.OVERRIDE)
        composer.source_mapping = {"existing_tool": "other_server"}
        
        resolved = composer._resolve_name_conflict(
            "tool", "existing_tool", "server1", {"existing_tool": Mock()}
        )
        
        assert resolved == "existing_tool"
        assert len(composer.conflicts_resolved) == 1

    def test_resolve_name_conflict_ignore(self):
        """Test name conflict resolution with ignore strategy."""
        composer = MCPServerComposer(conflict_resolution=ConflictResolution.IGNORE)
        
        resolved = composer._resolve_name_conflict(
            "tool", "existing_tool", "server1", {"existing_tool": Mock()}
        )
        
        assert resolved is None

    def test_resolve_name_conflict_error(self):
        """Test name conflict resolution with error strategy."""
        composer = MCPServerComposer(conflict_resolution=ConflictResolution.ERROR)
        composer.source_mapping = {"existing_tool": "other_server"}
        
        with pytest.raises(MCPToolConflictError):
            composer._resolve_name_conflict(
                "tool", "existing_tool", "server1", {"existing_tool": Mock()}
            )

    def test_get_composition_summary(self):
        """Test composition summary generation."""
        composer = MCPServerComposer()
        composer.composed_tools = {"tool1": Mock(), "tool2": Mock()}
        composer.composed_prompts = {"prompt1": Mock()}
        composer.source_mapping = {
            "tool1": "server1",
            "tool2": "server2", 
            "prompt1": "server1"
        }
        composer.conflicts_resolved = [{"type": "prefix", "name": "test"}]
        
        summary = composer.get_composition_summary()
        
        assert summary["total_tools"] == 2
        assert summary["total_prompts"] == 1
        assert summary["total_resources"] == 0
        assert summary["source_servers"] == 2
        assert summary["conflicts_resolved"] == 1

    def test_list_methods(self):
        """Test list methods for tools, prompts, and resources."""
        composer = MCPServerComposer()
        composer.composed_tools = {"tool1": Mock(), "tool2": Mock()}
        composer.composed_prompts = {"prompt1": Mock()}
        composer.composed_resources = {"resource1": Mock()}
        
        assert set(composer.list_tools()) == {"tool1", "tool2"}
        assert composer.list_prompts() == ["prompt1"]
        assert composer.list_resources() == ["resource1"]

    def test_get_source_methods(self):
        """Test source retrieval methods."""
        composer = MCPServerComposer()
        composer.source_mapping = {
            "tool1": "server1",
            "prompt1": "server2",
            "resource1": "server3"
        }
        
        assert composer.get_tool_source("tool1") == "server1"
        assert composer.get_prompt_source("prompt1") == "server2"
        assert composer.get_resource_source("resource1") == "server3"
        assert composer.get_tool_source("nonexistent") is None


class TestMCPServerInfo:
    """Test cases for MCPServerInfo."""

    def test_init(self):
        """Test MCPServerInfo initialization."""
        tools = {"tool1": Mock()}
        prompts = {"prompt1": Mock()}
        resources = {"resource1": Mock()}
        
        info = MCPServerInfo(
            package_name="test-package",
            version="1.0.0",
            tools=tools,
            prompts=prompts,
            resources=resources,
        )
        
        assert info.package_name == "test-package"
        assert info.version == "1.0.0"
        assert info.tools is tools
        assert info.prompts is prompts
        assert info.resources is resources

    def test_init_defaults(self):
        """Test MCPServerInfo initialization with defaults."""
        info = MCPServerInfo(
            package_name="test-package",
            version="1.0.0",
        )
        
        assert info.tools == {}
        assert info.prompts == {}
        assert info.resources == {}


class TestConflictResolution:
    """Test cases for ConflictResolution enum."""

    def test_enum_values(self):
        """Test enum values."""
        assert ConflictResolution.PREFIX.value == "prefix"
        assert ConflictResolution.SUFFIX.value == "suffix"
        assert ConflictResolution.IGNORE.value == "ignore"
        assert ConflictResolution.ERROR.value == "error"
        assert ConflictResolution.OVERRIDE.value == "override"

    def test_enum_from_string(self):
        """Test creating enum from string value."""
        assert ConflictResolution("prefix") == ConflictResolution.PREFIX
        assert ConflictResolution("error") == ConflictResolution.ERROR


if __name__ == "__main__":
    pytest.main([__file__])
