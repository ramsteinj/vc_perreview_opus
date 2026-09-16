"""평가 회차 API 테스트 (specs/05-admin-features.md FR-A-10)."""

import pytest

from apps.evaluations.models import CycleStatus, EvaluationItem, EvaluatorAssignment, TargetType

from .conftest import make_items

pytestmark = pytest.mark.django_db

URL = '/api/admin/cycles/'


def test_회차를_생성한다(admin_client):
    res = admin_client.post(
        URL,
        {
            'name': '2026년 상반기 평가',
            'year': 2026,
            'starts_on': '2026-09-01',
            'ends_on': '2026-09-30',
        },
        format='json',
    )

    assert res.status_code == 201
    assert res.data['status'] == CycleStatus.DRAFT


def test_마감일이_시작일보다_빠르면_400이다(admin_client):
    res = admin_client.post(
        URL,
        {'name': '잘못된 회차', 'year': 2026, 'starts_on': '2026-09-30', 'ends_on': '2026-09-01'},
        format='json',
    )
    assert res.status_code == 400


def test_반영비율_합이_100이_아니면_400이다(admin_client):
    res = admin_client.post(
        URL,
        {
            'name': '비율오류',
            'year': 2026,
            'starts_on': '2026-09-01',
            'ends_on': '2026-09-30',
            'primary_weight': '60.00',
            'secondary_weight': '30.00',
        },
        format='json',
    )
    assert res.status_code == 400


def test_기본_가감_파라미터가_스펙_기본값이다(admin_client, cycle):
    res = admin_client.get(f'{URL}{cycle.id}/')

    assert res.data['primary_weight'] == '70.00'
    assert res.data['secondary_weight'] == '30.00'
    assert res.data['dept_baseline_score'] == '70.00'
    assert res.data['dept_adjust_factor'] == '0.20'
    assert res.data['dept_adjust_limit'] == '10.00'


# ── 가중치 검증 ──────────────────────────────────────────────


def test_가중치_합계를_조회한다(admin_client, cycle, full_items):
    res = admin_client.get(f'{URL}{cycle.id}/weight-check/')

    assert res.data['EMPLOYEE']['sum'] == '100.00'
    assert res.data['EMPLOYEE']['valid'] is True
    assert res.data['DEPARTMENT']['item_count'] == 0


def test_비활성_항목은_가중치_합계에서_제외된다(admin_client, cycle, full_items):
    full_items[0].is_active = False
    full_items[0].save()

    res = admin_client.get(f'{URL}{cycle.id}/weight-check/')

    assert res.data['EMPLOYEE']['sum'] == '50.00'
    assert res.data['EMPLOYEE']['valid'] is False


# ── OPEN 전이 ────────────────────────────────────────────────


def test_가중치_합계가_100이_아니면_OPEN이_거부된다(admin_client, cycle):
    """완료 조건: 가중치 합계가 100이 아니면 OPEN 전이가 거부된다."""
    make_items(cycle, weights=(50, 30))  # 합계 80

    res = admin_client.post(f'{URL}{cycle.id}/open/?confirm=true')

    assert res.status_code == 400
    assert res.data['code'] == 'WEIGHT_SUM_INVALID'
    assert res.data['invalid']['EMPLOYEE']['sum'] == '80.00'

    cycle.refresh_from_db()
    assert cycle.status == CycleStatus.DRAFT


def test_항목이_없으면_OPEN이_거부된다(admin_client, cycle):
    res = admin_client.post(f'{URL}{cycle.id}/open/?confirm=true')

    assert res.status_code == 400
    assert res.data['code'] == 'NO_ACTIVE_ITEMS'


def test_부서_항목_합계가_100이_아니면_OPEN이_거부된다(admin_client, cycle, full_items):
    make_items(cycle, target_type=TargetType.DEPARTMENT, weights=(60, 30))  # 합계 90

    res = admin_client.post(f'{URL}{cycle.id}/open/?confirm=true')

    assert res.status_code == 400
    assert 'DEPARTMENT' in res.data['invalid']


def test_부서_항목이_아예_없으면_OPEN이_허용된다(admin_client, cycle, full_items):
    """부서 평가는 선택이므로 항목이 0개면 검증 대상이 아니다."""
    res = admin_client.post(f'{URL}{cycle.id}/open/?confirm=true')

    assert res.status_code == 200
    cycle.refresh_from_db()
    assert cycle.status == CycleStatus.OPEN


def test_미배정_대상이_있으면_확인을_요구한다(admin_client, cycle, full_items, member):
    res = admin_client.post(f'{URL}{cycle.id}/open/')

    assert res.status_code == 409
    assert res.data['code'] == 'UNASSIGNED_TARGETS'
    assert len(res.data['unassigned']['employees']) >= 1

    cycle.refresh_from_db()
    assert cycle.status == CycleStatus.DRAFT


def test_confirm하면_미배정이_있어도_OPEN된다(admin_client, cycle, full_items, member):
    res = admin_client.post(f'{URL}{cycle.id}/open/?confirm=true')

    assert res.status_code == 200
    cycle.refresh_from_db()
    assert cycle.status == CycleStatus.OPEN


def test_이미_OPEN인_회차는_다시_열_수_없다(admin_client, cycle, full_items):
    admin_client.post(f'{URL}{cycle.id}/open/?confirm=true')

    res = admin_client.post(f'{URL}{cycle.id}/open/?confirm=true')

    assert res.status_code == 409
    assert res.data['code'] == 'ALREADY_OPEN'


# ── CLOSE / REOPEN ───────────────────────────────────────────


def test_DRAFT_회차는_마감할_수_없다(admin_client, cycle):
    res = admin_client.post(f'{URL}{cycle.id}/close/')

    assert res.status_code == 409
    assert res.data['code'] == 'CYCLE_NOT_OPEN'


def test_OPEN_회차를_마감한다(admin_client, cycle, full_items):
    admin_client.post(f'{URL}{cycle.id}/open/?confirm=true')

    res = admin_client.post(f'{URL}{cycle.id}/close/')

    assert res.status_code == 200
    cycle.refresh_from_db()
    assert cycle.status == CycleStatus.CLOSED


def test_마감된_회차는_다시_열_수_없다(admin_client, cycle, full_items):
    admin_client.post(f'{URL}{cycle.id}/open/?confirm=true')
    admin_client.post(f'{URL}{cycle.id}/close/')

    res = admin_client.post(f'{URL}{cycle.id}/open/?confirm=true')

    assert res.status_code == 409
    assert res.data['code'] == 'CYCLE_CLOSED'


def test_reopen으로_마감을_되돌린다(admin_client, cycle, full_items):
    admin_client.post(f'{URL}{cycle.id}/open/?confirm=true')
    admin_client.post(f'{URL}{cycle.id}/close/')

    res = admin_client.post(f'{URL}{cycle.id}/reopen/')

    assert res.status_code == 200
    cycle.refresh_from_db()
    assert cycle.status == CycleStatus.OPEN


def test_마감된_회차는_수정할_수_없다(admin_client, cycle, full_items):
    admin_client.post(f'{URL}{cycle.id}/open/?confirm=true')
    admin_client.post(f'{URL}{cycle.id}/close/')

    res = admin_client.patch(f'{URL}{cycle.id}/', {'name': '변경'}, format='json')

    assert res.status_code == 400


# ── 삭제 / 복제 ──────────────────────────────────────────────


def test_항목이_있는_회차는_삭제할_수_없다(admin_client, cycle, full_items):
    res = admin_client.delete(f'{URL}{cycle.id}/')

    assert res.status_code == 409
    assert res.data['code'] == 'CYCLE_IN_USE'


def test_빈_회차는_삭제된다(admin_client, cycle):
    res = admin_client.delete(f'{URL}{cycle.id}/')
    assert res.status_code == 204


def test_다른_회차의_항목을_복제한다(admin_client, cycle, full_items):
    from apps.evaluations.models import EvaluationCycle

    target = EvaluationCycle.objects.create(
        name='2026년 하반기 평가', year=2026, starts_on='2027-01-01', ends_on='2027-01-31'
    )

    res = admin_client.post(
        f'{URL}{target.id}/clone-items/', {'source_cycle': cycle.id}, format='json'
    )

    assert res.status_code == 200
    assert res.data['created'] == 3
    assert target.items.count() == 3
    assert sum(i.weight for i in target.items.all()) == 100


def test_같은_코드는_복제되지_않는다(admin_client, cycle, full_items):
    from apps.evaluations.models import EvaluationCycle

    target = EvaluationCycle.objects.create(
        name='하반기', year=2026, starts_on='2027-01-01', ends_on='2027-01-31'
    )
    EvaluationItem.objects.create(
        cycle=target, target_type=TargetType.EMPLOYEE, code='EMP1', title='기존', weight=100
    )

    res = admin_client.post(
        f'{URL}{target.id}/clone-items/', {'source_cycle': cycle.id}, format='json'
    )

    assert res.data['created'] == 2
    assert len(res.data['skipped']) == 1


def test_미배정_목록을_조회한다(admin_client, cycle, member, dept, manager):
    EvaluatorAssignment.objects.create(
        cycle=cycle,
        target_type=TargetType.EMPLOYEE,
        target_user=member,
        primary_evaluator=manager,
    )

    res = admin_client.get(f'{URL}{cycle.id}/unassigned/')

    assigned_names = [e['name'] for e in res.data['employees']]
    assert '김철수' not in assigned_names
    assert '박팀장' in assigned_names
    assert res.data['department_count'] == 1


def test_가중치_오류_응답의_item_count는_숫자다(admin_client, cycle):
    """DomainError.context는 DRF의 ErrorDetail 래핑을 거치지 않아 자료형이 보존된다."""
    make_items(cycle, weights=(50, 30))

    res = admin_client.post(f'{URL}{cycle.id}/open/?confirm=true')

    invalid = res.data['invalid']['EMPLOYEE']
    assert invalid['item_count'] == 2
    assert isinstance(invalid['item_count'], int)


def test_미배정_응답의_구조가_유지된다(admin_client, cycle, full_items, member):
    res = admin_client.post(f'{URL}{cycle.id}/open/')

    employees = res.data['unassigned']['employees']
    assert isinstance(employees, list)
    assert isinstance(employees[0], dict)
    assert isinstance(employees[0]['id'], int)
