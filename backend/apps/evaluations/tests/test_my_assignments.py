"""내 평가 목록 테스트 (specs/04-employee-features.md FR-E-02, FR-E-05)."""

import pytest

from apps.evaluations.models import CycleStatus, EvaluationResponse, ResponseStatus

pytestmark = pytest.mark.django_db

URL = '/api/my/assignments/'


def test_비인증이면_401이다():
    from rest_framework.test import APIClient

    assert APIClient().get(URL).status_code == 401


def test_배정된_대상이_목록에_나온다(manager_client, assignment, member):
    res = manager_client.get(URL)

    assert res.status_code == 200
    assert res.data['summary']['total'] == 1
    row = res.data['results'][0]
    assert row['target']['name'] == '김철수'
    assert row['round'] == 'PRIMARY'
    assert row['status'] == 'NOT_STARTED'
    assert row['response_id'] is None
    assert row['total_items'] == 3


def test_배정되지_않은_사용자에게는_빈_목록이다(member_client, assignment):
    res = member_client.get(URL)

    assert res.data['summary']['total'] == 0
    assert res.data['results'] == []


def test_2차_평가자에게도_행이_생긴다(director_client, assignment_with_secondary):
    res = director_client.get(URL)

    assert res.data['summary']['total'] == 1
    assert res.data['results'][0]['round'] == 'SECONDARY'


def test_DRAFT_회차의_배정은_나오지_않는다(manager_client, assignment, open_cycle):
    open_cycle.status = CycleStatus.DRAFT
    open_cycle.save()

    res = manager_client.get(URL)

    assert res.data['summary']['total'] == 0


def test_마감_회차의_배정은_나오지_않는다(manager_client, assignment, open_cycle):
    open_cycle.status = CycleStatus.CLOSED
    open_cycle.save()

    res = manager_client.get(URL)

    assert res.data['summary']['total'] == 0


def test_요약_집계가_상태별로_맞다(manager_client, assignment, open_cycle, dept, director):
    from apps.accounts.models import User
    from apps.evaluations.models import EvaluatorAssignment, TargetType

    other = User.objects.create_user(
        employee_no='20230777', name='이영희', password='pass123456!', department=dept
    )
    second = EvaluatorAssignment.objects.create(
        cycle=open_cycle,
        target_type=TargetType.EMPLOYEE,
        target_user=other,
        primary_evaluator=assignment.primary_evaluator,
    )
    EvaluationResponse.objects.create(
        assignment=second,
        evaluator=assignment.primary_evaluator,
        round='PRIMARY',
        status=ResponseStatus.SUBMITTED,
    )

    res = manager_client.get(URL)

    assert res.data['summary'] == {'total': 2, 'submitted': 1, 'draft': 0, 'not_started': 1}


def test_마감일이_지나면_editable이_거짓이다(manager_client, assignment, open_cycle):
    from datetime import date, timedelta

    open_cycle.starts_on = date.today() - timedelta(days=30)
    open_cycle.ends_on = date.today() - timedelta(days=1)
    open_cycle.save()

    res = manager_client.get(URL)

    assert res.data['results'][0]['editable'] is False
