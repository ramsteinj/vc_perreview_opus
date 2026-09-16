"""평가자 배정 API 테스트 (specs/05-admin-features.md FR-A-05)."""

import pytest

from apps.evaluations.models import EvaluatorAssignment, TargetType

pytestmark = pytest.mark.django_db

URL = '/api/admin/assignments/'


def test_1차_평가자만으로_배정할_수_있다(admin_client, cycle, member, manager):
    """완료 조건: 2차 평가자 없이 배정을 저장할 수 있다."""
    res = admin_client.post(
        URL,
        {
            'cycle': cycle.id,
            'target_type': TargetType.EMPLOYEE,
            'target_user': member.id,
            'primary_evaluator': manager.id,
        },
        format='json',
    )

    assert res.status_code == 201
    assert res.data['secondary_evaluator'] is None


def test_2차_평가자를_함께_지정할_수_있다(admin_client, cycle, member, manager, director):
    res = admin_client.post(
        URL,
        {
            'cycle': cycle.id,
            'target_type': TargetType.EMPLOYEE,
            'target_user': member.id,
            'primary_evaluator': manager.id,
            'secondary_evaluator': director.id,
        },
        format='json',
    )

    assert res.status_code == 201
    assert res.data['secondary_evaluator_detail']['name'] == '최본부장'


def test_1차_평가자가_없으면_400이다(admin_client, cycle, member):
    res = admin_client.post(
        URL,
        {'cycle': cycle.id, 'target_type': TargetType.EMPLOYEE, 'target_user': member.id},
        format='json',
    )

    assert res.status_code == 400


def test_본인을_본인의_평가자로_지정하면_400이다(admin_client, cycle, member):
    """완료 조건: 본인을 본인의 평가자로 지정하면 거부된다."""
    res = admin_client.post(
        URL,
        {
            'cycle': cycle.id,
            'target_type': TargetType.EMPLOYEE,
            'target_user': member.id,
            'primary_evaluator': member.id,
        },
        format='json',
    )

    assert res.status_code == 400
    assert 'primary_evaluator' in res.data['fields']


def test_본인을_2차_평가자로_지정해도_400이다(admin_client, cycle, member, manager):
    res = admin_client.post(
        URL,
        {
            'cycle': cycle.id,
            'target_type': TargetType.EMPLOYEE,
            'target_user': member.id,
            'primary_evaluator': manager.id,
            'secondary_evaluator': member.id,
        },
        format='json',
    )

    assert res.status_code == 400


def test_1차와_2차가_같으면_400이다(admin_client, cycle, member, manager):
    res = admin_client.post(
        URL,
        {
            'cycle': cycle.id,
            'target_type': TargetType.EMPLOYEE,
            'target_user': member.id,
            'primary_evaluator': manager.id,
            'secondary_evaluator': manager.id,
        },
        format='json',
    )

    assert res.status_code == 400
    assert 'secondary_evaluator' in res.data['fields']


def test_같은_대상에_중복_배정하면_400이다(admin_client, cycle, member, manager, director):
    payload = {
        'cycle': cycle.id,
        'target_type': TargetType.EMPLOYEE,
        'target_user': member.id,
        'primary_evaluator': manager.id,
    }
    admin_client.post(URL, payload, format='json')

    res = admin_client.post(URL, {**payload, 'primary_evaluator': director.id}, format='json')

    assert res.status_code == 400
    assert res.data['code'] == 'ALREADY_ASSIGNED'


def test_개인_평가에_부서를_지정하면_400이다(admin_client, cycle, member, manager, dept):
    res = admin_client.post(
        URL,
        {
            'cycle': cycle.id,
            'target_type': TargetType.EMPLOYEE,
            'target_user': member.id,
            'target_department': dept.id,
            'primary_evaluator': manager.id,
        },
        format='json',
    )

    assert res.status_code == 400


def test_부서_평가를_배정한다(admin_client, cycle, dept, director):
    res = admin_client.post(
        URL,
        {
            'cycle': cycle.id,
            'target_type': TargetType.DEPARTMENT,
            'target_department': dept.id,
            'primary_evaluator': director.id,
        },
        format='json',
    )

    assert res.status_code == 201
    assert res.data['target_name'] == '개발1팀'


def test_부서_평가에_직원을_지정하면_400이다(admin_client, cycle, dept, member, director):
    res = admin_client.post(
        URL,
        {
            'cycle': cycle.id,
            'target_type': TargetType.DEPARTMENT,
            'target_department': dept.id,
            'target_user': member.id,
            'primary_evaluator': director.id,
        },
        format='json',
    )

    assert res.status_code == 400


# ── 배정 현황 ────────────────────────────────────────────────


def test_현황에는_미배정_대상도_포함된다(admin_client, cycle, member, manager):
    """미배정 대상이 행으로 보여야 누락을 발견할 수 있다."""
    EvaluatorAssignment.objects.create(
        cycle=cycle,
        target_type=TargetType.EMPLOYEE,
        target_user=member,
        primary_evaluator=manager,
    )

    res = admin_client.get(
        f'{URL}overview/', {'cycle': cycle.id, 'target_type': TargetType.EMPLOYEE}
    )

    assert res.status_code == 200
    assert res.data['assigned'] == 1
    assert res.data['unassigned'] >= 1

    rows = {row['target']['name']: row for row in res.data['results']}
    assert rows['김철수']['assigned'] is True
    assert rows['박팀장']['assigned'] is False
    assert rows['박팀장']['primary_evaluator'] is None


def test_현황을_부서로_필터한다(admin_client, cycle, member, dept):
    res = admin_client.get(
        f'{URL}overview/',
        {'cycle': cycle.id, 'target_type': TargetType.EMPLOYEE, 'department': dept.id},
    )

    names = [row['target']['name'] for row in res.data['results']]
    assert '김철수' in names
    assert 'ADMIN' not in names


def test_cycle_없이_현황을_요청하면_400이다(admin_client):
    res = admin_client.get(f'{URL}overview/', {'target_type': TargetType.EMPLOYEE})
    assert res.status_code == 400


# ── 일괄 배정 ────────────────────────────────────────────────


def test_부서_단위로_일괄_배정한다(admin_client, cycle, dept, member, manager, director):
    res = admin_client.post(
        f'{URL}bulk/',
        {
            'cycle': cycle.id,
            'target_type': TargetType.EMPLOYEE,
            'department': dept.id,
            'primary_evaluator': director.id,
        },
        format='json',
    )

    assert res.status_code == 200
    # 개발1팀 소속은 김철수 + 박팀장 2명
    assert res.data['created'] == 2


def test_일괄_배정에서_본인은_건너뛴다(admin_client, cycle, dept, member, manager):
    """평가자가 대상 부서에 속하면 자기 평가가 되므로 제외한다."""
    res = admin_client.post(
        f'{URL}bulk/',
        {
            'cycle': cycle.id,
            'target_type': TargetType.EMPLOYEE,
            'department': dept.id,
            'primary_evaluator': manager.id,
        },
        format='json',
    )

    assert res.data['created'] == 1
    assert len(res.data['skipped']) == 1
    assert res.data['skipped'][0]['reason'] == 'SELF_EVALUATION'
    assert res.data['skipped'][0]['name'] == '박팀장'


def test_기존_배정은_overwrite_없이_건너뛴다(admin_client, cycle, dept, member, manager, director):
    EvaluatorAssignment.objects.create(
        cycle=cycle,
        target_type=TargetType.EMPLOYEE,
        target_user=member,
        primary_evaluator=manager,
    )

    res = admin_client.post(
        f'{URL}bulk/',
        {
            'cycle': cycle.id,
            'target_type': TargetType.EMPLOYEE,
            'target_ids': [member.id],
            'primary_evaluator': director.id,
        },
        format='json',
    )

    assert res.data['created'] == 0
    assert res.data['skipped'][0]['reason'] == 'ALREADY_ASSIGNED'

    member.refresh_from_db()
    assignment = EvaluatorAssignment.objects.get(cycle=cycle, target_user=member)
    assert assignment.primary_evaluator == manager


def test_overwrite면_기존_배정을_덮어쓴다(admin_client, cycle, member, manager, director):
    EvaluatorAssignment.objects.create(
        cycle=cycle,
        target_type=TargetType.EMPLOYEE,
        target_user=member,
        primary_evaluator=manager,
    )

    res = admin_client.post(
        f'{URL}bulk/',
        {
            'cycle': cycle.id,
            'target_type': TargetType.EMPLOYEE,
            'target_ids': [member.id],
            'primary_evaluator': director.id,
            'overwrite': True,
        },
        format='json',
    )

    assert res.data['updated'] == 1
    assignment = EvaluatorAssignment.objects.get(cycle=cycle, target_user=member)
    assert assignment.primary_evaluator == director


def test_대상도_부서도_없으면_400이다(admin_client, cycle, manager):
    res = admin_client.post(
        f'{URL}bulk/',
        {'cycle': cycle.id, 'target_type': TargetType.EMPLOYEE, 'primary_evaluator': manager.id},
        format='json',
    )
    assert res.status_code == 400


def test_일괄_배정에서_1차와_2차가_같으면_400이다(admin_client, cycle, dept, manager):
    res = admin_client.post(
        f'{URL}bulk/',
        {
            'cycle': cycle.id,
            'target_type': TargetType.EMPLOYEE,
            'department': dept.id,
            'primary_evaluator': manager.id,
            'secondary_evaluator': manager.id,
        },
        format='json',
    )
    assert res.status_code == 400
