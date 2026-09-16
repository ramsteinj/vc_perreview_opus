"""응답 현황 요약 테스트 (specs/05-admin-features.md FR-A-06 6-1)."""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def url(cycle):
    return f'/api/admin/cycles/{cycle.id}/status/summary/'


def test_관리자가_아니면_접근할_수_없다(manager_client, scenario):
    assert manager_client.get(url(scenario['cycle'])).status_code == 403


def test_비인증이면_401이다(scenario):
    assert APIClient().get(url(scenario['cycle'])).status_code == 401


def test_분모는_기대_응답_수다(admin_client, scenario):
    """배정 5건 중 1건은 2차 평가자가 있으므로 기대 응답은 6건이다."""
    res = admin_client.get(url(scenario['cycle']))

    assert res.status_code == 200
    overall = res.data['overall']
    assert overall['total_responses'] == 6
    assert overall['submitted'] == 2
    assert overall['draft'] == 2
    assert overall['not_started'] == 2


def test_미시작_건이_분모에_포함된다(admin_client, scenario):
    """수용 기준: 미시작(레코드 없음) 건이 분모에 포함된다."""
    from apps.evaluations.models import EvaluationResponse

    res = admin_client.get(url(scenario['cycle']))

    record_count = EvaluationResponse.objects.filter(assignment__cycle=scenario['cycle']).count()

    assert record_count == 4
    assert res.data['overall']['total_responses'] == 6  # 레코드 수보다 크다
    assert res.data['overall']['not_started'] == 2


def test_제출률이_정확하다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']))

    # 2 / 6 = 33.33%
    assert res.data['overall']['submission_rate'] == Decimal('33.33')


def test_차수별_집계(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']))

    primary = res.data['by_round']['PRIMARY']
    secondary = res.data['by_round']['SECONDARY']

    assert primary['total'] == 5
    assert primary['submitted'] == 2
    assert secondary['total'] == 1
    assert secondary['submitted'] == 0
    assert secondary['not_started'] == 1


def test_대상_유형별_집계(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']))

    employee = res.data['by_target_type']['EMPLOYEE']
    department = res.data['by_target_type']['DEPARTMENT']

    assert employee['total'] == 4
    assert employee['submitted'] == 2
    assert department['total'] == 2
    assert department['submitted'] == 0


def test_부서별_제출률이_정확하다(admin_client, scenario):
    """수용 기준: 부서별 제출률이 정확히 계산된다.

    부서는 평가자 소속 기준이다.
      개발1팀 박팀장   : 김철수 1차(제출) + 이영희 1차(임시) + 개발1팀 1차(미시작) = 3건, 1건 제출
      인사팀 최본부장 : 김철수 2차(미시작) + 정민수 1차(제출) + 인사팀 1차(임시) = 3건, 1건 제출
    """
    res = admin_client.get(url(scenario['cycle']))

    by_dept = {row['department_name']: row for row in res.data['by_department']}

    assert by_dept['개발1팀']['total'] == 3
    assert by_dept['개발1팀']['submitted'] == 1
    assert by_dept['개발1팀']['draft'] == 1
    assert by_dept['개발1팀']['not_started'] == 1
    assert by_dept['개발1팀']['rate'] == Decimal('33.33')

    assert by_dept['인사팀']['total'] == 3
    assert by_dept['인사팀']['submitted'] == 1


def test_부서_집계_합이_전체와_같다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']))

    total = sum(row['total'] for row in res.data['by_department'])
    submitted = sum(row['submitted'] for row in res.data['by_department'])

    assert total == res.data['overall']['total_responses']
    assert submitted == res.data['overall']['submitted']


def test_회차_정보와_남은_일수가_포함된다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']))

    assert res.data['cycle']['name'] == '2026년 상반기 평가'
    assert res.data['cycle']['status'] == 'OPEN'
    assert res.data['cycle']['days_left'] > 0


def test_배정이_없으면_0으로_집계된다(admin_client, db):
    from apps.evaluations.models import CycleStatus, EvaluationCycle

    empty = EvaluationCycle.objects.create(
        name='빈 회차',
        year=2026,
        starts_on='2026-01-01',
        ends_on='2026-12-31',
        status=CycleStatus.DRAFT,
    )

    res = admin_client.get(url(empty))

    assert res.data['overall']['total_responses'] == 0
    assert res.data['overall']['submission_rate'] == Decimal('0.00')
    assert res.data['by_department'] == []


def test_집계_쿼리_수가_고정이다(admin_client, scenario, django_assert_num_queries):
    """N+1 방지. 배정·평가지·항목수 3개 쿼리 + 인증 오버헤드."""
    with django_assert_num_queries(5):
        admin_client.get(url(scenario['cycle']))
