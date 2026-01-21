# Copyright (c) 2023-2025 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Tests for tool-level authorization.
"""

import pytest

from mcp_compose.tool_authz import (
    ToolAction,
    ToolGroup,
    ToolPermission,
    ToolPermissionManager,
    create_tool_permission_manager,
)
from mcp_compose.authz import Permission, RoleManager


class TestToolPermission:
    """Test ToolPermission class."""
    
    def test_create_tool_permission(self):
        """Test creating a tool permission."""
        perm = ToolPermission("calculate", "execute")
        assert perm.tool_name == "calculate"
        assert perm.action == "execute"
        assert perm.server is None
        assert str(perm) == "calculate:execute"
    
    def test_create_tool_permission_with_server(self):
        """Test creating tool permission with server."""
        perm = ToolPermission("calculate", "execute", server="math_server")
        assert perm.server == "math_server"
        assert str(perm) == "math_server:calculate:execute"
    
    def test_tool_permission_validation(self):
        """Test tool permission validation."""
        with pytest.raises(ValueError, match="Tool name cannot be empty"):
            ToolPermission("", "execute")
        
        with pytest.raises(ValueError, match="Action cannot be empty"):
            ToolPermission("calculate", "")
    
    def test_tool_permission_equality(self):
        """Test tool permission equality."""
        perm1 = ToolPermission("calculate", "execute")
        perm2 = ToolPermission("calculate", "execute")
        perm3 = ToolPermission("search", "execute")
        
        assert perm1 == perm2
        assert perm1 != perm3
    
    def test_tool_permission_hashing(self):
        """Test tool permission can be used in sets."""
        perm1 = ToolPermission("calculate", "execute")
        perm2 = ToolPermission("calculate", "execute")
        perm3 = ToolPermission("search", "execute")
        
        perms = {perm1, perm2, perm3}
        assert len(perms) == 2
    
    def test_matches_exact(self):
        """Test exact tool permission matching."""
        perm = ToolPermission("calculate", "execute")
        assert perm.matches("calculate", "execute")
        assert not perm.matches("calculate", "view")
        assert not perm.matches("search", "execute")
    
    def test_matches_wildcard_tool(self):
        """Test wildcard tool name matching."""
        perm = ToolPermission("calc*", "execute")
        assert perm.matches("calculate", "execute")
        assert perm.matches("calc_sum", "execute")
        assert not perm.matches("search", "execute")
    
    def test_matches_wildcard_action(self):
        """Test wildcard action matching."""
        perm = ToolPermission("calculate", "*")
        assert perm.matches("calculate", "execute")
        assert perm.matches("calculate", "view")
        assert not perm.matches("search", "execute")
    
    def test_matches_with_server(self):
        """Test matching with server specification."""
        perm = ToolPermission("calculate", "execute", server="math_server")
        assert perm.matches("calculate", "execute", server="math_server")
        assert not perm.matches("calculate", "execute", server="other_server")
        assert not perm.matches("calculate", "execute")  # No server provided
    
    def test_matches_wildcard_server(self):
        """Test wildcard server matching."""
        perm = ToolPermission("*", "execute", server="math_*")
        assert perm.matches("calculate", "execute", server="math_server")
        assert perm.matches("add", "execute", server="math_tools")
        assert not perm.matches("search", "execute", server="data_server")
    
    def test_matches_with_conditions(self):
        """Test matching with conditions."""
        perm = ToolPermission(
            "calculate",
            "execute",
            conditions={"env": "production"}
        )
        assert perm.matches("calculate", "execute", context={"env": "production"})
        assert not perm.matches("calculate", "execute", context={"env": "development"})
        assert perm.matches("calculate", "execute")  # No context = ignore conditions
    
    def test_from_string_simple(self):
        """Test creating tool permission from simple string."""
        perm = ToolPermission.from_string("calculate:execute")
        assert perm.tool_name == "calculate"
        assert perm.action == "execute"
        assert perm.server is None
    
    def test_from_string_with_server(self):
        """Test creating tool permission from string with server."""
        perm = ToolPermission.from_string("math_server:calculate:execute")
        assert perm.server == "math_server"
        assert perm.tool_name == "calculate"
        assert perm.action == "execute"
    
    def test_from_string_invalid(self):
        """Test invalid tool permission string."""
        with pytest.raises(ValueError, match="Invalid tool permission format"):
            ToolPermission.from_string("invalid")
        
        with pytest.raises(ValueError, match="Invalid tool permission format"):
            ToolPermission.from_string("too:many:parts:here")


class TestToolGroup:
    """Test ToolGroup class."""
    
    def test_create_tool_group(self):
        """Test creating a tool group."""
        group = ToolGroup(
            name="read_tools",
            tool_patterns=["get_*", "list_*"],
            description="Read-only tools"
        )
        assert group.name == "read_tools"
        assert len(group.tool_patterns) == 2
        assert group.description == "Read-only tools"
    
    def test_matches_tool_simple(self):
        """Test simple tool matching."""
        group = ToolGroup(name="read", tool_patterns=["get_data"])
        assert group.matches_tool("get_data")
        assert not group.matches_tool("set_data")
    
    def test_matches_tool_wildcard(self):
        """Test wildcard tool matching."""
        group = ToolGroup(name="read", tool_patterns=["get_*", "list_*"])
        assert group.matches_tool("get_data")
        assert group.matches_tool("get_user")
        assert group.matches_tool("list_items")
        assert not group.matches_tool("create_item")
    
    def test_matches_tool_with_server(self):
        """Test tool matching with server pattern."""
        group = ToolGroup(
            name="math",
            tool_patterns=["*"],
            server_pattern="math_*"
        )
        assert group.matches_tool("calculate", server="math_server")
        assert group.matches_tool("add", server="math_tools")
        assert not group.matches_tool("search", server="data_server")
    
    def test_add_remove_pattern(self):
        """Test adding and removing patterns."""
        group = ToolGroup(name="test", tool_patterns=["get_*"])
        
        group.add_pattern("list_*")
        assert "list_*" in group.tool_patterns
        
        group.remove_pattern("get_*")
        assert "get_*" not in group.tool_patterns


class TestToolPermissionManager:
    """Test ToolPermissionManager class."""
    
    def test_create_manager(self):
        """Test creating tool permission manager."""
        manager = ToolPermissionManager()
        assert manager.role_manager is None
        assert len(manager._tool_groups) > 0  # Default groups
    
    def test_create_manager_with_role_manager(self):
        """Test creating manager with role manager."""
        role_mgr = RoleManager()
        manager = ToolPermissionManager(role_manager=role_mgr)
        assert manager.role_manager == role_mgr
    
    def test_default_tool_groups(self):
        """Test default tool groups are created."""
        manager = ToolPermissionManager()
        
        readonly = manager.get_tool_group("readonly")
        assert readonly is not None
        assert "get_*" in readonly.tool_patterns
        
        write = manager.get_tool_group("write")
        assert write is not None
        assert "create_*" in write.tool_patterns
        
        admin = manager.get_tool_group("admin")
        assert admin is not None
        assert "admin_*" in admin.tool_patterns
    
    def test_create_tool_group(self):
        """Test creating custom tool group."""
        manager = ToolPermissionManager()
        
        group = manager.create_tool_group(
            "math_tools",
            tool_patterns=["calc_*", "compute_*"],
            description="Math calculation tools"
        )
        
        assert group.name == "math_tools"
        assert manager.get_tool_group("math_tools") == group
    
    def test_create_duplicate_group(self):
        """Test creating duplicate group fails."""
        manager = ToolPermissionManager()
        manager.create_tool_group("custom")
        
        with pytest.raises(ValueError, match="already exists"):
            manager.create_tool_group("custom")
    
    def test_delete_tool_group(self):
        """Test deleting a tool group."""
        manager = ToolPermissionManager()
        manager.create_tool_group("temp")
        
        assert manager.get_tool_group("temp") is not None
        assert manager.delete_tool_group("temp")
        assert manager.get_tool_group("temp") is None
    
    def test_list_tool_groups(self):
        """Test listing all tool groups."""
        manager = ToolPermissionManager()
        manager.create_tool_group("custom1")
        manager.create_tool_group("custom2")
        
        groups = manager.list_tool_groups()
        group_names = {g.name for g in groups}
        
        assert "readonly" in group_names
        assert "write" in group_names
        assert "admin" in group_names
        assert "custom1" in group_names
        assert "custom2" in group_names
    
    def test_grant_revoke_tool_permission(self):
        """Test granting and revoking tool permissions."""
        manager = ToolPermissionManager()
        perm = ToolPermission("calculate", "execute")
        
        manager.grant_tool_permission("user1", perm)
        perms = manager.get_user_tool_permissions("user1")
        assert perm in perms
        
        assert manager.revoke_tool_permission("user1", perm)
        perms = manager.get_user_tool_permissions("user1")
        assert perm not in perms
    
    def test_register_tool_policy(self):
        """Test registering tool policy."""
        manager = ToolPermissionManager()
        
        policy = [
            ToolPermission("sensitive_tool", "execute"),
            ToolPermission("sensitive_tool", "view"),
        ]
        
        manager.register_tool_policy("sensitive_tool", policy)
        retrieved = manager.get_tool_policy("sensitive_tool")
        assert retrieved == policy
    
    def test_check_tool_permission_direct(self):
        """Test checking direct tool permission."""
        manager = ToolPermissionManager()
        perm = ToolPermission("calculate", "execute")
        
        manager.grant_tool_permission("user1", perm)
        
        assert manager.check_tool_permission("user1", "calculate", "execute")
        assert not manager.check_tool_permission("user1", "search", "execute")
    
    def test_check_tool_permission_wildcard(self):
        """Test checking wildcard tool permission."""
        manager = ToolPermissionManager()
        perm = ToolPermission("calc_*", "execute")
        
        manager.grant_tool_permission("user1", perm)
        
        assert manager.check_tool_permission("user1", "calc_sum", "execute")
        assert manager.check_tool_permission("user1", "calc_avg", "execute")
        assert not manager.check_tool_permission("user1", "search", "execute")
    
    def test_check_tool_permission_with_role_manager(self):
        """Test checking tool permission with role manager."""
        role_mgr = RoleManager()
        role_mgr.assign_role("user1", "user")  # User role has tool:execute
        
        manager = ToolPermissionManager(role_manager=role_mgr)
        
        # Should pass due to role-based permission
        assert manager.check_tool_permission("user1", "any_tool", "execute")
    
    def test_check_tool_permission_admin_role(self):
        """Test admin role has all tool permissions."""
        role_mgr = RoleManager()
        role_mgr.assign_role("admin1", "admin")
        
        manager = ToolPermissionManager(role_manager=role_mgr)
        
        assert manager.check_tool_permission("admin1", "any_tool", "execute")
        assert manager.check_tool_permission("admin1", "any_tool", "delete")
    
    def test_grant_group_permission(self):
        """Test granting permission for a tool group."""
        manager = ToolPermissionManager()
        
        manager.grant_group_permission("user1", "readonly", "execute")
        
        # User should now have permission for readonly group tools
        assert manager.check_tool_permission("user1", "get_data", "execute")
        assert manager.check_tool_permission("user1", "list_items", "execute")
    
    def test_grant_group_permission_invalid_group(self):
        """Test granting permission for nonexistent group fails."""
        manager = ToolPermissionManager()
        
        with pytest.raises(ValueError, match="does not exist"):
            manager.grant_group_permission("user1", "nonexistent", "execute")
    
    def test_list_user_accessible_tools(self):
        """Test listing accessible tools for a user."""
        manager = ToolPermissionManager()
        
        # Grant specific permissions
        manager.grant_tool_permission("user1", ToolPermission("tool1", "execute"))
        manager.grant_tool_permission("user1", ToolPermission("tool2", "execute"))
        
        available_tools = ["tool1", "tool2", "tool3", "tool4"]
        accessible = manager.list_user_accessible_tools("user1", available_tools)
        
        assert "tool1" in accessible
        assert "tool2" in accessible
        assert "tool3" not in accessible
        assert "tool4" not in accessible
    
    def test_list_user_accessible_tools_with_wildcards(self):
        """Test listing accessible tools with wildcard permissions."""
        manager = ToolPermissionManager()
        
        # Grant wildcard permission
        manager.grant_tool_permission("user1", ToolPermission("get_*", "execute"))
        
        available_tools = ["get_data", "get_user", "set_data", "list_items"]
        accessible = manager.list_user_accessible_tools("user1", available_tools)
        
        assert "get_data" in accessible
        assert "get_user" in accessible
        assert "set_data" not in accessible
        assert "list_items" not in accessible
    
    def test_get_permission_summary(self):
        """Test getting permission summary."""
        manager = ToolPermissionManager()
        
        manager.grant_tool_permission("user1", ToolPermission("tool1", "execute"))
        manager.grant_tool_permission("user1", ToolPermission("tool2", "execute"))
        manager.grant_tool_permission("user1", ToolPermission("tool3", "view"))
        
        summary = manager.get_permission_summary("user1")
        
        assert summary["user_id"] == "user1"
        assert summary["direct_permissions"] == 3
        assert "execute" in summary["permissions_by_action"]
        assert "view" in summary["permissions_by_action"]


class TestToolPermissionFactory:
    """Test tool permission factory function."""
    
    def test_create_tool_permission_manager(self):
        """Test creating manager via factory."""
        manager = create_tool_permission_manager()
        assert isinstance(manager, ToolPermissionManager)
        assert manager.role_manager is None
    
    def test_create_tool_permission_manager_with_role_manager(self):
        """Test factory with role manager."""
        role_mgr = RoleManager()
        manager = create_tool_permission_manager(role_manager=role_mgr)
        assert manager.role_manager == role_mgr


class TestIntegration:
    """Integration tests for tool-level authorization."""
    
    def test_complete_tool_authorization_flow(self):
        """Test complete tool authorization flow."""
        # Setup
        role_mgr = RoleManager()
        manager = ToolPermissionManager(role_manager=role_mgr)
        
        # Create custom tool group
        group = manager.create_tool_group(
            "analytics",
            tool_patterns=["analyze_*", "report_*"]
        )
        
        # Grant group permission to user
        manager.grant_group_permission("analyst1", "analytics", "execute")
        
        # Check permissions
        assert manager.check_tool_permission("analyst1", "analyze_data", "execute")
        assert manager.check_tool_permission("analyst1", "report_results", "execute")
        assert not manager.check_tool_permission("analyst1", "delete_data", "execute")
    
    def test_role_and_tool_permission_combination(self):
        """Test combining role-based and tool-specific permissions."""
        # Setup role manager with custom role
        role_mgr = RoleManager()
        role = role_mgr.create_role("analyst")
        role.add_permission(Permission("tool", "execute"))
        role_mgr.assign_role("user1", "analyst")
        
        # Setup tool permission manager
        manager = ToolPermissionManager(role_manager=role_mgr)
        
        # User should have general execute permission from role
        assert manager.check_tool_permission("user1", "any_tool", "execute")
        
        # But not delete permission
        assert not manager.check_tool_permission("user1", "any_tool", "delete")
        
        # Grant specific delete permission for one tool
        manager.grant_tool_permission("user1", ToolPermission("special_tool", "delete"))
        
        # Now user can delete that specific tool
        assert manager.check_tool_permission("user1", "special_tool", "delete")
        assert not manager.check_tool_permission("user1", "other_tool", "delete")
    
    def test_tool_group_hierarchy(self):
        """Test hierarchical tool group permissions."""
        manager = ToolPermissionManager()
        
        # Create parent group for all data tools
        data_group = manager.create_tool_group(
            "data_tools",
            tool_patterns=["get_*", "set_*", "delete_*"]
        )
        
        # Create more specific groups
        read_group = manager.create_tool_group(
            "data_read",
            tool_patterns=["get_*"]
        )
        
        write_group = manager.create_tool_group(
            "data_write",
            tool_patterns=["set_*", "delete_*"]
        )
        
        # Grant read-only user access to read group
        manager.grant_group_permission("reader1", "data_read", "execute")
        
        # Grant writer access to both groups
        manager.grant_group_permission("writer1", "data_read", "execute")
        manager.grant_group_permission("writer1", "data_write", "execute")
        
        # Test reader permissions
        assert manager.check_tool_permission("reader1", "get_user", "execute")
        assert not manager.check_tool_permission("reader1", "set_user", "execute")
        
        # Test writer permissions
        assert manager.check_tool_permission("writer1", "get_user", "execute")
        assert manager.check_tool_permission("writer1", "set_user", "execute")
    
    def test_server_specific_permissions(self):
        """Test server-specific tool permissions."""
        manager = ToolPermissionManager()
        
        # Grant permission for tools on specific server
        perm = ToolPermission("*", "execute", server="production_*")
        manager.grant_tool_permission("prod_user", perm)
        
        # Should have access to production servers
        assert manager.check_tool_permission(
            "prod_user", "any_tool", "execute", server="production_db"
        )
        assert manager.check_tool_permission(
            "prod_user", "any_tool", "execute", server="production_api"
        )
        
        # Should not have access to other servers
        assert not manager.check_tool_permission(
            "prod_user", "any_tool", "execute", server="staging_db"
        )
    
    def test_conditional_tool_permissions(self):
        """Test conditional tool permissions."""
        manager = ToolPermissionManager()
        
        # Grant permission with environment condition
        perm = ToolPermission(
            "deploy_*",
            "execute",
            conditions={"env": "production"}
        )
        manager.grant_tool_permission("deployer", perm)
        
        # Should have permission in production environment
        assert manager.check_tool_permission(
            "deployer",
            "deploy_app",
            "execute",
            context={"env": "production"}
        )
        
        # Should not have permission in other environments
        assert not manager.check_tool_permission(
            "deployer",
            "deploy_app",
            "execute",
            context={"env": "staging"}
        )
