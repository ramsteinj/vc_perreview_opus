import pytest
from django.conf import settings
from rest_framework.test import APIClient

from apps.accounts.models import Department, User
from apps.evaluations.models import (
    CycleStatus,
    EvaluationAnswer,
    EvaluationCycle,
    EvaluationItem,
    EvaluationResponse,
    EvaluatorAssignment,
    ResponseStatus,
    TargetType,
)


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
def scenario(db):
    """두 부서, 평가자 2명, 대상 3명으로 상태가 섞인 회차를 만든다.

    기대 응답 행 (총 6):
      dev팀 박팀장 → 김철수 1차   : SUBMITTED
      dev팀 박팀장 → 이영희 1차   : DRAFT (1/2 입력)
      dev팀 박팀장 → 개발1팀 1차  : NOT_STARTED   (부서 대상)
      hr팀 최본부장 → 김철수 2차  : NOT_STARTED
      hr팀 최본부장 → 정민수 1차  : SUBMITTED
      hr팀 최본부장 → 인사팀 1차  : DRAFT (0/2 입력)
    """
    dev = Department.objects.create(code='DEV1', name='개발1팀')
    hr = Department.objects.create(code='HR', name='인사팀')

    manager = User.objects.create_user(
        employee_no='20180001', name='박팀장', password='managerPass1!', department=dev
    )
    director = User.objects.create_user(
        employee_no='20150001', name='최본부장', password='directorPass1!', department=hr
    )
    member1 = User.objects.create_user(
        employee_no='20230001', name='김철수', password='memberPass1!', department=dev
    )
    member2 = User.objects.create_user(
        employee_no='20230002', name='이영희', password='memberPass1!', department=dev
    )
    member3 = User.objects.create_user(
        employee_no='20230003', name='정민수', password='memberPass1!', department=hr
    )

    cycle = EvaluationCycle.objects.create(
        name='2026년 상반기 평가',
        year=2026,
        starts_on='2026-01-01',
        ends_on='2099-12-31',
        status=CycleStatus.OPEN,
    )

    emp_items = [
        EvaluationItem.objects.create(
            cycle=cycle,
            target_type=TargetType.EMPLOYEE,
            code=f'E{i}',
            title=f'개인{i}',
            weight=50,
            order=i,
        )
        for i in (1, 2)
    ]
    dept_items = [
        EvaluationItem.objects.create(
            cycle=cycle,
            target_type=TargetType.DEPARTMENT,
            code=f'D{i}',
            title=f'부서{i}',
            weight=50,
            order=i,
        )
        for i in (1, 2)
    ]

    # 김철수: 1차 박팀장(제출), 2차 최본부장(미시작)
    a1 = EvaluatorAssignment.objects.create(
        cycle=cycle,
        target_type=TargetType.EMPLOYEE,
        target_user=member1,
        primary_evaluator=manager,
        secondary_evaluator=director,
    )
    r1 = EvaluationResponse.objects.create(
        assignment=a1,
        evaluator=manager,
        round='PRIMARY',
        status=ResponseStatus.SUBMITTED,
    )
    for item in emp_items:
        EvaluationAnswer.objects.create(response=r1, item=item, score=4)

    # 이영희: 1차 박팀장(임시저장 1/2)
    a2 = EvaluatorAssignment.objects.create(
        cycle=cycle,
        target_type=TargetType.EMPLOYEE,
        target_user=member2,
        primary_evaluator=manager,
    )
    r2 = EvaluationResponse.objects.create(assignment=a2, evaluator=manager, round='PRIMARY')
    EvaluationAnswer.objects.create(response=r2, item=emp_items[0], score=3)
    EvaluationAnswer.objects.create(response=r2, item=emp_items[1], score=None)

    # 정민수: 1차 최본부장(제출)
    a3 = EvaluatorAssignment.objects.create(
        cycle=cycle,
        target_type=TargetType.EMPLOYEE,
        target_user=member3,
        primary_evaluator=director,
    )
    r3 = EvaluationResponse.objects.create(
        assignment=a3,
        evaluator=director,
        round='PRIMARY',
        status=ResponseStatus.SUBMITTED,
    )
    for item in emp_items:
        EvaluationAnswer.objects.create(response=r3, item=item, score=5)

    # 개발1팀(부서): 1차 박팀장(미시작)
    a4 = EvaluatorAssignment.objects.create(
        cycle=cycle,
        target_type=TargetType.DEPARTMENT,
        target_department=dev,
        primary_evaluator=manager,
    )

    # 인사팀(부서): 1차 최본부장(임시저장 0/2)
    a5 = EvaluatorAssignment.objects.create(
        cycle=cycle,
        target_type=TargetType.DEPARTMENT,
        target_department=hr,
        primary_evaluator=director,
    )
    EvaluationResponse.objects.create(assignment=a5, evaluator=director, round='PRIMARY')

    return {
        'cycle': cycle,
        'dev': dev,
        'hr': hr,
        'manager': manager,
        'director': director,
        'member1': member1,
        'member2': member2,
        'member3': member3,
        'emp_items': emp_items,
        'dept_items': dept_items,
        'submitted_response': r1,
        'draft_response': r2,
        'assignments': [a1, a2, a3, a4, a5],
    }


@pytest.fixture
def manager_client(db, scenario):
    client = APIClient()
    login(client, '박팀장', '20180001', 'managerPass1!')
    return client
