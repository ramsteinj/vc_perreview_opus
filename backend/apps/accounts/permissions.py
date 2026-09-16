from rest_framework.permissions import BasePermission

from .models import Role


class IsAdminRole(BasePermission):
    """관리자 권한(role=ADMIN)을 요구한다."""

    message = '관리자 권한이 필요합니다.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == Role.ADMIN)
