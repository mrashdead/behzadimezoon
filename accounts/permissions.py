# accounts/permissions.py
"""
Role-based permission helpers for user management.
"""
from .models import User


def can_create_users(user):
    """Check if user can create any internal users."""
    if not user.is_authenticated:
        return False
    return user.role in [User.Role.SUPER_ADMIN, User.Role.MANAGER]


def allowed_creatable_roles(user):
    """
    Return list of Role choices that the user can create.

    Rules:
    - SUPER_ADMIN can create: MANAGER, SELLER
    - MANAGER can create: SELLER only
    - SELLER cannot create anyone
    """
    if not user.is_authenticated:
        return []

    if user.role == User.Role.SUPER_ADMIN:
        return [User.Role.MANAGER, User.Role.SELLER]
    elif user.role == User.Role.MANAGER:
        return [User.Role.SELLER]
    else:
        return []


def get_role_display_choices(user):
    """
    Return role display tuples for form rendering.

    Returns list of (value, display_label) tuples based on what user can create.
    """
    allowed_roles = allowed_creatable_roles(user)
    return [
        (role, User.Role(role).label)
        for role in allowed_roles
    ]
