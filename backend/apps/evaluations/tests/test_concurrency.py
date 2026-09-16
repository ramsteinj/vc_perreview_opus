"""동시 제출 방지 테스트 (specs/04-employee-features.md FR-E-06).

select_for_update가 실제로 동작하는지 확인하려면 자동 커밋 환경이 필요하므로
transaction=True를 쓴다. 이 테스트는 다른 테스트보다 느리다.
"""

import threading

import pytest
from django.db import connections

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
from apps.evaluations.services import response as response_service


@pytest.fixture
def scenario(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        dept = Department.objects.create(code='CONC', name='동시성팀')
        evaluator = User.objects.create_user(
            employee_no='90001', name='평가자', password='pass123456!', department=dept
        )
        target = User.objects.create_user(
            employee_no='90002', name='대상자', password='pass123456!', department=dept
        )
        cycle = EvaluationCycle.objects.create(
            name='동시성 회차',
            year=2026,
            starts_on='2026-01-01',
            ends_on='2099-12-31',
            status=CycleStatus.OPEN,
        )
        item = EvaluationItem.objects.create(
            cycle=cycle, target_type=TargetType.EMPLOYEE, code='A', title='항목', weight=100
        )
        assignment = EvaluatorAssignment.objects.create(
            cycle=cycle,
            target_type=TargetType.EMPLOYEE,
            target_user=target,
            primary_evaluator=evaluator,
        )
        response = EvaluationResponse.objects.create(
            assignment=assignment, evaluator=evaluator, round='PRIMARY'
        )
        EvaluationAnswer.objects.create(response=response, item=item, score=4)

    yield {'response': response, 'evaluator': evaluator, 'assignment': assignment}

    with django_db_blocker.unblock():
        EvaluationAnswer.objects.all().delete()
        EvaluationResponse.objects.all().delete()
        EvaluatorAssignment.objects.all().delete()
        EvaluationItem.objects.all().delete()
        EvaluationCycle.objects.all().delete()
        User.objects.filter(employee_no__startswith='9000').delete()
        Department.objects.filter(code='CONC').delete()


@pytest.mark.django_db(transaction=True)
def test_동시_제출은_하나만_성공한다(scenario):
    """두 스레드가 동시에 제출해도 하나만 통과하고 나머지는 거부된다."""
    response = scenario['response']
    evaluator = scenario['evaluator']

    results = []
    barrier = threading.Barrier(2)

    def worker():
        barrier.wait()  # 두 스레드를 같은 순간에 출발시킨다
        try:
            response_service.submit(response.id, evaluator)
            results.append('OK')
        except Exception as exc:  # noqa: BLE001 - 어떤 거부든 실패로 집계한다
            results.append(type(exc).__name__)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert results.count('OK') == 1, f'정확히 한 번만 성공해야 한다: {results}'
    assert 'AlreadySubmitted' in results

    submitted = EvaluationResponse.objects.filter(pk=response.id, status=ResponseStatus.SUBMITTED)
    assert submitted.count() == 1
