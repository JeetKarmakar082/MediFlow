"""
Role helpers and DRF permission classes for MediFlow RBAC.

Roles (Django Groups):
  staff  — front-desk / reception
  doctor — clinical staff

Superusers bypass all checks.
"""
from rest_framework.permissions import BasePermission


# ── Role helpers ──────────────────────────────────────────────────────────────

def is_admin(user):
    return user.is_superuser


def is_doctor(user):
    return user.groups.filter(name='doctor').exists()


def is_staff_role(user):
    return user.groups.filter(name='staff').exists()


def get_role(user):
    """Return the primary role string for a user."""
    if user.is_superuser:
        return 'admin'
    if is_doctor(user):
        return 'doctor'
    if is_staff_role(user):
        return 'staff'
    return 'staff'   # default fallback for unassigned users


# ── DRF Permission classes ────────────────────────────────────────────────────

class IsAdminRole(BasePermission):
    """Only superusers."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and is_admin(request.user)


class IsAdminOrDoctor(BasePermission):
    """Superusers and doctors."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            is_admin(request.user) or is_doctor(request.user)
        )


class IsAdminOrStaff(BasePermission):
    """Superusers and staff."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            is_admin(request.user) or is_staff_role(request.user)
        )


class IsAnyRole(BasePermission):
    """Any authenticated user (staff, doctor, admin)."""
    def has_permission(self, request, view):
        return request.user.is_authenticated
