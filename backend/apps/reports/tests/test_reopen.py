"""평가지 열람·반려 테스트 (FR-A-06 6-4)."""

import pytest
from rest_framework.test import APIClient

from apps.evaluations.models import EvaluationResponse, ResponseStatus

pytestmark = pytest.mark.django_db


def url(response_id):
    return f'/api/admin/responses/{response_id}/'


def reopen_url(response_id):
    return f'{url(response_id)}reopen/'


# ── 열람 ─────────────────────────────────────────────────────


def test_관리자는_타인의_평가지를_열람한다(admin_client, scenario):
    response = scenario['submitted_response']

    res = admin_client.get(url(response.id))

    assert res.status_code == 200
    assert res.data['evaluator']['name'] == '박팀장'
    assert res.data['target']['name'] == '김철수'
    assert res.data['status'] == ResponseStatus.SUBMITTED
    assert len(res.data['items']) == 2
    assert res.data['items'][0]['answer']['score'] == 4


def test_직원은_열람할_수_없다(manager_client, scenario):
    res = manager_client.get(url(scenario['submitted_response'].id))
    assert res.status_code == 403


def test_비인증이면_401이다(scenario):
    assert APIClient().get(url(scenario['submitted_response'].id)).status_code == 401


# ── 반려 ─────────────────────────────────────────────────────


def test_제출된_평가지를_반려한다(admin_client, scenario):
    response = scenario['submitted_response']

    res = admin_client.post(reopen_url(response.id), {'reason': '평가 기준 재안내'}, format='json')

    assert res.status_code == 200
    assert res.data['status'] == ResponseStatus.DRAFT
    assert res.data['submitted_at'] is None

    response.refresh_from_db()
    assert response.status == ResponseStatus.DRAFT
    assert response.submitted_at is None


def test_사유_없이도_반려할_수_있다(admin_client, scenario):
    res = admin_client.post(reopen_url(scenario['submitted_response'].id), {}, format='json')
    assert res.status_code == 200


def test_임시저장_평가지는_반려할_수_없다(admin_client, scenario):
    res = admin_client.post(reopen_url(scenario['draft_response'].id), {}, format='json')

    assert res.status_code == 409
    assert res.data['code'] == 'NOT_SUBMITTED'


def test_직원은_반려할_수_없다(manager_client, scenario):
    res = manager_client.post(reopen_url(scenario['submitted_response'].id), {}, format='json')

    assert res.status_code == 403
    scenario['submitted_response'].refresh_from_db()
    assert scenario['submitted_response'].status == ResponseStatus.SUBMITTED


def test_반려_후_현황_집계가_바뀐다(admin_client, scenario):
    cycle = scenario['cycle']
    before = admin_client.get(f'/api/admin/cycles/{cycle.id}/status/summary/')

    admin_client.post(reopen_url(scenario['submitted_response'].id), {}, format='json')

    after = admin_client.get(f'/api/admin/cycles/{cycle.id}/status/summary/')

    assert after.data['overall']['submitted'] == before.data['overall']['submitted'] - 1
    assert after.data['overall']['draft'] == before.data['overall']['draft'] + 1


def test_반려하면_평가자가_다시_수정_제출할_수_있다(admin_client, scenario):
    """수용 기준: 반려한 평가지는 평가자 화면에서 다시 수정 가능 상태가 된다."""
    response = scenario['submitted_response']
    client = APIClient()
    login = client.post(
        '/api/auth/login/',
        {'name': '박팀장', 'employee_no': '20180001', 'password': 'managerPass1!'},
        format='json',
    )
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {login.data["access"]}')

    # 반려 전에는 수정이 막힌다
    blocked = client.put(
        f'/api/my/responses/{response.id}/', {'overall_comment': '수정 시도'}, format='json'
    )
    assert blocked.status_code == 409
    assert blocked.data['code'] == 'ALREADY_SUBMITTED'

    admin_client.post(reopen_url(response.id), {'reason': '재작성 요청'}, format='json')

    # 반려 후에는 editable이 되고 수정·재제출이 가능하다
    detail = client.get(f'/api/my/responses/{response.id}/')
    assert detail.data['editable'] is True
    assert detail.data['status'] == ResponseStatus.DRAFT

    saved = client.put(
        f'/api/my/responses/{response.id}/', {'overall_comment': '재작성했습니다'}, format='json'
    )
    assert saved.status_code == 200

    resubmitted = client.post(f'/api/my/responses/{response.id}/submit/')
    assert resubmitted.status_code == 200
    assert resubmitted.data['status'] == ResponseStatus.SUBMITTED


def test_반려한_평가지가_내_평가_목록에_수정_가능으로_나온다(admin_client, scenario):
    response = scenario['submitted_response']
    admin_client.post(reopen_url(response.id), {}, format='json')

    client = APIClient()
    login = client.post(
        '/api/auth/login/',
        {'name': '박팀장', 'employee_no': '20180001', 'password': 'managerPass1!'},
        format='json',
    )
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {login.data["access"]}')

    res = client.get('/api/my/assignments/')

    row = next(r for r in res.data['results'] if r['response_id'] == response.id)
    assert row['status'] == ResponseStatus.DRAFT
    assert row['editable'] is True


def test_재산출_필요_플래그가_포함된다(admin_client, scenario):
    """ScoreResult는 Phase 6에서 추가되므로 현재는 항상 False다."""
    res = admin_client.post(reopen_url(scenario['submitted_response'].id), {}, format='json')

    assert 'recalculation_required' in res.data
    assert res.data['recalculation_required'] is False


def test_없는_평가지를_반려하면_404다(admin_client, scenario):
    res = admin_client.post(reopen_url(999999), {}, format='json')
    assert res.status_code == 404


def test_반려는_제출_이력만_되돌리고_답변은_보존한다(admin_client, scenario):
    response = scenario['submitted_response']
    before = list(
        EvaluationResponse.objects.get(pk=response.id).answers.values_list('item_id', 'score')
    )

    admin_client.post(reopen_url(response.id), {}, format='json')

    after = list(
        EvaluationResponse.objects.get(pk=response.id).answers.values_list('item_id', 'score')
    )
    assert before == after
