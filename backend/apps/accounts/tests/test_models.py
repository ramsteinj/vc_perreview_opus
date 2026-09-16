"""모델 제약 테스트 (specs/02-data-model.md)."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.accounts.models import Department, Role, User

pytestmark = pytest.mark.django_db


def test_사번은_중복될_수_없다(employee):
    with pytest.raises(IntegrityError):
        User.objects.create_user(employee_no='20230101', name='다른사람', password='pass123456!')


def test_사번_없이_생성할_수_없다():
    with pytest.raises(ValueError):
        User.objects.create_user(employee_no='', name='홍길동', password='pass123456!')


def test_성명_없이_생성할_수_없다():
    with pytest.raises(ValueError):
        User.objects.create_user(employee_no='20230999', name='', password='pass123456!')


def test_ADMIN_역할이면_is_staff가_켜진다():
    user = User.objects.create_user(
        employee_no='20230200', name='관리자', password='pass123456!', role=Role.ADMIN
    )
    assert user.is_staff is True
    assert user.is_admin is True


def test_username_필드는_제거되었다(employee):
    assert not hasattr(employee, 'username') or employee.username is None
    assert User.USERNAME_FIELD == 'employee_no'


def test_get_full_name은_성명을_반환한다(employee):
    assert employee.get_full_name() == '홍길동'


def test_부서코드는_중복될_수_없다():
    Department.objects.create(code='DEV1', name='개발1팀')
    with pytest.raises(IntegrityError):
        Department.objects.create(code='DEV1', name='개발2팀')


def test_자기_자신을_상위부서로_지정할_수_없다():
    dept = Department.objects.create(code='DEV1', name='개발1팀')
    dept.parent = dept
    with pytest.raises(ValidationError):
        dept.clean()


def test_상위부서_순환참조를_막는다():
    a = Department.objects.create(code='A', name='A본부')
    b = Department.objects.create(code='B', name='B팀', parent=a)
    a.parent = b
    with pytest.raises(ValidationError):
        a.clean()


def test_정상적인_부서_트리는_통과한다():
    a = Department.objects.create(code='A', name='A본부')
    b = Department.objects.create(code='B', name='B팀', parent=a)
    b.clean()  # 예외가 발생하지 않아야 한다
    assert b.parent == a


# ── 권한 클래스 ──────────────────────────────────────────────


def test_IsAdminRole은_관리자만_통과시킨다(employee):
    from unittest.mock import Mock

    from apps.accounts.permissions import IsAdminRole

    permission = IsAdminRole()

    admin = User.objects.get(employee_no='ADMIN')
    assert permission.has_permission(Mock(user=admin), None) is True
    assert permission.has_permission(Mock(user=employee), None) is False


def test_IsAdminRole은_익명_사용자를_거부한다():
    from unittest.mock import Mock

    from django.contrib.auth.models import AnonymousUser

    from apps.accounts.permissions import IsAdminRole

    assert IsAdminRole().has_permission(Mock(user=AnonymousUser()), None) is False
