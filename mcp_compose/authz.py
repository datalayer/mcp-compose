"""
Authorization middleware for MCP Compose.

This module provides Role-Based Access Control (RBAC) and resource-based
authorization for MCP servers.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from enum import Enum

from .auth import AuthContext, InsufficientScopesError

logger = logging.getLogger(__name__)


class Action(str, Enum):
    """Standard resource actions."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    LIST = "list"
    ADMIN = "admin"


@dataclass
class Permission:
    """
    Represents a permission to perform an action on a resource.
    
    Permissions follow the format: resource:action
    Examples: "tool:execute", "prompt:read", "*:admin"
    """
    resource: str
    action: str
    
    def __post_init__(self):
        """Validate permission format."""
        if not self.resource:
            raise ValueError("Resource cannot be empty")
        if not self.action:
            raise ValueError("Action cannot be empty")
    
    def __str__(self) -> str:
        """String representation of permission."""
        return f"{self.resource}:{self.action}"
    
    def __hash__(self) -> int:
        """Make permission hashable."""
        return hash((self.resource, self.action))
    
    def __eq__(self, other: Any) -> bool:
        """Check equality."""
        if not isinstance(other, Permission):
            return False
        return self.resource == other.resource and self.action == other.action
    
    def matches(self, resource: str, action: str) -> bool:
        """
        Check if this permission matches the given resource and action.
        
        Supports wildcards:
        - "*" matches any resource
        - "*" matches any action
        
        Args:
            resource: Resource to check.
            action: Action to check.
        
        Returns:
            True if permission matches.
        """
        resource_match = self.resource == "*" or self.resource == resource
        action_match = self.action == "*" or self.action == action
        return resource_match and action_match
    
    @classmethod
    def from_string(cls, permission_str: str) -> "Permission":
        """
        Create permission from string.
        
        Args:
            permission_str: Permission string in format "resource:action".
        
        Returns:
            Permission instance.
        
        Raises:
            ValueError: If format is invalid.
        """
        parts = permission_str.split(":", 1)
        if len(parts) != 2:
            raise ValueError(
                f"Invalid permission format: {permission_str}. "
                "Expected format: resource:action"
            )
        return cls(resource=parts[0], action=parts[1])


@dataclass
class Role:
    """
    Represents a role with a set of permissions.
    
    Roles can inherit permissions from parent roles.
    """
    name: str
    permissions: Set[Permission] = field(default_factory=set)
    description: str = ""
    parent_roles: List[str] = field(default_factory=list)
    
    def add_permission(self, permission: Permission) -> None:
        """Add a permission to this role."""
        self.permissions.add(permission)
    
    def remove_permission(self, permission: Permission) -> None:
        """Remove a permission from this role."""
        self.permissions.discard(permission)
    
    def has_permission(
        self,
        resource: str,
        action: str,
        role_manager: Optional["RoleManager"] = None,
    ) -> bool:
        """
        Check if role has permission for resource and action.
        
        Args:
            resource: Resource to check.
            action: Action to check.
            role_manager: Optional role manager to resolve parent roles.
        
        Returns:
            True if role has permission.
        """
        # Check direct permissions
        for perm in self.permissions:
            if perm.matches(resource, action):
                return True
        
        # Check parent roles
        if role_manager:
            for parent_name in self.parent_roles:
                parent = role_manager.get_role(parent_name)
                if parent and parent.has_permission(resource, action, role_manager):
                    return True
        
        return False
    
    def get_all_permissions(
        self,
        role_manager: Optional["RoleManager"] = None,
    ) -> Set[Permission]:
        """
        Get all permissions including inherited ones.
        
        Args:
            role_manager: Optional role manager to resolve parent roles.
        
        Returns:
            Set of all permissions.
        """
        all_perms = self.permissions.copy()
        
        if role_manager:
            for parent_name in self.parent_roles:
                parent = role_manager.get_role(parent_name)
                if parent:
                    all_perms.update(parent.get_all_permissions(role_manager))
        
        return all_perms


class RoleManager:
    """
    Manages roles and their permissions.
    
    Provides methods to create, retrieve, and manage roles.
    """
    
    def __init__(self):
        """Initialize role manager."""
        self._roles: Dict[str, Role] = {}
        self._user_roles: Dict[str, Set[str]] = {}  # user_id -> role names
        
        # Create default roles
        self._create_default_roles()
    
    def _create_default_roles(self) -> None:
        """Create default system roles."""
        # Admin role - full access
        admin_role = Role(
            name="admin",
            description="Full administrative access",
            permissions={
                Permission("*", "*"),
            },
        )
        self._roles["admin"] = admin_role
        
        # User role - basic access
        user_role = Role(
            name="user",
            description="Basic user access",
            permissions={
                Permission("tool", "execute"),
                Permission("tool", "list"),
                Permission("prompt", "read"),
                Permission("prompt", "list"),
            },
        )
        self._roles["user"] = user_role
        
        # Read-only role
        readonly_role = Role(
            name="readonly",
            description="Read-only access",
            permissions={
                Permission("*", "read"),
                Permission("*", "list"),
            },
        )
        self._roles["readonly"] = readonly_role
    
    def create_role(
        self,
        name: str,
        permissions: Optional[Set[Permission]] = None,
        description: str = "",
        parent_roles: Optional[List[str]] = None,
    ) -> Role:
        """
        Create a new role.
        
        Args:
            name: Role name.
            permissions: Set of permissions.
            description: Role description.
            parent_roles: List of parent role names.
        
        Returns:
            Created role.
        
        Raises:
            ValueError: If role already exists.
        """
        if name in self._roles:
            raise ValueError(f"Role '{name}' already exists")
        
        role = Role(
            name=name,
            permissions=permissions or set(),
            description=description,
            parent_roles=parent_roles or [],
        )
        self._roles[name] = role
        logger.info(f"Created role: {name}")
        return role
    
    def get_role(self, name: str) -> Optional[Role]:
        """Get a role by name."""
        return self._roles.get(name)
    
    def delete_role(self, name: str) -> bool:
        """
        Delete a role.
        
        Args:
            name: Role name.
        
        Returns:
            True if role was deleted.
        """
        if name in self._roles:
            del self._roles[name]
            
            # Remove role from all users
            for user_roles in self._user_roles.values():
                user_roles.discard(name)
            
            logger.info(f"Deleted role: {name}")
            return True
        return False
    
    def list_roles(self) -> List[Role]:
        """List all roles."""
        return list(self._roles.values())
    
    def assign_role(self, user_id: str, role_name: str) -> bool:
        """
        Assign a role to a user.
        
        Args:
            user_id: User ID.
            role_name: Role name.
        
        Returns:
            True if role was assigned.
        
        Raises:
            ValueError: If role doesn't exist.
        """
        if role_name not in self._roles:
            raise ValueError(f"Role '{role_name}' does not exist")
        
        if user_id not in self._user_roles:
            self._user_roles[user_id] = set()
        
        self._user_roles[user_id].add(role_name)
        logger.info(f"Assigned role '{role_name}' to user {user_id}")
        return True
    
    def revoke_role(self, user_id: str, role_name: str) -> bool:
        """
        Revoke a role from a user.
        
        Args:
            user_id: User ID.
            role_name: Role name.
        
        Returns:
            True if role was revoked.
        """
        if user_id in self._user_roles:
            if role_name in self._user_roles[user_id]:
                self._user_roles[user_id].remove(role_name)
                logger.info(f"Revoked role '{role_name}' from user {user_id}")
                return True
        return False
    
    def get_user_roles(self, user_id: str) -> List[Role]:
        """
        Get all roles for a user.
        
        Args:
            user_id: User ID.
        
        Returns:
            List of roles.
        """
        role_names = self._user_roles.get(user_id, set())
        return [self._roles[name] for name in role_names if name in self._roles]
    
    def get_user_permissions(self, user_id: str) -> Set[Permission]:
        """
        Get all permissions for a user from all their roles.
        
        Args:
            user_id: User ID.
        
        Returns:
            Set of all permissions.
        """
        all_perms = set()
        for role in self.get_user_roles(user_id):
            all_perms.update(role.get_all_permissions(self))
        return all_perms
    
    def check_permission(
        self,
        user_id: str,
        resource: str,
        action: str,
    ) -> bool:
        """
        Check if user has permission for resource and action.
        
        Args:
            user_id: User ID.
            resource: Resource to check.
            action: Action to check.
        
        Returns:
            True if user has permission.
        """
        for role in self.get_user_roles(user_id):
            if role.has_permission(resource, action, self):
                return True
        return False


class AuthorizationMiddleware:
    """
    Middleware to enforce authorization on MCP requests.
    
    Uses RBAC to check if users have required permissions.
    """
    
    def __init__(
        self,
        role_manager: Optional[RoleManager] = None,
        enforce_authorization: bool = True,
    ):
        """
        Initialize authorization middleware.
        
        Args:
            role_manager: Role manager instance (creates new if not provided).
            enforce_authorization: Whether to enforce authorization checks.
        """
        self.role_manager = role_manager or RoleManager()
        self.enforce_authorization = enforce_authorization
    
    def check_permission(
        self,
        auth_context: AuthContext,
        resource: str,
        action: str,
    ) -> bool:
        """
        Check if auth context has permission.
        
        Args:
            auth_context: Authentication context.
            resource: Resource to access.
            action: Action to perform.
        
        Returns:
            True if authorized.
        """
        if not self.enforce_authorization:
            return True
        
        # Check if user has wildcard scope
        if "*" in auth_context.scopes:
            return True
        
        # Check RBAC permissions
        return self.role_manager.check_permission(
            auth_context.user_id,
            resource,
            action,
        )
    
    def require_permission(
        self,
        resource: str,
        action: str,
    ) -> Callable:
        """
        Decorator to require permission for a handler.
        
        Args:
            resource: Required resource.
            action: Required action.
        
        Returns:
            Decorator function.
        """
        def decorator(handler: Callable) -> Callable:
            async def wrapped_handler(request: Dict[str, Any], **kwargs) -> Any:
                auth_context = request.get("auth_context")
                
                if not auth_context:
                    raise InsufficientScopesError(
                        "No authentication context available"
                    )
                
                if not self.check_permission(auth_context, resource, action):
                    raise InsufficientScopesError(
                        f"Missing permission: {resource}:{action}"
                    )
                
                return await handler(request, **kwargs)
            
            return wrapped_handler
        
        return decorator
    
    def wrap_handler(
        self,
        handler: Callable,
        resource: str,
        action: str,
    ) -> Callable:
        """
        Wrap a handler with authorization check.
        
        Args:
            handler: Handler function to wrap.
            resource: Required resource.
            action: Required action.
        
        Returns:
            Wrapped handler.
        """
        async def wrapped_handler(request: Dict[str, Any], **kwargs) -> Any:
            auth_context = request.get("auth_context")
            
            if not auth_context:
                raise InsufficientScopesError(
                    "No authentication context available"
                )
            
            if not self.check_permission(auth_context, resource, action):
                raise InsufficientScopesError(
                    f"Missing permission: {resource}:{action}"
                )
            
            return await handler(request, **kwargs)
        
        return wrapped_handler


def create_authorization_middleware(
    role_manager: Optional[RoleManager] = None,
    **kwargs
) -> AuthorizationMiddleware:
    """
    Factory function to create authorization middleware.
    
    Args:
        role_manager: Role manager instance.
        **kwargs: Additional arguments for AuthorizationMiddleware.
    
    Returns:
        AuthorizationMiddleware instance.
    """
    return AuthorizationMiddleware(role_manager=role_manager, **kwargs)
