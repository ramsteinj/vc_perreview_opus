"""점수 산출 API 테스트 (specs/05-admin-features.md FR-A-08, FR-A-09)."""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.evaluations.models import CycleStatus
from apps.reports.models import ScoreResult

pytestmark = pytest.mark.django_db

D = Decimal


def calc_url(cycle):
    return f'/api/admin/cycles/{cycle.id}/calculate/'


def scores_url(cycle):
    return f'/api/admin/cycles/{cycle.id}/scores/'


def dept_scores_url(cycle):
    return f'/api/admin/cycles/{cycle.id}/department-scores/'


# ── 권한 ─────────────────────────────────────────────────────


def test_직원은_산출할_수_없다(manager_client, scenario):
    assert manager_client.post(calc_url(scenario['cycle'])).status_code == 403


def test_비인증이면_401이다(scenario):
    assert APIClient().post(calc_url(scenario['cycle'])).status_code == 401


def test_직원은_점수를_조회할_수_없다(manager_client, scenario):
    assert manager_client.get(scores_url(scenario['cycle'])).status_code == 403


# ── 산출 ─────────────────────────────────────────────────────


def test_산출_결과_요약을_반환한다(admin_client, scenario):
    res = admin_client.post(calc_url(scenario['cycle']))

    assert res.status_code == 200
    # 개인 배정 3건(김철수/이영희/정민수) 중 제출된 것은 2건
    assert res.data['total_targets'] == 3
    assert res.data['calculated'] == 2
    assert res.data['skipped'] == 1
    assert res.data['skipped_reasons'][0]['reason'] == 'PRIMARY_NOT_SUBMITTED'
    assert res.data['skipped_reasons'][0]['name'] == '이영희'


def test_마감되지_않은_회차는_잠정_결과로_표시된다(admin_client, scenario):
    res = admin_client.post(calc_url(scenario['cycle']))
    assert res.data['is_provisional'] is True


def test_산출_결과가_저장된다(admin_client, scenario):
    admin_client.post(calc_url(scenario['cycle']))

    score = ScoreResult.objects.get(cycle=scenario['cycle'], user=scenario['member1'])
    # 항목 2개 각 가중치 50, 점수 4/5 → 80.00
    assert score.primary_score == D('80.00')
    assert score.individual_score == D('80.00')
    assert score.final_score == D('80.00')


def test_재산출은_멱등하다(admin_client, scenario):
    first = admin_client.post(calc_url(scenario['cycle']))
    second = admin_client.post(calc_url(scenario['cycle']))

    assert first.data['calculated'] == second.data['calculated']
    assert ScoreResult.objects.filter(cycle=scenario['cycle']).count() == 2


# ── 목록 ─────────────────────────────────────────────────────


def test_점수_목록을_조회한다(admin_client, scenario):
    admin_client.post(calc_url(scenario['cycle']))

    res = admin_client.get(scores_url(scenario['cycle']))

    assert res.status_code == 200
    assert res.data['count'] == 2
    assert res.data['total_targets'] == 3
    assert res.data['not_calculated'] == 1

    row = res.data['results'][0]
    assert 'final_score' in row
    assert row['user']['employee_no']


def test_최종_점수_내림차순이_기본이다(admin_client, scenario):
    admin_client.post(calc_url(scenario['cycle']))

    res = admin_client.get(scores_url(scenario['cycle']))

    scores = [D(str(r['final_score'])) for r in res.data['results']]
    assert scores == sorted(scores, reverse=True)


def test_부서로_필터된다(admin_client, scenario):
    admin_client.post(calc_url(scenario['cycle']))

    res = admin_client.get(scores_url(scenario['cycle']), {'department': scenario['dev'].id})

    assert res.data['count'] == 1
    assert res.data['results'][0]['user']['name'] == '김철수'


def test_성명으로_검색된다(admin_client, scenario):
    admin_client.post(calc_url(scenario['cycle']))

    res = admin_client.get(scores_url(scenario['cycle']), {'search': '정민수'})

    assert res.data['count'] == 1


def test_허용되지_않은_정렬은_기본값으로_대체된다(admin_client, scenario):
    admin_client.post(calc_url(scenario['cycle']))

    res = admin_client.get(scores_url(scenario['cycle']), {'ordering': 'password'})

    assert res.status_code == 200
    scores = [D(str(r['final_score'])) for r in res.data['results']]
    assert scores == sorted(scores, reverse=True)


def test_산출_전에는_목록이_비어있다(admin_client, scenario):
    res = admin_client.get(scores_url(scenario['cycle']))

    assert res.data['count'] == 0
    assert res.data['not_calculated'] == 3


# ── 부서 성과 점수 ───────────────────────────────────────────


def test_부서_성과_점수를_조회한다(admin_client, scenario):
    res = admin_client.get(dept_scores_url(scenario['cycle']))

    assert res.status_code == 200
    assert res.data['count'] == 2

    by_name = {r['department_name']: r for r in res.data['results']}
    # 두 부서 모두 부서 평가지가 미제출이다
    assert by_name['개발1팀']['evaluated'] is False
    assert by_name['개발1팀']['department_score'] is None
    assert by_name['개발1팀']['department_adjustment'] == '0.00'


def test_가감_파라미터가_함께_반환된다(admin_client, scenario):
    res = admin_client.get(dept_scores_url(scenario['cycle']))

    params = res.data['parameters']
    assert params['baseline'] == '70.00'
    assert params['factor'] == '0.20'
    assert params['limit'] == '10.00'


def test_파라미터를_바꾸면_가감이_달라진다(admin_client, scenario):
    """회차별 파라미터 변경 후 재산출하면 최종 점수에 반영된다."""
    from apps.evaluations.models import (
        EvaluationAnswer,
        EvaluationResponse,
        EvaluatorAssignment,
        ResponseStatus,
        TargetType,
    )

    cycle = scenario['cycle']
    dept_assignment = EvaluatorAssignment.objects.get(
        cycle=cycle, target_type=TargetType.DEPARTMENT, target_department=scenario['dev']
    )
    response = EvaluationResponse.objects.create(
        assignment=dept_assignment,
        evaluator=scenario['manager'],
        round='PRIMARY',
        status=ResponseStatus.SUBMITTED,
    )
    for item in scenario['dept_items']:
        EvaluationAnswer.objects.create(response=response, item=item, score=5)

    admin_client.post(calc_url(cycle))
    before = ScoreResult.objects.get(cycle=cycle, user=scenario['member1'])
    # 부서 100.00 → (100-70)×0.2 = +6.00
    assert before.department_adjustment == D('6.00')

    admin_client.patch(
        f'/api/admin/cycles/{cycle.id}/', {'dept_adjust_factor': '0.50'}, format='json'
    )
    admin_client.post(calc_url(cycle))

    after = ScoreResult.objects.get(cycle=cycle, user=scenario['member1'])
    # (100-70)×0.5 = +15.00 → 한도 10.00으로 절단
    assert after.department_adjustment == D('10.00')


# ── 마감 시 자동 산출 ────────────────────────────────────────


def test_회차를_마감하면_자동_산출된다(admin_client, scenario):
    cycle = scenario['cycle']

    res = admin_client.post(f'/api/admin/cycles/{cycle.id}/close/?confirm=true')

    assert res.status_code == 200
    assert res.data['calculation']['calculated'] == 2
    assert ScoreResult.objects.filter(cycle=cycle).count() == 2

    cycle.refresh_from_db()
    assert cycle.status == CycleStatus.CLOSED


def test_마감_후_목록은_잠정이_아니다(admin_client, scenario):
    cycle = scenario['cycle']
    admin_client.post(f'/api/admin/cycles/{cycle.id}/close/?confirm=true')

    res = admin_client.get(scores_url(cycle))

    assert res.data['is_provisional'] is False


# ── 반려와 재산출 ────────────────────────────────────────────


def test_산출_후_반려하면_재산출_필요가_표시된다(admin_client, scenario):
    admin_client.post(calc_url(scenario['cycle']))

    res = admin_client.post(
        f"/api/admin/responses/{scenario['submitted_response'].id}/reopen/", {}, format='json'
    )

    assert res.data['recalculation_required'] is True


def test_반려_후_재산출하면_해당_대상이_제외된다(admin_client, scenario):
    cycle = scenario['cycle']
    admin_client.post(calc_url(cycle))
    assert ScoreResult.objects.filter(cycle=cycle, user=scenario['member1']).exists()

    admin_client.post(
        f"/api/admin/responses/{scenario['submitted_response'].id}/reopen/", {}, format='json'
    )
    res = admin_client.post(calc_url(cycle))

    assert res.data['calculated'] == 1
    assert not ScoreResult.objects.filter(cycle=cycle, user=scenario['member1']).exists()
