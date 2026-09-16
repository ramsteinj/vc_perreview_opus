"""CSV 내보내기 성능 테스트 (specs/05-admin-features.md FR-A-07 수용 기준).

1000명 규모에서 응답 시간이 5초를 넘지 않아야 한다.
데이터 구축 비용이 있어 다른 테스트보다 느리다.
"""

import time

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

pytestmark = pytest.mark.django_db

SCALE = 1000
BUDGET_SECONDS = 5.0


@pytest.fixture(scope='module')
def _unused():
    return None


@pytest.fixture
def large_cycle(db):
    """부서 20개, 직원 1000명, 각자 1차 평가 제출 완료."""
    departments = Department.objects.bulk_create(
        [Department(code=f'D{i:03d}', name=f'{i}팀') for i in range(20)]
    )
    departments = list(Department.objects.order_by('code'))

    evaluators = [
        User(
            employee_no=f'EV{i:03d}',
            name=f'평가자{i}',
            department=departments[i % 20],
            is_active=True,
        )
        for i in range(20)
    ]
    targets = [
        User(
            employee_no=f'T{i:05d}',
            name=f'직원{i}',
            position='선임',
            department=departments[i % 20],
            is_active=True,
        )
        for i in range(SCALE)
    ]
    for user in evaluators + targets:
        user.set_unusable_password()
    User.objects.bulk_create(evaluators + targets, batch_size=500)

    evaluators = list(User.objects.filter(employee_no__startswith='EV').order_by('employee_no'))
    targets = list(User.objects.filter(employee_no__startswith='T0').order_by('employee_no'))

    cycle = EvaluationCycle.objects.create(
        name='대규모 회차',
        year=2026,
        starts_on='2026-01-01',
        ends_on='2099-12-31',
        status=CycleStatus.OPEN,
    )
    items = EvaluationItem.objects.bulk_create(
        [
            EvaluationItem(
                cycle=cycle,
                target_type=TargetType.EMPLOYEE,
                code=f'E{i}',
                title=f'항목{i}',
                weight=weight,
                max_score=5,
                order=i,
            )
            for i, weight in enumerate((50, 30, 20), start=1)
        ]
    )
    items = list(EvaluationItem.objects.filter(cycle=cycle).order_by('order'))

    assignments = EvaluatorAssignment.objects.bulk_create(
        [
            EvaluatorAssignment(
                cycle=cycle,
                target_type=TargetType.EMPLOYEE,
                target_user=target,
                primary_evaluator=evaluators[index % 20],
            )
            for index, target in enumerate(targets)
        ],
        batch_size=500,
    )
    assignments = list(EvaluatorAssignment.objects.filter(cycle=cycle).order_by('id'))

    responses = EvaluationResponse.objects.bulk_create(
        [
            EvaluationResponse(
                assignment=assignment,
                evaluator=assignment.primary_evaluator,
                round='PRIMARY',
                status=ResponseStatus.SUBMITTED,
            )
            for assignment in assignments
        ],
        batch_size=500,
    )
    responses = list(EvaluationResponse.objects.filter(assignment__cycle=cycle).order_by('id'))

    EvaluationAnswer.objects.bulk_create(
        [
            EvaluationAnswer(response=response, item=item, score=(index % 5) + 1)
            for index, response in enumerate(responses)
            for item in items
        ],
        batch_size=1000,
    )

    return cycle


@pytest.fixture
def admin_client_large(db):
    client = APIClient()
    res = client.post(
        '/api/auth/login/',
        {
            'name': settings.DEFAULT_ADMIN_NAME,
            'employee_no': settings.DEFAULT_ADMIN_EMPLOYEE_NO,
            'password': settings.DEFAULT_ADMIN_PASSWORD,
        },
        format='json',
    )
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {res.data["access"]}')
    return client


def measure(client, path):
    started = time.perf_counter()
    response = client.get(path)
    body = b''.join(response.streaming_content)
    elapsed = time.perf_counter() - started
    return response, body, elapsed


def test_1000명_점수_CSV가_5초_이내다(admin_client_large, large_cycle):
    admin_client_large.post(f'/api/admin/cycles/{large_cycle.id}/calculate/')

    response, body, elapsed = measure(
        admin_client_large, f'/api/admin/cycles/{large_cycle.id}/export/scores.csv'
    )

    line_count = body.decode('utf-8-sig').count('\r\n')
    assert response.status_code == 200
    assert line_count == SCALE + 1  # 헤더 + 1000행
    assert elapsed < BUDGET_SECONDS, f'{elapsed:.2f}초 (예산 {BUDGET_SECONDS}초)'
    print(f'\n  scores.csv  {SCALE}행 → {elapsed:.2f}초')


def test_1000명_응답상세_CSV가_5초_이내다(admin_client_large, large_cycle):
    response, body, elapsed = measure(
        admin_client_large, f'/api/admin/cycles/{large_cycle.id}/export/responses.csv'
    )

    line_count = body.decode('utf-8-sig').count('\r\n')
    assert response.status_code == 200
    assert line_count == SCALE + 1
    assert elapsed < BUDGET_SECONDS, f'{elapsed:.2f}초 (예산 {BUDGET_SECONDS}초)'
    print(f'\n  responses.csv  {SCALE}행 → {elapsed:.2f}초')


def test_1000명_점수_산출이_10초_이내다(admin_client_large, large_cycle):
    """specs/09-non-functional.md §2: 점수 산출(1000명) < 10s"""
    started = time.perf_counter()
    response = admin_client_large.post(f'/api/admin/cycles/{large_cycle.id}/calculate/')
    elapsed = time.perf_counter() - started

    assert response.data['calculated'] == SCALE
    assert elapsed < 10.0, f'{elapsed:.2f}초 (예산 10초)'
    print(f'\n  점수 산출  {SCALE}명 → {elapsed:.2f}초')
