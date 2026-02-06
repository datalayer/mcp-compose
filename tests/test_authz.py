# Copyright (c) 2025-2026 Datalayer, Inc.
# Distributed under the terms of the Modified BSD License.

"""
Tests for authorization middleware.
"""

import pytest

from mcp_compose.auth import AuthContext, AuthType, InsufficientScopesError
from mcp_compose.authz import (
    AuthorizationMiddleware,
    Permission,
    Role,
    RoleManager,
    create_authorization_middleware,
)


class TestPermission:
    """Test Permission class."""

    def test_create_permission(self):
        """Test creating a permission."""
        perm = Permission("tool", "execute")
        assert perm.resource == "tool"
        assert perm.action == "execute"
        assert str(perm) == "tool:execute"

    def test_permission_validation(self):
        """Test permission validation."""
        with pytest.raises(ValueError, match="Resource cannot be empty"):
            Permission("", "execute")

        with pytest.raises(ValueError, match="Action cannot be empty"):
            Permission("tool", "")

    def test_permission_equality(self):
        """Test permission equality."""
        perm1 = Permission("tool", "execute")
        perm2 = Permission("tool", "execute")
        perm3 = Permission("prompt", "read")

        assert perm1 == perm2
        assert perm1 != perm3
        assert perm1 != "tool:execute"

    def test_permission_hashing(self):
        """Test permission can be used in sets."""
        perm1 = Permission("tool", "execute")
        perm2 = Permission("tool", "execute")
        perm3 = Permission("prompt", "read")

        perms = {perm1, perm2, perm3}
        assert len(perms) == 2  # perm1 and perm2 are same

    def test_permission_matches_exact(self):
        """Test exact permission matching."""
        perm = Permission("tool", "execute")
        assert perm.matches("tool", "execute")
        assert not perm.matches("tool", "read")
        assert not perm.matches("prompt", "execute")

    def test_permission_matches_wildcard_resource(self):
        """Test wildcard resource matching."""
        perm = Permission("*", "execute")
        assert perm.matches("tool", "execute")
        assert perm.matches("prompt", "execute")
        assert not perm.matches("tool", "read")

    def test_permission_matches_wildcard_action(self):
        """Test wildcard action matching."""
        perm = Permission("tool", "*")
        assert perm.matches("tool", "execute")
        assert perm.matches("tool", "read")
        assert not perm.matches("prompt", "execute")

    def test_permission_matches_wildcard_both(self):
        """Test wildcard for both resource and action."""
        perm = Permission("*", "*")
        assert perm.matches("tool", "execute")
        assert perm.matches("prompt", "read")
        assert perm.matches("anything", "anything")

    def test_permission_from_string(self):
        """Test creating permission from string."""
        perm = Permission.from_string("tool:execute")
        assert perm.resource == "tool"
        assert perm.action == "execute"

    def test_permission_from_string_invalid(self):
        """Test invalid permission string."""
        with pytest.raises(ValueError, match="Invalid permission format"):
            Permission.from_string("invalid")


class TestRole:
    """Test Role class."""

    def test_create_role(self):
        """Test creating a role."""
        role = Role(name="test_role", description="Test role")
        assert role.name == "test_role"
        assert role.description == "Test role"
        assert len(role.permissions) == 0
        assert len(role.parent_roles) == 0

    def test_add_remove_permission(self):
        """Test adding and removing permissions."""
        role = Role(name="test_role")
        perm = Permission("tool", "execute")

        role.add_permission(perm)
        assert perm in role.permissions

        role.remove_permission(perm)
        assert perm not in role.permissions

    def test_has_permission_direct(self):
        """Test checking direct permissions."""
        role = Role(name="test_role")
        role.add_permission(Permission("tool", "execute"))

        assert role.has_permission("tool", "execute")
        assert not role.has_permission("tool", "read")
        assert not role.has_permission("prompt", "execute")

    def test_has_permission_wildcard(self):
        """Test checking wildcard permissions."""
        role = Role(name="admin")
        role.add_permission(Permission("*", "*"))

        assert role.has_permission("tool", "execute")
        assert role.has_permission("prompt", "read")
        assert role.has_permission("anything", "anything")

    def test_has_permission_inherited(self):
        """Test checking inherited permissions."""
        manager = RoleManager()

        parent_role = manager.create_role("parent")
        parent_role.add_permission(Permission("tool", "execute"))

        child_role = manager.create_role("child", parent_roles=["parent"])

        assert child_role.has_permission("tool", "execute", manager)
        assert not child_role.has_permission("prompt", "read", manager)

    def test_get_all_permissions(self):
        """Test getting all permissions including inherited."""
        manager = RoleManager()

        parent_role = manager.create_role("parent")
        parent_role.add_permission(Permission("tool", "execute"))

        child_role = manager.create_role("child", parent_roles=["parent"])
        child_role.add_permission(Permission("prompt", "read"))

        all_perms = child_role.get_all_permissions(manager)
        assert len(all_perms) == 2
        assert Permission("tool", "execute") in all_perms
        assert Permission("prompt", "read") in all_perms

    def test_get_all_permissions_without_manager(self):
        """Test getting permissions without role manager."""
        role = Role(name="test_role")
        role.add_permission(Permission("tool", "execute"))

        all_perms = role.get_all_permissions()
        assert len(all_perms) == 1
        assert Permission("tool", "execute") in all_perms


class TestRoleManager:
    """Test RoleManager class."""

    def test_default_roles(self):
        """Test default roles are created."""
        manager = RoleManager()

        admin_role = manager.get_role("admin")
        assert admin_role is not None
        assert admin_role.has_permission("anything", "anything")

        user_role = manager.get_role("user")
        assert user_role is not None
        assert user_role.has_permission("tool", "execute")

        readonly_role = manager.get_role("readonly")
        assert readonly_role is not None
        assert readonly_role.has_permission("tool", "read")

    def test_create_role(self):
        """Test creating a custom role."""
        manager = RoleManager()

        role = manager.create_role(
            "custom",
            permissions={Permission("tool", "execute")},
            description="Custom role",
        )

        assert role.name == "custom"
        assert role.description == "Custom role"
        assert manager.get_role("custom") == role

    def test_create_duplicate_role(self):
        """Test creating duplicate role fails."""
        manager = RoleManager()
        manager.create_role("custom")

        with pytest.raises(ValueError, match="already exists"):
            manager.create_role("custom")

    def test_delete_role(self):
        """Test deleting a role."""
        manager = RoleManager()
        manager.create_role("temp")

        assert manager.get_role("temp") is not None
        assert manager.delete_role("temp")
        assert manager.get_role("temp") is None
        assert not manager.delete_role("temp")  # Already deleted

    def test_delete_role_removes_user_assignments(self):
        """Test deleting role removes it from users."""
        manager = RoleManager()
        manager.create_role("temp")
        manager.assign_role("user1", "temp")

        assert "temp" in [r.name for r in manager.get_user_roles("user1")]

        manager.delete_role("temp")
        assert "temp" not in [r.name for r in manager.get_user_roles("user1")]

    def test_list_roles(self):
        """Test listing all roles."""
        manager = RoleManager()
        manager.create_role("custom1")
        manager.create_role("custom2")

        roles = manager.list_roles()
        role_names = {r.name for r in roles}

        assert "admin" in role_names
        assert "user" in role_names
        assert "readonly" in role_names
        assert "custom1" in role_names
        assert "custom2" in role_names

    def test_assign_role(self):
        """Test assigning role to user."""
        manager = RoleManager()

        assert manager.assign_role("user1", "user")
        roles = manager.get_user_roles("user1")
        assert len(roles) == 1
        assert roles[0].name == "user"

    def test_assign_nonexistent_role(self):
        """Test assigning nonexistent role fails."""
        manager = RoleManager()

        with pytest.raises(ValueError, match="does not exist"):
            manager.assign_role("user1", "nonexistent")

    def test_assign_multiple_roles(self):
        """Test assigning multiple roles to user."""
        manager = RoleManager()
        manager.assign_role("user1", "user")
        manager.assign_role("user1", "readonly")

        roles = manager.get_user_roles("user1")
        role_names = {r.name for r in roles}
        assert role_names == {"user", "readonly"}

    def test_revoke_role(self):
        """Test revoking role from user."""
        manager = RoleManager()
        manager.assign_role("user1", "user")

        assert manager.revoke_role("user1", "user")
        roles = manager.get_user_roles("user1")
        assert len(roles) == 0

    def test_revoke_nonexistent_role(self):
        """Test revoking nonexistent role."""
        manager = RoleManager()

        assert not manager.revoke_role("user1", "user")

    def test_get_user_permissions(self):
        """Test getting all user permissions."""
        manager = RoleManager()
        manager.assign_role("user1", "user")

        perms = manager.get_user_permissions("user1")
        assert Permission("tool", "execute") in perms
        assert Permission("prompt", "read") in perms

    def test_get_user_permissions_multiple_roles(self):
        """Test getting permissions from multiple roles."""
        manager = RoleManager()

        # Create custom role
        custom = manager.create_role("custom")
        custom.add_permission(Permission("custom", "action"))

        # Assign multiple roles
        manager.assign_role("user1", "user")
        manager.assign_role("user1", "custom")

        perms = manager.get_user_permissions("user1")
        assert Permission("tool", "execute") in perms
        assert Permission("custom", "action") in perms

    def test_check_permission(self):
        """Test checking user permission."""
        manager = RoleManager()
        manager.assign_role("user1", "user")

        assert manager.check_permission("user1", "tool", "execute")
        assert not manager.check_permission("user1", "tool", "delete")
        assert not manager.check_permission("user2", "tool", "execute")

    def test_check_permission_admin(self):
        """Test admin has all permissions."""
        manager = RoleManager()
        manager.assign_role("admin1", "admin")

        assert manager.check_permission("admin1", "tool", "execute")
        assert manager.check_permission("admin1", "anything", "anything")


class TestAuthorizationMiddleware:
    """Test AuthorizationMiddleware class."""

    def test_create_middleware(self):
        """Test creating authorization middleware."""
        middleware = AuthorizationMiddleware()
        assert middleware.role_manager is not None
        assert middleware.enforce_authorization is True

    def test_create_middleware_with_manager(self):
        """Test creating middleware with custom role manager."""
        manager = RoleManager()
        middleware = AuthorizationMiddleware(role_manager=manager)
        assert middleware.role_manager == manager

    def test_check_permission_disabled(self):
        """Test authorization can be disabled."""
        middleware = AuthorizationMiddleware(enforce_authorization=False)
        auth_context = AuthContext(user_id="user1", auth_type=AuthType.API_KEY, scopes=[])

        # Should allow anything when disabled
        assert middleware.check_permission(auth_context, "tool", "execute")
        assert middleware.check_permission(auth_context, "anything", "anything")

    def test_check_permission_wildcard_scope(self):
        """Test wildcard scope grants all permissions."""
        middleware = AuthorizationMiddleware()
        auth_context = AuthContext(user_id="user1", auth_type=AuthType.API_KEY, scopes=["*"])

        assert middleware.check_permission(auth_context, "tool", "execute")
        assert middleware.check_permission(auth_context, "anything", "anything")

    def test_check_permission_with_role(self):
        """Test checking permission with assigned role."""
        middleware = AuthorizationMiddleware()
        middleware.role_manager.assign_role("user1", "user")

        auth_context = AuthContext(user_id="user1", auth_type=AuthType.API_KEY, scopes=[])

        assert middleware.check_permission(auth_context, "tool", "execute")
        assert not middleware.check_permission(auth_context, "tool", "delete")

    def test_check_permission_admin_role(self):
        """Test admin role has all permissions."""
        middleware = AuthorizationMiddleware()
        middleware.role_manager.assign_role("admin1", "admin")

        auth_context = AuthContext(user_id="admin1", auth_type=AuthType.API_KEY, scopes=[])

        assert middleware.check_permission(auth_context, "tool", "execute")
        assert middleware.check_permission(auth_context, "anything", "anything")

    @pytest.mark.asyncio
    async def test_require_permission_decorator(self):
        """Test require_permission decorator."""
        middleware = AuthorizationMiddleware()
        middleware.role_manager.assign_role("user1", "user")

        @middleware.require_permission("tool", "execute")
        async def handler(request):
            return {"result": "success"}

        auth_context = AuthContext(user_id="user1", auth_type=AuthType.API_KEY, scopes=[])
        request = {"auth_context": auth_context}

        result = await handler(request)
        assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_require_permission_decorator_no_auth(self):
        """Test decorator fails without auth context."""
        middleware = AuthorizationMiddleware()

        @middleware.require_permission("tool", "execute")
        async def handler(request):
            return {"result": "success"}

        request = {}

        with pytest.raises(InsufficientScopesError, match="No authentication context"):
            await handler(request)

    @pytest.mark.asyncio
    async def test_require_permission_decorator_insufficient(self):
        """Test decorator fails with insufficient permissions."""
        middleware = AuthorizationMiddleware()
        middleware.role_manager.assign_role("user1", "readonly")

        @middleware.require_permission("tool", "execute")
        async def handler(request):
            return {"result": "success"}

        auth_context = AuthContext(user_id="user1", auth_type=AuthType.API_KEY, scopes=[])
        request = {"auth_context": auth_context}

        with pytest.raises(InsufficientScopesError, match="Missing permission: tool:execute"):
            await handler(request)

    @pytest.mark.asyncio
    async def test_wrap_handler(self):
        """Test wrapping handler with authorization."""
        middleware = AuthorizationMiddleware()
        middleware.role_manager.assign_role("user1", "user")

        async def original_handler(request):
            return {"result": "success"}

        wrapped = middleware.wrap_handler(original_handler, "tool", "execute")

        auth_context = AuthContext(user_id="user1", auth_type=AuthType.API_KEY, scopes=[])
        request = {"auth_context": auth_context}

        result = await wrapped(request)
        assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_wrap_handler_no_permission(self):
        """Test wrapped handler fails without permission."""
        middleware = AuthorizationMiddleware()
        middleware.role_manager.assign_role("user1", "readonly")

        async def original_handler(request):
            return {"result": "success"}

        wrapped = middleware.wrap_handler(original_handler, "tool", "execute")

        auth_context = AuthContext(user_id="user1", auth_type=AuthType.API_KEY, scopes=[])
        request = {"auth_context": auth_context}

        with pytest.raises(InsufficientScopesError, match="Missing permission: tool:execute"):
            await wrapped(request)


class TestAuthorizationFactory:
    """Test authorization factory function."""

    def test_create_authorization_middleware(self):
        """Test creating middleware via factory."""
        middleware = create_authorization_middleware()
        assert isinstance(middleware, AuthorizationMiddleware)
        assert middleware.role_manager is not None

    def test_create_authorization_middleware_with_manager(self):
        """Test factory with custom role manager."""
        manager = RoleManager()
        middleware = create_authorization_middleware(role_manager=manager)
        assert middleware.role_manager == manager

    def test_create_authorization_middleware_kwargs(self):
        """Test factory with additional kwargs."""
        middleware = create_authorization_middleware(enforce_authorization=False)
        assert middleware.enforce_authorization is False


class TestIntegration:
    """Integration tests for authorization system."""

    @pytest.mark.asyncio
    async def test_complete_authorization_flow(self):
        """Test complete authorization flow."""
        # Create middleware
        middleware = AuthorizationMiddleware()

        # Create custom role with specific permissions
        role = middleware.role_manager.create_role("operator")
        role.add_permission(Permission("tool", "execute"))
        role.add_permission(Permission("tool", "list"))

        # Assign role to user
        middleware.role_manager.assign_role("operator1", "operator")

        # Create handler with authorization
        @middleware.require_permission("tool", "execute")
        async def execute_tool(request):
            return {"status": "executed"}

        # Test with authorized user
        auth_context = AuthContext(user_id="operator1", auth_type=AuthType.API_KEY, scopes=[])
        request = {"auth_context": auth_context}

        result = await execute_tool(request)
        assert result == {"status": "executed"}

        # Test with unauthorized action
        @middleware.require_permission("tool", "delete")
        async def delete_tool(request):
            return {"status": "deleted"}

        with pytest.raises(InsufficientScopesError):
            await delete_tool(request)

    @pytest.mark.asyncio
    async def test_role_inheritance_flow(self):
        """Test role inheritance in authorization."""
        middleware = AuthorizationMiddleware()

        # Create parent role
        parent = middleware.role_manager.create_role("tool_user")
        parent.add_permission(Permission("tool", "execute"))

        # Create child role that inherits from parent
        child = middleware.role_manager.create_role(
            "power_user",
            parent_roles=["tool_user"],
        )
        child.add_permission(Permission("prompt", "create"))

        # Assign child role
        middleware.role_manager.assign_role("user1", "power_user")

        # User should have both inherited and direct permissions
        auth_context = AuthContext(user_id="user1", auth_type=AuthType.API_KEY, scopes=[])

        assert middleware.check_permission(auth_context, "tool", "execute")
        assert middleware.check_permission(auth_context, "prompt", "create")
        assert not middleware.check_permission(auth_context, "tool", "delete")
