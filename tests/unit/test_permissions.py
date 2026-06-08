import pytest

from app.core.permissions import Permission, ROLE_PERMISSIONS, check_permissions, get_user_permissions


class TestPermissions:
    def test_super_admin_has_all_permissions(self):
        perms = get_user_permissions(["super_admin"])
        assert perms == set(Permission)

    def test_tenant_admin_has_management_permissions(self):
        perms = get_user_permissions(["tenant_admin"])
        assert Permission.SUBSCRIBER_READ in perms
        assert Permission.SUBSCRIBER_WRITE in perms
        assert Permission.SUBSCRIBER_DELETE in perms
        assert Permission.LIST_WRITE in perms
        assert Permission.USER_MANAGE in perms

    def test_member_limited_permissions(self):
        perms = get_user_permissions(["member"])
        assert Permission.SUBSCRIBER_READ in perms
        assert Permission.SUBSCRIBER_WRITE in perms
        assert Permission.LIST_READ in perms
        assert Permission.SUBSCRIBER_DELETE not in perms
        assert Permission.LIST_WRITE not in perms
        assert Permission.USER_MANAGE not in perms

    def test_check_permissions_passes_with_sufficient_role(self):
        assert check_permissions(["tenant_admin"], [Permission.SUBSCRIBER_READ]) is True

    def test_check_permissions_fails_with_insufficient_role(self):
        assert check_permissions(["member"], [Permission.SUBSCRIBER_DELETE]) is False

    def test_check_permissions_multiple_required(self):
        assert check_permissions(["member"], [Permission.SUBSCRIBER_READ, Permission.SUBSCRIBER_DELETE]) is False
        assert check_permissions(["tenant_admin"], [Permission.SUBSCRIBER_READ, Permission.SUBSCRIBER_DELETE]) is True

    def test_unknown_role_has_no_permissions(self):
        perms = get_user_permissions(["unknown_role"])
        assert len(perms) == 0
