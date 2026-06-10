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
    # Phase 2
    TEMPLATE_READ = "template:read"
    TEMPLATE_WRITE = "template:write"
    CAMPAIGN_READ = "campaign:read"
    CAMPAIGN_WRITE = "campaign:write"
    SEGMENT_READ = "segment:read"
    SEGMENT_WRITE = "segment:write"
    CHANNEL_READ = "channel:read"
    CHANNEL_WRITE = "channel:write"
    TRACKING_READ = "tracking:read"
    REPORT_READ = "report:read"


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
        Permission.TEMPLATE_READ,
        Permission.TEMPLATE_WRITE,
        Permission.CAMPAIGN_READ,
        Permission.CAMPAIGN_WRITE,
        Permission.SEGMENT_READ,
        Permission.SEGMENT_WRITE,
        Permission.CHANNEL_READ,
        Permission.CHANNEL_WRITE,
        Permission.TRACKING_READ,
        Permission.REPORT_READ,
    },
    "member": {
        Permission.SUBSCRIBER_READ,
        Permission.SUBSCRIBER_WRITE,
        Permission.LIST_READ,
        Permission.TEMPLATE_READ,
        Permission.CAMPAIGN_READ,
        Permission.SEGMENT_READ,
        Permission.REPORT_READ,
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
