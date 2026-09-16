"""평가지 작성·임시저장·제출 테스트 (FR-E-03 ~ FR-E-06)."""

from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient

from apps.evaluations.models import (
    CycleStatus,
    EvaluationAnswer,
    EvaluationResponse,
    ResponseStatus,
)

pytestmark = pytest.mark.django_db

URL = '/api/my/responses/'


@pytest.fixture
def response_id(manager_client, assignment):
    res = manager_client.post(URL, {'assignment': assignment.id}, format='json')
    return res.data['id']


# ── 생성 ─────────────────────────────────────────────────────


def test_평가지를_생성한다(manager_client, assignment, full_items):
    res = manager_client.post(URL, {'assignment': assignment.id}, format='json')

    assert res.status_code == 201
    assert res.data['status'] == ResponseStatus.DRAFT
    assert res.data['round'] == 'PRIMARY'
    assert res.data['progress'] == 0
    assert len(res.data['items']) == 3


def test_생성은_멱등하다(manager_client, assignment):
    first = manager_client.post(URL, {'assignment': assignment.id}, format='json')
    second = manager_client.post(URL, {'assignment': assignment.id}, format='json')

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.data['id'] == second.data['id']
    assert EvaluationResponse.objects.filter(assignment=assignment).count() == 1


def test_평가자가_아니면_생성할_수_없다(member_client, assignment):
    res = member_client.post(URL, {'assignment': assignment.id}, format='json')

    assert res.status_code == 403
    assert res.data['code'] == 'NOT_ASSIGNED_EVALUATOR'


def test_DRAFT_회차에서는_생성할_수_없다(manager_client, assignment, open_cycle):
    open_cycle.status = CycleStatus.DRAFT
    open_cycle.save()

    res = manager_client.post(URL, {'assignment': assignment.id}, format='json')

    assert res.status_code == 409
    assert res.data['code'] == 'CYCLE_NOT_OPEN'


def test_상세에_항목과_가중치가_담긴다(manager_client, response_id):
    res = manager_client.get(f'{URL}{response_id}/')

    item = res.data['items'][0]
    assert 'weight' in item
    assert 'max_score' in item
    assert item['answer'] == {'score': None, 'comment': ''}
    assert res.data['editable'] is True


# ── 권한 격리 ────────────────────────────────────────────────


def test_타인의_평가지는_조회할_수_없다(member_client, response_id):
    """완료 조건: 다른 사람의 평가지에 접근하면 403/404가 반환된다."""
    res = member_client.get(f'{URL}{response_id}/')
    assert res.status_code == 404


def test_타인의_평가지는_저장할_수_없다(member_client, response_id):
    res = member_client.put(f'{URL}{response_id}/', {'overall_comment': '침입'}, format='json')
    assert res.status_code == 404


def test_타인의_평가지는_제출할_수_없다(member_client, response_id):
    res = member_client.post(f'{URL}{response_id}/submit/')
    assert res.status_code == 404


def test_비인증이면_401이다(response_id):
    assert APIClient().get(f'{URL}{response_id}/').status_code == 401


# ── 임시 저장 ────────────────────────────────────────────────


def test_부분_저장이_허용된다(manager_client, response_id, full_items):
    res = manager_client.put(
        f'{URL}{response_id}/',
        {
            'answers': [
                {'item': full_items[0].id, 'score': 4, 'comment': ''},
                {'item': full_items[1].id, 'score': None, 'comment': '보류'},
            ],
            'overall_comment': '작성 중',
        },
        format='json',
    )

    assert res.status_code == 200
    assert res.data['answered_count'] == 1
    assert res.data['total_items'] == 3
    assert res.data['progress'] == 33


def test_임시저장_후_재조회하면_입력이_복원된다(manager_client, response_id, full_items):
    """완료 조건: 임시 저장 후 재접속 시 입력이 복원된다."""
    manager_client.put(
        f'{URL}{response_id}/',
        {
            'answers': [{'item': full_items[0].id, 'score': 5, 'comment': '우수'}],
            'overall_comment': '전반적으로 좋음',
        },
        format='json',
    )

    res = manager_client.get(f'{URL}{response_id}/')

    assert res.data['overall_comment'] == '전반적으로 좋음'
    first = next(i for i in res.data['items'] if i['id'] == full_items[0].id)
    assert first['answer'] == {'score': 5, 'comment': '우수'}


def test_반복_저장해도_답변이_중복되지_않는다(manager_client, response_id, full_items):
    for score in range(1, 6):
        manager_client.put(
            f'{URL}{response_id}/',
            {'answers': [{'item': full_items[0].id, 'score': score}]},
            format='json',
        )

    answers = EvaluationAnswer.objects.filter(response_id=response_id, item=full_items[0])
    assert answers.count() == 1
    assert answers.first().score == 5


def test_점수를_지우면_진행률이_감소한다(manager_client, response_id, full_items):
    manager_client.put(
        f'{URL}{response_id}/',
        {'answers': [{'item': i.id, 'score': 3} for i in full_items]},
        format='json',
    )

    res = manager_client.put(
        f'{URL}{response_id}/',
        {'answers': [{'item': full_items[0].id, 'score': None}]},
        format='json',
    )

    assert res.data['progress'] == 66
    assert res.data['answered_count'] == 2


def test_척도를_넘는_점수는_거부된다(manager_client, response_id, full_items):
    res = manager_client.put(
        f'{URL}{response_id}/',
        {'answers': [{'item': full_items[0].id, 'score': 9}]},
        format='json',
    )

    assert res.status_code == 400
    assert res.data['code'] == 'SCORE_OUT_OF_RANGE'


def test_다른_회차의_항목은_무시된다(manager_client, response_id, full_items):
    from apps.evaluations.models import EvaluationCycle, EvaluationItem, TargetType

    other_cycle = EvaluationCycle.objects.create(
        name='다른 회차', year=2026, starts_on='2027-01-01', ends_on='2027-01-31'
    )
    alien = EvaluationItem.objects.create(
        cycle=other_cycle, target_type=TargetType.EMPLOYEE, code='X', title='X', weight=100
    )

    res = manager_client.put(
        f'{URL}{response_id}/', {'answers': [{'item': alien.id, 'score': 5}]}, format='json'
    )

    assert res.status_code == 200
    assert res.data['answered_count'] == 0
    assert not EvaluationAnswer.objects.filter(response_id=response_id, item=alien).exists()


def test_마감일이_지나면_저장할_수_없다(manager_client, response_id, open_cycle, full_items):
    open_cycle.starts_on = date.today() - timedelta(days=30)
    open_cycle.ends_on = date.today() - timedelta(days=1)
    open_cycle.save()

    res = manager_client.put(
        f'{URL}{response_id}/',
        {'answers': [{'item': full_items[0].id, 'score': 4}]},
        format='json',
    )

    assert res.status_code == 409
    assert res.data['code'] == 'CYCLE_DEADLINE_PASSED'


# ── 제출 ─────────────────────────────────────────────────────


def fill_all(client, response_id, items, score=4):
    client.put(
        f'{URL}{response_id}/',
        {'answers': [{'item': i.id, 'score': score} for i in items]},
        format='json',
    )


def test_모두_입력하면_제출된다(manager_client, response_id, full_items):
    fill_all(manager_client, response_id, full_items)

    res = manager_client.post(f'{URL}{response_id}/submit/')

    assert res.status_code == 200
    assert res.data['status'] == ResponseStatus.SUBMITTED
    assert res.data['progress'] == 100
    assert res.data['submitted_at'] is not None


def test_미입력_항목이_있으면_제출이_거부된다(manager_client, response_id, full_items):
    """완료 조건: 미입력 항목이 있으면 제출이 거부된다."""
    manager_client.put(
        f'{URL}{response_id}/',
        {'answers': [{'item': full_items[0].id, 'score': 4}]},
        format='json',
    )

    res = manager_client.post(f'{URL}{response_id}/submit/')

    assert res.status_code == 400
    assert res.data['code'] == 'INCOMPLETE_ANSWERS'
    assert set(res.data['missing_items']) == {full_items[1].id, full_items[2].id}


def test_missing_items는_정수_리스트다(manager_client, response_id, full_items):
    res = manager_client.post(f'{URL}{response_id}/submit/')

    missing = res.data['missing_items']
    assert isinstance(missing, list)
    assert all(isinstance(i, int) for i in missing)


def test_제출_후_재제출하면_409다(manager_client, response_id, full_items):
    fill_all(manager_client, response_id, full_items)
    manager_client.post(f'{URL}{response_id}/submit/')

    res = manager_client.post(f'{URL}{response_id}/submit/')

    assert res.status_code == 409
    assert res.data['code'] == 'ALREADY_SUBMITTED'


def test_제출_후에는_수정할_수_없다(manager_client, response_id, full_items):
    fill_all(manager_client, response_id, full_items)
    manager_client.post(f'{URL}{response_id}/submit/')

    res = manager_client.put(
        f'{URL}{response_id}/', {'overall_comment': '수정 시도'}, format='json'
    )

    assert res.status_code == 409
    assert res.data['code'] == 'ALREADY_SUBMITTED'


def test_제출_후_상세는_읽기_전용이다(manager_client, response_id, full_items):
    fill_all(manager_client, response_id, full_items)
    manager_client.post(f'{URL}{response_id}/submit/')

    res = manager_client.get(f'{URL}{response_id}/')

    assert res.data['editable'] is False
    assert res.data['status'] == ResponseStatus.SUBMITTED


def test_중복_제출_시도에도_평가지는_하나다(manager_client, response_id, full_items, assignment):
    """완료 조건: 제출 버튼 더블 클릭에도 평가지가 하나만 제출된다."""
    fill_all(manager_client, response_id, full_items)

    first = manager_client.post(f'{URL}{response_id}/submit/')
    submitted_at = EvaluationResponse.objects.get(pk=response_id).submitted_at

    second = manager_client.post(f'{URL}{response_id}/submit/')

    assert first.status_code == 200
    assert second.status_code == 409

    submitted = EvaluationResponse.objects.filter(
        assignment=assignment, status=ResponseStatus.SUBMITTED
    )
    assert submitted.count() == 1
    # 두 번째 요청이 제출 시각을 덮어쓰지 않아야 한다
    assert submitted.first().submitted_at == submitted_at


def test_같은_배정_같은_차수에_평가지는_하나만_존재한다(assignment, manager):
    """DB UniqueConstraint가 중복 응답 방지의 최종 방어선이다."""
    from django.db import IntegrityError

    EvaluationResponse.objects.create(assignment=assignment, evaluator=manager, round='PRIMARY')

    with pytest.raises(IntegrityError):
        EvaluationResponse.objects.create(assignment=assignment, evaluator=manager, round='PRIMARY')


def test_1차와_2차는_별개의_평가지다(assignment_with_secondary, manager, director):
    EvaluationResponse.objects.create(
        assignment=assignment_with_secondary, evaluator=manager, round='PRIMARY'
    )
    EvaluationResponse.objects.create(
        assignment=assignment_with_secondary, evaluator=director, round='SECONDARY'
    )

    assert EvaluationResponse.objects.filter(assignment=assignment_with_secondary).count() == 2


def test_반려하면_다시_수정할_수_있다(manager_client, response_id, full_items):
    from apps.evaluations.services import response as response_service

    fill_all(manager_client, response_id, full_items)
    manager_client.post(f'{URL}{response_id}/submit/')

    response_service.reopen(EvaluationResponse.objects.get(pk=response_id))

    res = manager_client.put(f'{URL}{response_id}/', {'overall_comment': '재작성'}, format='json')

    assert res.status_code == 200
    assert res.data['status'] == ResponseStatus.DRAFT
    assert res.data['submitted_at'] is None


# ── 회차 마감 시 미제출 집계 (Phase 3 잔여분) ────────────────


def test_미제출_평가지가_있으면_마감에_확인이_필요하다(admin_client, assignment, open_cycle):
    res = admin_client.post(f'/api/admin/cycles/{open_cycle.id}/close/')

    assert res.status_code == 409
    assert res.data['code'] == 'PENDING_RESPONSES'
    assert res.data['pending_count'] == 1


def test_기대_응답_수는_2차_평가자를_포함한다(admin_client, assignment_with_secondary, open_cycle):
    res = admin_client.post(f'/api/admin/cycles/{open_cycle.id}/close/')

    assert res.data['pending_count'] == 2


def test_모두_제출되면_확인_없이_마감된다(
    admin_client, manager_client, assignment, open_cycle, full_items
):
    created = manager_client.post(URL, {'assignment': assignment.id}, format='json')
    fill_all(manager_client, created.data['id'], full_items)
    manager_client.post(f"{URL}{created.data['id']}/submit/")

    res = admin_client.post(f'/api/admin/cycles/{open_cycle.id}/close/')

    assert res.status_code == 200
    open_cycle.refresh_from_db()
    assert open_cycle.status == CycleStatus.CLOSED
