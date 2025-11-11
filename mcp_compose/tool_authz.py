"""
Tool-level authorization for MCP Compose.

This module provides fine-grained permissions for individual tools and tool groups,
extending the RBAC system to provide per-tool access control.
"""

import fnmatch
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from .auth import AuthContext
from .authz import Permission, RoleManager

logger = logging.getLogger(__name__)


class ToolAction(str, Enum):
    """Standard tool actions."""
    EXECUTE = "execute"
    VIEW = "view"
    CONFIGURE = "configure"
    DELETE = "delete"


@dataclass
class ToolPermission:
    """
    Represents a permission for a specific tool or tool pattern.
    
    Supports wildcards for tool names and server names.
    Examples:
        - tool_name="calculate_*", action="execute"
        - tool_name="*", server="data_server", action="execute"
        - tool_name="sensitive_tool", action="execute"
    """
    tool_name: str
    action: str
    server: Optional[str] = None
    conditions: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate tool permission format."""
        if not self.tool_name:
            raise ValueError("Tool name cannot be empty")
        if not self.action:
            raise ValueError("Action cannot be empty")
    
    def __str__(self) -> str:
        """String representation of tool permission."""
        if self.server:
            return f"{self.server}:{self.tool_name}:{self.action}"
        return f"{self.tool_name}:{self.action}"
    
    def __hash__(self) -> int:
        """Make tool permission hashable."""
        return hash((self.tool_name, self.action, self.server))
    
    def __eq__(self, other: Any) -> bool:
        """Check equality."""
        if not isinstance(other, ToolPermission):
            return False
        return (self.tool_name == other.tool_name and 
                self.action == other.action and
                self.server == other.server)
    
    def matches(
        self,
        tool_name: str,
        action: str,
        server: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Check if this permission matches the given tool and action.
        
        Supports wildcards:
        - "*" matches any tool name
        - "prefix_*" matches tools starting with prefix
        - "*_suffix" matches tools ending with suffix
        
        Args:
            tool_name: Tool name to check.
            action: Action to check.
            server: Optional server name to check.
            context: Optional context for condition evaluation.
        
        Returns:
            True if permission matches.
        """
        # Check action match
        action_match = self.action == "*" or self.action == action
        if not action_match:
            return False
        
        # Check server match if specified
        if self.server is not None:
            if server is None:
                return False
            server_match = fnmatch.fnmatch(server, self.server)
            if not server_match:
                return False
        
        # Check tool name match (supports wildcards)
        tool_match = fnmatch.fnmatch(tool_name, self.tool_name)
        if not tool_match:
            return False
        
        # Check conditions if specified
        if self.conditions and context:
            if not self._evaluate_conditions(context):
                return False
        
        return True
    
    def _evaluate_conditions(self, context: Dict[str, Any]) -> bool:
        """
        Evaluate permission conditions against context.
        
        Args:
            context: Context dictionary to evaluate conditions against.
        
        Returns:
            True if all conditions are met.
        """
        for key, expected_value in self.conditions.items():
            actual_value = context.get(key)
            if actual_value != expected_value:
                return False
        return True
    
    @classmethod
    def from_string(cls, permission_str: str) -> "ToolPermission":
        """
        Create tool permission from string.
        
        Formats:
            - "tool_name:action"
            - "server:tool_name:action"
        
        Args:
            permission_str: Permission string.
        
        Returns:
            ToolPermission instance.
        
        Raises:
            ValueError: If format is invalid.
        """
        parts = permission_str.split(":")
        if len(parts) == 2:
            return cls(tool_name=parts[0], action=parts[1])
        elif len(parts) == 3:
            return cls(server=parts[0], tool_name=parts[1], action=parts[2])
        else:
            raise ValueError(
                f"Invalid tool permission format: {permission_str}. "
                "Expected format: 'tool_name:action' or 'server:tool_name:action'"
            )


@dataclass
class ToolGroup:
    """
    Represents a group of tools with shared permissions.
    
    Tool groups allow managing permissions for multiple tools at once.
    """
    name: str
    tool_patterns: List[str] = field(default_factory=list)
    server_pattern: Optional[str] = None
    description: str = ""
    
    def matches_tool(self, tool_name: str, server: Optional[str] = None) -> bool:
        """
        Check if a tool matches this group.
        
        Args:
            tool_name: Tool name to check.
            server: Optional server name.
        
        Returns:
            True if tool matches any pattern in the group.
        """
        # Check server pattern if specified
        if self.server_pattern and server:
            if not fnmatch.fnmatch(server, self.server_pattern):
                return False
        
        # Check tool patterns
        for pattern in self.tool_patterns:
            if fnmatch.fnmatch(tool_name, pattern):
                return True
        
        return False
    
    def add_pattern(self, pattern: str) -> None:
        """Add a tool pattern to the group."""
        if pattern not in self.tool_patterns:
            self.tool_patterns.append(pattern)
    
    def remove_pattern(self, pattern: str) -> None:
        """Remove a tool pattern from the group."""
        if pattern in self.tool_patterns:
            self.tool_patterns.remove(pattern)


class ToolPermissionManager:
    """
    Manages tool-level permissions and tool groups.
    
    Integrates with RoleManager to provide fine-grained tool access control.
    """
    
    def __init__(self, role_manager: Optional[RoleManager] = None):
        """
        Initialize tool permission manager.
        
        Args:
            role_manager: Optional role manager for integration.
        """
        self.role_manager = role_manager
        self._tool_groups: Dict[str, ToolGroup] = {}
        self._user_tool_permissions: Dict[str, Set[ToolPermission]] = {}
        self._tool_policies: Dict[str, List[ToolPermission]] = {}
        
        # Create default tool groups
        self._create_default_groups()
    
    def _create_default_groups(self) -> None:
        """Create default tool groups."""
        # Read-only tools group
        readonly_group = ToolGroup(
            name="readonly",
            tool_patterns=["get_*", "list_*", "search_*", "find_*"],
            description="Read-only tools that don't modify data",
        )
        self._tool_groups["readonly"] = readonly_group
        
        # Write tools group
        write_group = ToolGroup(
            name="write",
            tool_patterns=["create_*", "update_*", "delete_*", "modify_*"],
            description="Tools that modify data",
        )
        self._tool_groups["write"] = write_group
        
        # Admin tools group
        admin_group = ToolGroup(
            name="admin",
            tool_patterns=["admin_*", "configure_*", "manage_*"],
            description="Administrative tools",
        )
        self._tool_groups["admin"] = admin_group
    
    def create_tool_group(
        self,
        name: str,
        tool_patterns: Optional[List[str]] = None,
        server_pattern: Optional[str] = None,
        description: str = "",
    ) -> ToolGroup:
        """
        Create a new tool group.
        
        Args:
            name: Group name.
            tool_patterns: List of tool name patterns (supports wildcards).
            server_pattern: Optional server name pattern.
            description: Group description.
        
        Returns:
            Created tool group.
        
        Raises:
            ValueError: If group already exists.
        """
        if name in self._tool_groups:
            raise ValueError(f"Tool group '{name}' already exists")
        
        group = ToolGroup(
            name=name,
            tool_patterns=tool_patterns or [],
            server_pattern=server_pattern,
            description=description,
        )
        self._tool_groups[name] = group
        logger.info(f"Created tool group: {name}")
        return group
    
    def get_tool_group(self, name: str) -> Optional[ToolGroup]:
        """Get a tool group by name."""
        return self._tool_groups.get(name)
    
    def delete_tool_group(self, name: str) -> bool:
        """
        Delete a tool group.
        
        Args:
            name: Group name.
        
        Returns:
            True if group was deleted.
        """
        if name in self._tool_groups:
            del self._tool_groups[name]
            logger.info(f"Deleted tool group: {name}")
            return True
        return False
    
    def list_tool_groups(self) -> List[ToolGroup]:
        """List all tool groups."""
        return list(self._tool_groups.values())
    
    def grant_tool_permission(
        self,
        user_id: str,
        tool_permission: ToolPermission,
    ) -> None:
        """
        Grant a tool permission to a user.
        
        Args:
            user_id: User ID.
            tool_permission: Tool permission to grant.
        """
        if user_id not in self._user_tool_permissions:
            self._user_tool_permissions[user_id] = set()
        
        self._user_tool_permissions[user_id].add(tool_permission)
        logger.info(f"Granted tool permission '{tool_permission}' to user {user_id}")
    
    def revoke_tool_permission(
        self,
        user_id: str,
        tool_permission: ToolPermission,
    ) -> bool:
        """
        Revoke a tool permission from a user.
        
        Args:
            user_id: User ID.
            tool_permission: Tool permission to revoke.
        
        Returns:
            True if permission was revoked.
        """
        if user_id in self._user_tool_permissions:
            if tool_permission in self._user_tool_permissions[user_id]:
                self._user_tool_permissions[user_id].remove(tool_permission)
                logger.info(f"Revoked tool permission '{tool_permission}' from user {user_id}")
                return True
        return False
    
    def get_user_tool_permissions(self, user_id: str) -> Set[ToolPermission]:
        """
        Get all tool permissions for a user.
        
        Args:
            user_id: User ID.
        
        Returns:
            Set of tool permissions.
        """
        return self._user_tool_permissions.get(user_id, set())
    
    def register_tool_policy(
        self,
        tool_name: str,
        required_permissions: List[ToolPermission],
    ) -> None:
        """
        Register a policy for a specific tool.
        
        Args:
            tool_name: Tool name.
            required_permissions: List of required permissions.
        """
        self._tool_policies[tool_name] = required_permissions
        logger.info(f"Registered policy for tool: {tool_name}")
    
    def get_tool_policy(self, tool_name: str) -> List[ToolPermission]:
        """
        Get the policy for a specific tool.
        
        Args:
            tool_name: Tool name.
        
        Returns:
            List of required permissions, or empty list if no policy.
        """
        return self._tool_policies.get(tool_name, [])
    
    def check_tool_permission(
        self,
        user_id: str,
        tool_name: str,
        action: str,
        server: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Check if user has permission to perform action on tool.
        
        This checks:
        1. Role-based permissions (if role_manager is available)
        2. Direct user tool permissions
        3. Tool group permissions
        
        Args:
            user_id: User ID.
            tool_name: Tool name.
            action: Action to perform.
            server: Optional server name.
            context: Optional context for condition evaluation.
        
        Returns:
            True if user has permission.
        """
        # Check role-based permissions first
        if self.role_manager:
            # Check if user has general tool:action permission
            if self.role_manager.check_permission(user_id, "tool", action):
                return True
            
            # Check if user has admin role (grants all permissions)
            if self.role_manager.check_permission(user_id, "*", "*"):
                return True
        
        # Check direct tool permissions
        user_perms = self.get_user_tool_permissions(user_id)
        for perm in user_perms:
            if perm.matches(tool_name, action, server, context):
                return True
        
        # Check tool group permissions
        for group in self._tool_groups.values():
            if group.matches_tool(tool_name, server):
                # Check if user has permission for this group
                group_perm = ToolPermission(tool_name=group.name, action=action)
                if group_perm in user_perms:
                    return True
        
        return False
    
    def grant_group_permission(
        self,
        user_id: str,
        group_name: str,
        action: str,
    ) -> None:
        """
        Grant permission for all tools in a group.
        
        Args:
            user_id: User ID.
            group_name: Tool group name.
            action: Action to allow.
        
        Raises:
            ValueError: If group doesn't exist.
        """
        group = self.get_tool_group(group_name)
        if not group:
            raise ValueError(f"Tool group '{group_name}' does not exist")
        
        # Grant permission using group name as tool pattern
        perm = ToolPermission(tool_name=group_name, action=action)
        self.grant_tool_permission(user_id, perm)
        logger.info(f"Granted group '{group_name}' permission to user {user_id}")
    
    def list_user_accessible_tools(
        self,
        user_id: str,
        available_tools: List[str],
        action: str = "execute",
        server: Optional[str] = None,
    ) -> List[str]:
        """
        List tools that a user can access.
        
        Args:
            user_id: User ID.
            available_tools: List of available tool names.
            action: Action to check (default: execute).
            server: Optional server name.
        
        Returns:
            List of accessible tool names.
        """
        accessible = []
        for tool_name in available_tools:
            if self.check_tool_permission(user_id, tool_name, action, server):
                accessible.append(tool_name)
        return accessible
    
    def get_permission_summary(self, user_id: str) -> Dict[str, Any]:
        """
        Get a summary of user's tool permissions.
        
        Args:
            user_id: User ID.
        
        Returns:
            Dictionary with permission summary.
        """
        direct_perms = self.get_user_tool_permissions(user_id)
        
        # Group permissions by action
        by_action: Dict[str, List[str]] = {}
        for perm in direct_perms:
            if perm.action not in by_action:
                by_action[perm.action] = []
            by_action[perm.action].append(str(perm))
        
        # Get accessible groups
        accessible_groups = []
        for group in self._tool_groups.values():
            group_perm = ToolPermission(tool_name=group.name, action="*")
            if group_perm in direct_perms:
                accessible_groups.append(group.name)
        
        return {
            "user_id": user_id,
            "direct_permissions": len(direct_perms),
            "permissions_by_action": by_action,
            "accessible_groups": accessible_groups,
        }


def create_tool_permission_manager(
    role_manager: Optional[RoleManager] = None,
) -> ToolPermissionManager:
    """
    Factory function to create tool permission manager.
    
    Args:
        role_manager: Optional role manager for integration.
    
    Returns:
        ToolPermissionManager instance.
    """
    return ToolPermissionManager(role_manager=role_manager)
