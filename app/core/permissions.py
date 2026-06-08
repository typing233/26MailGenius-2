from enum import Enum
from functools import wraps
from typing import Callable

from fastapi import Depends, HTTPException, status


class Permission(str, Enum):
    SUBSCRIBER_READ = "subscriber:read"
    SUBSCRIBER_WRITE = "subscriber:write"
    SUBSCRIBER_DELETE = "subscriber:delete"
    SUBSCRIBER_IMPORT = "subscriber:import"
    SUBSCRIBER_EXPORT = "subscriber:export"
    LIST_READ = "list:read"
    LIST_WRITE = "list:write"
    LIST_DELETE = "list:delete"
    USER_MANAGE = "user:manage"
    TENANT_SETTINGS = "tenant:settings"
    AUDIT_READ = "audit:read"
    SEND_QUEUE_READ = "send_queue:read"
    SEND_QUEUE_WRITE = "send_queue:write"


ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "super_admin": set(Permission),
    "tenant_admin": {
        Permission.SUBSCRIBER_READ,
        Permission.SUBSCRIBER_WRITE,
        Permission.SUBSCRIBER_DELETE,
        Permission.SUBSCRIBER_IMPORT,
        Permission.SUBSCRIBER_EXPORT,
        Permission.LIST_READ,
        Permission.LIST_WRITE,
        Permission.LIST_DELETE,
        Permission.USER_MANAGE,
        Permission.TENANT_SETTINGS,
        Permission.AUDIT_READ,
        Permission.SEND_QUEUE_READ,
        Permission.SEND_QUEUE_WRITE,
    },
    "member": {
        Permission.SUBSCRIBER_READ,
        Permission.SUBSCRIBER_WRITE,
        Permission.LIST_READ,
    },
}


def get_user_permissions(roles: list[str]) -> set[Permission]:
    perms: set[Permission] = set()
    for role in roles:
        perms |= ROLE_PERMISSIONS.get(role, set())
    return perms


def check_permissions(user_roles: list[str], required: list[Permission]) -> bool:
    user_perms = get_user_permissions(user_roles)
    return all(p in user_perms for p in required)
