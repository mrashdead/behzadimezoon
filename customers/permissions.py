from django.core.exceptions import PermissionDenied


def user_can_create_customer(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return getattr(user, 'role', None) in ['SELLER', 'MANAGER', 'SUPER_ADMIN']


def user_can_edit_customer(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return getattr(user, 'role', None) in ['MANAGER', 'SUPER_ADMIN']


def user_can_delete_customer(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return getattr(user, 'role', None) in ['MANAGER', 'SUPER_ADMIN']
