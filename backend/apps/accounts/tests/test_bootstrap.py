"""기본 관리자 부트스트랩 테스트 (specs/03-auth.md §5, FR-A-01)."""

import pytest
from django.conf import settings
from django.core.management import call_command

from apps.accounts.bootstrap import create_default_admin
from apps.accounts.models import Role, User

pytestmark = pytest.mark.django_db


def test_migrate로_기본_관리자가_생성된다():
    """post_migrate 시그널이 테스트 DB 구축 시 이미 실행되었어야 한다."""
    admin = User.objects.get(employee_no=settings.DEFAULT_ADMIN_EMPLOYEE_NO)
    assert admin.name == settings.DEFAULT_ADMIN_NAME
    assert admin.role == Role.ADMIN
    assert admin.is_staff is True
    assert admin.is_superuser is True
    assert admin.check_password(settings.DEFAULT_ADMIN_PASSWORD)


def test_재실행해도_중복_생성되지_않는다():
    before = User.objects.filter(role=Role.ADMIN).count()
    create_default_admin()
    create_default_admin()
    assert User.objects.filter(role=Role.ADMIN).count() == before


def test_다른_관리자가_있으면_기본_계정을_만들지_않는다():
    User.objects.filter(employee_no=settings.DEFAULT_ADMIN_EMPLOYEE_NO).delete()
    User.objects.create_user(
        employee_no='90000001', name='김관리', password='otherAdmin1!', role=Role.ADMIN
    )

    assert create_default_admin() is None
    assert not User.objects.filter(employee_no=settings.DEFAULT_ADMIN_EMPLOYEE_NO).exists()


def test_관리자가_없으면_생성된다():
    User.objects.all().delete()

    admin = create_default_admin()

    assert admin is not None
    assert admin.employee_no == settings.DEFAULT_ADMIN_EMPLOYEE_NO
    assert admin.check_password(settings.DEFAULT_ADMIN_PASSWORD)


def test_비활성_관리자만_있으면_기본_계정을_생성한다():
    User.objects.all().delete()
    User.objects.create_user(
        employee_no='90000002',
        name='퇴사관리자',
        password='otherAdmin1!',
        role=Role.ADMIN,
        is_active=False,
    )

    assert create_default_admin() is not None


def test_관리_명령으로_생성할_수_있다():
    User.objects.all().delete()
    call_command('create_default_admin')
    assert User.objects.filter(employee_no=settings.DEFAULT_ADMIN_EMPLOYEE_NO).exists()


def test_force_옵션은_비밀번호를_초기화한다():
    admin = User.objects.get(employee_no=settings.DEFAULT_ADMIN_EMPLOYEE_NO)
    admin.set_password('completelyDifferent9!')
    admin.save()

    call_command('create_default_admin', '--force')

    admin.refresh_from_db()
    assert admin.check_password(settings.DEFAULT_ADMIN_PASSWORD)
