"""미응답자 모니터링 테스트 (FR-A-06 6-3)."""

import pytest

pytestmark = pytest.mark.django_db


def url(cycle):
    return f'/api/admin/cycles/{cycle.id}/status/pending/'


def by_name(res):
    return {r['evaluator']['name']: r for r in res.data['results']}


def test_제출하지_않은_평가자만_나온다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']))

    assert res.status_code == 200
    # 박팀장(임시1+미시작1), 최본부장(미시작1+임시1)
    assert res.data['count'] == 2
    assert res.data['pending_total'] == 4


def test_미시작_건이_미응답자_목록에_포함된다(admin_client, scenario):
    """수용 기준: 미시작(레코드 없음) 건이 미응답자 목록에 포함된다."""
    res = admin_client.get(url(scenario['cycle']))

    manager = by_name(res)['박팀장']
    assert manager['not_started'] == 1
    assert manager['draft'] == 1
    assert manager['pending_count'] == 2

    # 미시작 건은 response_id가 없다
    not_started = [t for t in manager['pending_targets'] if t['status'] == 'NOT_STARTED']
    assert len(not_started) == 1
    assert not_started[0]['response_id'] is None
    assert not_started[0]['target_name'] == '개발1팀'
    assert not_started[0]['target_type'] == 'DEPARTMENT'


def test_평가자_단위로_묶인다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']))

    director = by_name(res)['최본부장']
    assert director['pending_count'] == 2
    assert len(director['pending_targets']) == 2

    rounds = {t['round'] for t in director['pending_targets']}
    assert rounds == {'PRIMARY', 'SECONDARY'}


def test_미응답_건수_내림차순으로_정렬된다(admin_client, scenario, dept_extra_pending):
    res = admin_client.get(url(scenario['cycle']))

    counts = [r['pending_count'] for r in res.data['results']]
    assert counts == sorted(counts, reverse=True)
    assert res.data['results'][0]['evaluator']['name'] == '박팀장'


def test_평가자_부서_정보가_포함된다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']))

    assert by_name(res)['박팀장']['evaluator']['department_name'] == '개발1팀'


def test_진행률이_담긴다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']))

    draft = next(t for t in by_name(res)['박팀장']['pending_targets'] if t['status'] == 'DRAFT')
    assert draft['progress'] == 50


def test_부서로_필터된다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']), {'department': scenario['dev'].id})

    assert res.data['count'] == 1
    assert res.data['results'][0]['evaluator']['name'] == '박팀장'


def test_평가자명으로_검색된다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']), {'search': '최본'})

    assert res.data['count'] == 1


def test_모두_제출되면_미응답자가_없다(admin_client, scenario):
    from apps.evaluations.models import EvaluationAnswer, EvaluationResponse, ResponseStatus

    cycle = scenario['cycle']
    # 남은 배정에 대해 제출 상태 평가지를 만들어 둔다
    for assignment in scenario['assignments']:
        items = (
            scenario['emp_items']
            if assignment.target_type == 'EMPLOYEE'
            else scenario['dept_items']
        )
        for round_value, evaluator in [
            ('PRIMARY', assignment.primary_evaluator),
            ('SECONDARY', assignment.secondary_evaluator),
        ]:
            if evaluator is None:
                continue
            response, _ = EvaluationResponse.objects.get_or_create(
                assignment=assignment, round=round_value, defaults={'evaluator': evaluator}
            )
            for item in items:
                EvaluationAnswer.objects.update_or_create(
                    response=response, item=item, defaults={'score': 4}
                )
            response.status = ResponseStatus.SUBMITTED
            response.save()

    res = admin_client.get(url(cycle))

    assert res.data['count'] == 0
    assert res.data['pending_total'] == 0


@pytest.fixture
def dept_extra_pending(scenario):
    """박팀장에게 미응답 1건을 더 붙여 정렬을 검증할 수 있게 한다."""
    from apps.accounts.models import User
    from apps.evaluations.models import EvaluatorAssignment, TargetType

    extra = User.objects.create_user(
        employee_no='20230009',
        name='추가대상',
        password='pass123456!',
        department=scenario['dev'],
    )
    return EvaluatorAssignment.objects.create(
        cycle=scenario['cycle'],
        target_type=TargetType.EMPLOYEE,
        target_user=extra,
        primary_evaluator=scenario['manager'],
    )
