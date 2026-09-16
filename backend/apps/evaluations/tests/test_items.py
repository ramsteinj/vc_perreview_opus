"""평가 항목 API 테스트 (specs/05-admin-features.md FR-A-04)."""

import pytest

from apps.evaluations.models import EvaluationItem, TargetType

pytestmark = pytest.mark.django_db

URL = '/api/admin/items/'


def test_항목을_생성한다(admin_client, cycle):
    res = admin_client.post(
        URL,
        {
            'cycle': cycle.id,
            'target_type': TargetType.EMPLOYEE,
            'code': 'PERF',
            'title': '업무 성과',
            'weight': '50.00',
            'max_score': 5,
            'order': 1,
        },
        format='json',
    )

    assert res.status_code == 201
    assert res.data['code'] == 'PERF'
    assert res.data['in_use'] is False


def test_항목코드는_소문자로_입력해도_대문자로_저장된다(admin_client, cycle):
    res = admin_client.post(
        URL,
        {
            'cycle': cycle.id,
            'target_type': TargetType.EMPLOYEE,
            'code': 'perf',
            'title': 'x',
            'weight': '10',
        },
        format='json',
    )
    assert res.data['code'] == 'PERF'


def test_같은_회차_같은_유형에_코드가_중복되면_400이다(admin_client, cycle):
    payload = {
        'cycle': cycle.id,
        'target_type': TargetType.EMPLOYEE,
        'code': 'PERF',
        'title': '업무 성과',
        'weight': '50.00',
    }
    admin_client.post(URL, payload, format='json')

    res = admin_client.post(URL, payload, format='json')

    assert res.status_code == 400


def test_대상_유형이_다르면_같은_코드를_쓸_수_있다(admin_client, cycle):
    base = {'cycle': cycle.id, 'code': 'PERF', 'title': '성과', 'weight': '50.00'}
    admin_client.post(URL, {**base, 'target_type': TargetType.EMPLOYEE}, format='json')

    res = admin_client.post(URL, {**base, 'target_type': TargetType.DEPARTMENT}, format='json')

    assert res.status_code == 201


@pytest.mark.parametrize('weight', ['0', '-10', '150'])
def test_가중치_범위를_벗어나면_400이다(admin_client, cycle, weight):
    res = admin_client.post(
        URL,
        {
            'cycle': cycle.id,
            'target_type': TargetType.EMPLOYEE,
            'code': f'W{weight}',
            'title': 'x',
            'weight': weight,
        },
        format='json',
    )
    assert res.status_code == 400


def test_편집_중에는_합계가_100이_아니어도_저장된다(admin_client, cycle):
    """스펙: 편집 중에는 합계가 100이 아니어도 저장 가능하다."""
    res = admin_client.post(
        URL,
        {
            'cycle': cycle.id,
            'target_type': TargetType.EMPLOYEE,
            'code': 'A',
            'title': 'A',
            'weight': '30',
        },
        format='json',
    )
    assert res.status_code == 201


def test_항목을_수정한다(admin_client, cycle, full_items):
    item = full_items[0]

    res = admin_client.patch(f'{URL}{item.id}/', {'title': '변경된 제목'}, format='json')

    assert res.status_code == 200
    item.refresh_from_db()
    assert item.title == '변경된 제목'


def test_항목을_삭제한다(admin_client, cycle, full_items):
    item = full_items[0]

    res = admin_client.delete(f'{URL}{item.id}/')

    assert res.status_code == 204
    assert not EvaluationItem.objects.filter(pk=item.pk).exists()


def test_회차와_유형으로_필터된다(admin_client, cycle, full_items):
    from .conftest import make_items

    make_items(cycle, target_type=TargetType.DEPARTMENT, weights=(100,))

    res = admin_client.get(URL, {'cycle': cycle.id, 'target_type': TargetType.EMPLOYEE})

    assert len(res.data) == 3


def test_순서를_일괄_변경한다(admin_client, cycle, full_items):
    reversed_ids = [item.id for item in reversed(full_items)]

    res = admin_client.post(
        f'{URL}reorder/', {'cycle': cycle.id, 'item_ids': reversed_ids}, format='json'
    )

    assert res.status_code == 200
    assert res.data['updated'] == 3

    ordered = list(
        EvaluationItem.objects.filter(cycle=cycle, target_type=TargetType.EMPLOYEE).order_by(
            'order'
        )
    )
    assert [i.id for i in ordered] == reversed_ids


def test_마감된_회차의_항목은_생성할_수_없다(admin_client, cycle, full_items):
    admin_client.post(f'/api/admin/cycles/{cycle.id}/open/?confirm=true')
    admin_client.post(f'/api/admin/cycles/{cycle.id}/close/')

    res = admin_client.post(
        URL,
        {
            'cycle': cycle.id,
            'target_type': TargetType.EMPLOYEE,
            'code': 'NEW',
            'title': 'x',
            'weight': '10',
        },
        format='json',
    )

    assert res.status_code == 400


def test_항목_목록은_페이지네이션되지_않는다(admin_client, cycle, full_items):
    """편집 화면에서 전체 항목을 한 번에 다뤄야 하므로 배열로 반환한다."""
    res = admin_client.get(URL, {'cycle': cycle.id})

    assert isinstance(res.data, list)
