import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def clear_cache():
    """로그인 시도 카운터가 테스트 간에 새지 않도록 캐시를 초기화한다."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def admin_password():
    return 'admin1234!'


@pytest.fixture
def employee(db):
    from apps.accounts.models import Role, User

    return User.objects.create_user(
        employee_no='20230101',
        name='홍길동',
        password='employeePass1!',
        role=Role.EMPLOYEE,
    )
