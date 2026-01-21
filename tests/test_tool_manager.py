# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Tests for Tool Manager.
"""

import pytest

from mcp_compose.config import (
    ConflictResolutionStrategy,
    CustomTemplateConfig,
    ToolManagerConfig,
    ToolOverrideConfig,
    VersioningConfig,
)
from mcp_compose.exceptions import MCPToolConflictError
from mcp_compose.tool_manager import ToolManager


class TestToolManager:
    """Test cases for ToolManager."""

    def test_init_default(self):
        """Test Tool Manager initialization with defaults."""
        tm = ToolManager()
        assert tm is not None
        assert tm.config is not None
        assert len(tm.tools) == 0

    def test_init_with_config(self):
        """Test Tool Manager initialization with custom config."""
        config = ToolManagerConfig(
            conflict_resolution=ConflictResolutionStrategy.SUFFIX,
            aliases={"old_name": "new_name"}
        )
        tm = ToolManager(config)
        assert tm.config.conflict_resolution == ConflictResolutionStrategy.SUFFIX
        assert "old_name" in tm.aliases

    def test_register_tools_no_conflict(self):
        """Test registering tools without conflicts."""
        tm = ToolManager()
        tools = {
            "tool1": {"description": "Tool 1"},
            "tool2": {"description": "Tool 2"}
        }
        
        mapping = tm.register_tools("server1", tools)
        
        assert len(tm.tools) == 2
        assert "tool1" in tm.tools
        assert "tool2" in tm.tools
        assert mapping == {"tool1": "tool1", "tool2": "tool2"}

    def test_register_tools_with_prefix_conflict(self):
        """Test registering tools with PREFIX resolution."""
        config = ToolManagerConfig(conflict_resolution=ConflictResolutionStrategy.PREFIX)
        tm = ToolManager(config)
        
        # Register first server
        tools1 = {"shared_tool": {"description": "Tool from server1"}}
        tm.register_tools("server1", tools1)
        
        # Register second server with conflicting tool
        tools2 = {"shared_tool": {"description": "Tool from server2"}}
        mapping = tm.register_tools("server2", tools2)
        
        assert len(tm.tools) == 2
        assert "shared_tool" in tm.tools  # Original
        assert "server2_shared_tool" in tm.tools  # Prefixed
        assert mapping["shared_tool"] == "server2_shared_tool"

    def test_register_tools_with_suffix_conflict(self):
        """Test registering tools with SUFFIX resolution."""
        config = ToolManagerConfig(conflict_resolution=ConflictResolutionStrategy.SUFFIX)
        tm = ToolManager(config)
        
        # Register first server
        tools1 = {"shared_tool": {"description": "Tool from server1"}}
        tm.register_tools("server1", tools1)
        
        # Register second server with conflicting tool
        tools2 = {"shared_tool": {"description": "Tool from server2"}}
        mapping = tm.register_tools("server2", tools2)
        
        assert len(tm.tools) == 2
        assert "shared_tool" in tm.tools
        assert "shared_tool_server2" in tm.tools
        assert mapping["shared_tool"] == "shared_tool_server2"

    def test_register_tools_with_override_conflict(self):
        """Test registering tools with OVERRIDE resolution."""
        config = ToolManagerConfig(conflict_resolution=ConflictResolutionStrategy.OVERRIDE)
        tm = ToolManager(config)
        
        # Register first server
        tools1 = {"shared_tool": {"description": "Tool from server1"}}
        tm.register_tools("server1", tools1)
        
        # Register second server with conflicting tool
        tools2 = {"shared_tool": {"description": "Tool from server2"}}
        mapping = tm.register_tools("server2", tools2)
        
        assert len(tm.tools) == 1
        assert tm.tools["shared_tool"]["description"] == "Tool from server2"
        assert mapping["shared_tool"] == "shared_tool"

    def test_register_tools_with_ignore_conflict(self):
        """Test registering tools with IGNORE resolution."""
        config = ToolManagerConfig(conflict_resolution=ConflictResolutionStrategy.IGNORE)
        tm = ToolManager(config)
        
        # Register first server
        tools1 = {"shared_tool": {"description": "Tool from server1"}}
        tm.register_tools("server1", tools1)
        
        # Register second server with conflicting tool
        tools2 = {"shared_tool": {"description": "Tool from server2"}}
        mapping = tm.register_tools("server2", tools2)
        
        assert len(tm.tools) == 1
        assert tm.tools["shared_tool"]["description"] == "Tool from server1"  # Original kept
        assert mapping["shared_tool"] == "shared_tool"

    def test_register_tools_with_error_conflict(self):
        """Test registering tools with ERROR resolution."""
        config = ToolManagerConfig(conflict_resolution=ConflictResolutionStrategy.ERROR)
        tm = ToolManager(config)
        
        # Register first server
        tools1 = {"shared_tool": {"description": "Tool from server1"}}
        tm.register_tools("server1", tools1)
        
        # Register second server with conflicting tool - should raise error
        tools2 = {"shared_tool": {"description": "Tool from server2"}}
        with pytest.raises(MCPToolConflictError):
            tm.register_tools("server2", tools2)

    def test_register_tools_with_custom_template(self):
        """Test registering tools with CUSTOM template resolution."""
        config = ToolManagerConfig(
            conflict_resolution=ConflictResolutionStrategy.CUSTOM,
            custom_template=CustomTemplateConfig(template="{server_name}::{tool_name}")
        )
        tm = ToolManager(config)
        
        # Register first server
        tools1 = {"shared_tool": {"description": "Tool from server1"}}
        tm.register_tools("server1", tools1)
        
        # Register second server with conflicting tool
        tools2 = {"shared_tool": {"description": "Tool from server2"}}
        mapping = tm.register_tools("server2", tools2)
        
        assert len(tm.tools) == 2
        assert "shared_tool" in tm.tools
        assert "server2::shared_tool" in tm.tools
        assert mapping["shared_tool"] == "server2::shared_tool"

    def test_per_tool_override(self):
        """Test per-tool conflict resolution override."""
        config = ToolManagerConfig(
            conflict_resolution=ConflictResolutionStrategy.PREFIX,
            tool_overrides=[
                ToolOverrideConfig(
                    tool_pattern="notebook_*",
                    resolution=ConflictResolutionStrategy.SUFFIX
                )
            ]
        )
        tm = ToolManager(config)
        
        # Register tools
        tools1 = {
            "notebook_create": {"description": "Create notebook"},
            "other_tool": {"description": "Other tool"}
        }
        tm.register_tools("server1", tools1)
        
        tools2 = {
            "notebook_create": {"description": "Create notebook 2"},
            "other_tool": {"description": "Other tool 2"}
        }
        mapping = tm.register_tools("server2", tools2)
        
        # notebook_* should use SUFFIX (override)
        assert "notebook_create_server2" in tm.tools
        
        # other_tool should use PREFIX (global)
        assert "server2_other_tool" in tm.tools

    def test_versioning_enabled(self):
        """Test tool versioning."""
        config = ToolManagerConfig(
            versioning=VersioningConfig(
                enabled=True,
                allow_multiple_versions=True,
                version_suffix_format="_v{version}"
            )
        )
        tm = ToolManager(config)
        
        # Register tool with version
        tools1 = {"my_tool": {"description": "Tool v1"}}
        mapping = tm.register_tools("server1", tools1, server_version="1.0.0")
        
        assert "my_tool_v1.0.0" in tm.tools
        assert mapping["my_tool"] == "my_tool_v1.0.0"
        
        # Register same tool with different version
        tools2 = {"my_tool": {"description": "Tool v2"}}
        mapping = tm.register_tools("server1", tools2, server_version="2.0.0")
        
        assert "my_tool_v2.0.0" in tm.tools
        assert len(tm.tools) == 2

    def test_add_alias(self):
        """Test adding tool aliases."""
        tm = ToolManager()
        
        # Register a tool
        tools = {"original_tool": {"description": "Original"}}
        tm.register_tools("server1", tools)
        
        # Add alias
        tm.add_alias("alias_tool", "original_tool")
        
        assert "alias_tool" in tm.aliases
        assert tm.aliases["alias_tool"] == "original_tool"

    def test_resolve_alias(self):
        """Test resolving aliases."""
        tm = ToolManager()
        
        # Register a tool
        tools = {"original_tool": {"description": "Original"}}
        tm.register_tools("server1", tools)
        
        # Add alias
        tm.add_alias("alias_tool", "original_tool")
        
        # Resolve alias
        assert tm.resolve_alias("alias_tool") == "original_tool"
        assert tm.resolve_alias("original_tool") == "original_tool"
        assert tm.resolve_alias("nonexistent") == "nonexistent"

    def test_get_tool(self):
        """Test getting a tool by name."""
        tm = ToolManager()
        
        tools = {"test_tool": {"description": "Test"}}
        tm.register_tools("server1", tools)
        
        tool = tm.get_tool("test_tool")
        assert tool is not None
        assert tool["description"] == "Test"

    def test_get_tool_by_alias(self):
        """Test getting a tool by alias."""
        tm = ToolManager()
        
        tools = {"original_tool": {"description": "Original"}}
        tm.register_tools("server1", tools)
        tm.add_alias("alias_tool", "original_tool")
        
        tool = tm.get_tool("alias_tool")
        assert tool is not None
        assert tool["description"] == "Original"

    def test_get_tool_source(self):
        """Test getting tool source server."""
        tm = ToolManager()
        
        tools = {"test_tool": {"description": "Test"}}
        tm.register_tools("server1", tools)
        
        source = tm.get_tool_source("test_tool")
        assert source == "server1"

    def test_get_tool_versions(self):
        """Test getting tool versions."""
        config = ToolManagerConfig(
            versioning=VersioningConfig(enabled=True, allow_multiple_versions=True)
        )
        tm = ToolManager(config)
        
        # Register multiple versions
        tools1 = {"my_tool": {"description": "V1"}}
        tm.register_tools("server1", tools1, server_version="1.0.0")
        
        tools2 = {"my_tool": {"description": "V2"}}
        tm.register_tools("server1", tools2, server_version="2.0.0")
        
        versions = tm.get_tool_versions("my_tool")
        assert len(versions) == 2
        assert ("1.0.0", "my_tool_v1.0.0") in versions
        assert ("2.0.0", "my_tool_v2.0.0") in versions

    def test_list_tools_all(self):
        """Test listing all tools."""
        tm = ToolManager()
        
        tools = {
            "tool1": {"description": "Tool 1"},
            "tool2": {"description": "Tool 2"}
        }
        tm.register_tools("server1", tools)
        
        all_tools = tm.list_tools()
        assert len(all_tools) == 2
        assert "tool1" in all_tools
        assert "tool2" in all_tools

    def test_list_tools_by_server(self):
        """Test listing tools filtered by server."""
        tm = ToolManager()
        
        tools1 = {"tool1": {"description": "Tool 1"}}
        tm.register_tools("server1", tools1)
        
        tools2 = {"tool2": {"description": "Tool 2"}}
        tm.register_tools("server2", tools2)
        
        server1_tools = tm.list_tools("server1")
        assert len(server1_tools) == 1
        assert "tool1" in server1_tools
        
        server2_tools = tm.list_tools("server2")
        assert len(server2_tools) == 1
        assert "tool2" in server2_tools

    def test_list_aliases(self):
        """Test listing all aliases."""
        config = ToolManagerConfig(aliases={"alias1": "target1"})
        tm = ToolManager(config)
        
        # Register tool and add another alias
        tools = {"target2": {"description": "Target 2"}}
        tm.register_tools("server1", tools)
        tm.add_alias("alias2", "target2")
        
        aliases = tm.list_aliases()
        assert len(aliases) == 2
        assert aliases["alias1"] == "target1"
        assert aliases["alias2"] == "target2"

    def test_get_conflicts(self):
        """Test getting conflict resolution history."""
        config = ToolManagerConfig(conflict_resolution=ConflictResolutionStrategy.PREFIX)
        tm = ToolManager(config)
        
        # Create a conflict
        tools1 = {"shared_tool": {"description": "Tool 1"}}
        tm.register_tools("server1", tools1)
        
        tools2 = {"shared_tool": {"description": "Tool 2"}}
        tm.register_tools("server2", tools2)
        
        conflicts = tm.get_conflicts()
        assert len(conflicts) == 1
        assert conflicts[0]["tool"] == "shared_tool"
        assert "server1" in conflicts[0]["servers"]
        assert "server2" in conflicts[0]["servers"]
        assert conflicts[0]["strategy"] == "prefix"

    def test_get_summary(self):
        """Test getting tool manager summary."""
        tm = ToolManager()
        
        tools1 = {"tool1": {"description": "Tool 1"}}
        tm.register_tools("server1", tools1)
        
        tools2 = {"tool2": {"description": "Tool 2"}}
        tm.register_tools("server2", tools2)
        
        tm.add_alias("alias1", "tool1")
        
        summary = tm.get_summary()
        assert summary["total_tools"] == 2
        assert summary["total_aliases"] == 1
        assert summary["servers"] == 2

    def test_clear(self):
        """Test clearing tool manager."""
        tm = ToolManager()
        
        tools = {"tool1": {"description": "Tool 1"}}
        tm.register_tools("server1", tools)
        tm.add_alias("alias1", "tool1")
        
        assert len(tm.tools) > 0
        
        tm.clear()
        
        assert len(tm.tools) == 0
        assert len(tm.tool_sources) == 0
        assert len(tm.conflicts_resolved) == 0

    def test_wildcard_pattern_matching(self):
        """Test wildcard pattern matching in tool overrides."""
        config = ToolManagerConfig(
            conflict_resolution=ConflictResolutionStrategy.PREFIX,
            tool_overrides=[
                ToolOverrideConfig(
                    tool_pattern="jupyter_*",
                    resolution=ConflictResolutionStrategy.SUFFIX
                ),
                ToolOverrideConfig(
                    tool_pattern="*_search",
                    resolution=ConflictResolutionStrategy.CUSTOM
                ),
            ],
            custom_template=CustomTemplateConfig(template="{tool_name}@{server_name}")
        )
        tm = ToolManager(config)
        
        # Register tools
        tools1 = {
            "jupyter_create": {"description": "Jupyter create"},
            "data_search": {"description": "Data search"},
            "other_tool": {"description": "Other"}
        }
        tm.register_tools("server1", tools1)
        
        tools2 = {
            "jupyter_create": {"description": "Jupyter create 2"},
            "data_search": {"description": "Data search 2"},
            "other_tool": {"description": "Other 2"}
        }
        tm.register_tools("server2", tools2)
        
        # jupyter_* should use SUFFIX
        assert "jupyter_create_server2" in tm.tools
        
        # *_search should use CUSTOM
        assert "data_search@server2" in tm.tools
        
        # other_tool should use PREFIX (global default)
        assert "server2_other_tool" in tm.tools
