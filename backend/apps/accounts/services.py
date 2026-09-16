"""계정 도메인 로직 (specs/05-admin-features.md FR-A-02, FR-A-03)."""

import string

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.crypto import get_random_string

from .models import Role, User

# 혼동하기 쉬운 문자(0/O, 1/l/I)는 제외한다 — 임시 비밀번호는 사람이 옮겨 적는다
_TEMP_PASSWORD_ALPHABET = (
    string.ascii_lowercase.replace('l', '').replace('o', '')
    + string.ascii_uppercase.replace('I', '').replace('O', '')
    + '23456789'
    + '!@#$%^&*'
)


def generate_temporary_password(user=None, length=12, attempts=10):
    """Django validator를 통과하는 임시 비밀번호를 생성한다."""
    for _ in range(attempts):
        password = get_random_string(length, _TEMP_PASSWORD_ALPHABET)
        try:
            password_validation.validate_password(password, user)
        except DjangoValidationError:
            continue
        return password
    raise RuntimeError('임시 비밀번호를 생성하지 못했습니다.')


def count_active_admins(exclude_pk=None):
    queryset = User.objects.filter(role=Role.ADMIN, is_active=True)
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)
    return queryset.count()


def is_last_active_admin(user):
    """이 사용자가 마지막 남은 활성 관리자인지 확인한다."""
    if user.role != Role.ADMIN or not user.is_active:
        return False
    return count_active_admins(exclude_pk=user.pk) == 0
