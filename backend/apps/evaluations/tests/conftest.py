import pytest
from django.conf import settings
from rest_framework.test import APIClient

from apps.accounts.models import Department, Role, User
from apps.evaluations.models import EvaluationCycle, EvaluationItem, TargetType


def login(client, name, employee_no, password):
    res = client.post(
        '/api/auth/login/',
        {'name': name, 'employee_no': employee_no, 'password': password},
        format='json',
    )
    if res.status_code == 200:
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {res.data["access"]}')
    return res


@pytest.fixture
def admin_client(db):
    client = APIClient()
    login(
        client,
        settings.DEFAULT_ADMIN_NAME,
        settings.DEFAULT_ADMIN_EMPLOYEE_NO,
        settings.DEFAULT_ADMIN_PASSWORD,
    )
    return client


@pytest.fixture
def dept(db):
    return Department.objects.create(code='DEV1', name='개발1팀')


@pytest.fixture
def manager(db, dept):
    return User.objects.create_user(
        employee_no='20180001', name='박팀장', password='managerPass1!', department=dept
    )


@pytest.fixture
def director(db):
    return User.objects.create_user(
        employee_no='20150001', name='최본부장', password='directorPass1!'
    )


@pytest.fixture
def member(db, dept):
    return User.objects.create_user(
        employee_no='20230001',
        name='김철수',
        password='memberPass1!',
        department=dept,
        role=Role.EMPLOYEE,
    )


@pytest.fixture
def cycle(db):
    return EvaluationCycle.objects.create(
        name='2026년 상반기 평가', year=2026, starts_on='2026-09-01', ends_on='2026-09-30'
    )


def make_items(cycle, target_type=TargetType.EMPLOYEE, weights=(50, 30, 20)):
    items = []
    for index, weight in enumerate(weights, start=1):
        items.append(
            EvaluationItem.objects.create(
                cycle=cycle,
                target_type=target_type,
                code=f'{target_type[:3]}{index}',
                title=f'항목{index}',
                weight=weight,
                order=index,
            )
        )
    return items


@pytest.fixture
def full_items(cycle):
    """가중치 합계가 100인 개인 평가 항목 3개."""
    return make_items(cycle)


@pytest.fixture
def open_cycle(cycle, full_items):
    """가중치 100을 채우고 OPEN 상태로 만든 회차."""
    from apps.evaluations.models import CycleStatus

    cycle.status = CycleStatus.OPEN
    cycle.save()
    return cycle


@pytest.fixture
def assignment(open_cycle, member, manager):
    """김철수(대상) ← 박팀장(1차). 2차 없음."""
    from apps.evaluations.models import EvaluatorAssignment, TargetType

    return EvaluatorAssignment.objects.create(
        cycle=open_cycle,
        target_type=TargetType.EMPLOYEE,
        target_user=member,
        primary_evaluator=manager,
    )


@pytest.fixture
def assignment_with_secondary(open_cycle, member, manager, director):
    from apps.evaluations.models import EvaluatorAssignment, TargetType

    return EvaluatorAssignment.objects.create(
        cycle=open_cycle,
        target_type=TargetType.EMPLOYEE,
        target_user=member,
        primary_evaluator=manager,
        secondary_evaluator=director,
    )


@pytest.fixture
def manager_client(db, manager):
    client = APIClient()
    login(client, '박팀장', '20180001', 'managerPass1!')
    return client


@pytest.fixture
def director_client(db, director):
    client = APIClient()
    login(client, '최본부장', '20150001', 'directorPass1!')
    return client


@pytest.fixture
def member_client(db, member):
    client = APIClient()
    login(client, '김철수', '20230001', 'memberPass1!')
    return client
