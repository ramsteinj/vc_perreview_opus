"""응답 현황 상세 테스트 (FR-A-06 6-2)."""

import pytest

pytestmark = pytest.mark.django_db


def url(cycle):
    return f'/api/admin/cycles/{cycle.id}/status/detail/'


def names(res):
    return [(r['evaluator']['name'], r['target']['name'], r['round']) for r in res.data['results']]


def test_모든_기대_응답_행이_나온다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']))

    assert res.status_code == 200
    assert res.data['count'] == 6


def test_미시작_행도_포함된다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']))

    not_started = [r for r in res.data['results'] if r['status'] == 'NOT_STARTED']
    assert len(not_started) == 2
    assert all(r['response_id'] is None for r in not_started)


def test_행에_평가자_부서가_담긴다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']))

    row = next(r for r in res.data['results'] if r['evaluator']['name'] == '박팀장')
    assert row['evaluator']['department_name'] == '개발1팀'
    assert row['evaluator']['employee_no'] == '20180001'


def test_진행률이_계산된다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']))

    draft = next(
        r for r in res.data['results'] if r['target']['name'] == '이영희' and r['status'] == 'DRAFT'
    )
    assert draft['answered_count'] == 1
    assert draft['total_items'] == 2
    assert draft['progress'] == 50

    submitted = next(
        r
        for r in res.data['results']
        if r['target']['name'] == '김철수' and r['round'] == 'PRIMARY'
    )
    assert submitted['progress'] == 100


# ── 필터 ─────────────────────────────────────────────────────


def test_상태로_필터된다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']), {'status': 'NOT_STARTED'})

    assert res.data['count'] == 2
    assert all(r['status'] == 'NOT_STARTED' for r in res.data['results'])


def test_상태를_복수로_지정할_수_있다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']), {'status': 'NOT_STARTED,DRAFT'})

    assert res.data['count'] == 4


def test_차수로_필터된다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']), {'round': 'SECONDARY'})

    assert res.data['count'] == 1
    assert res.data['results'][0]['evaluator']['name'] == '최본부장'


def test_대상_유형으로_필터된다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']), {'target_type': 'DEPARTMENT'})

    assert res.data['count'] == 2
    assert all(r['target_type'] == 'DEPARTMENT' for r in res.data['results'])


def test_부서로_필터된다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']), {'department': scenario['dev'].id})

    assert res.data['count'] == 3
    assert all(r['evaluator']['name'] == '박팀장' for r in res.data['results'])


def test_부서와_상태_필터가_조합된다(admin_client, scenario):
    """수용 기준: 상세 목록에서 부서·상태 필터가 조합해서 동작한다."""
    res = admin_client.get(
        url(scenario['cycle']), {'department': scenario['dev'].id, 'status': 'DRAFT'}
    )

    assert res.data['count'] == 1
    row = res.data['results'][0]
    assert row['evaluator']['name'] == '박팀장'
    assert row['target']['name'] == '이영희'


def test_평가자명으로_검색된다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']), {'search': '최본부장'})

    assert res.data['count'] == 3


def test_평가자_사번으로_검색된다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']), {'search': '20180001'})

    assert res.data['count'] == 3


def test_대상명으로도_검색된다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']), {'search': '김철수'})

    # 1차(박팀장) + 2차(최본부장)
    assert res.data['count'] == 2


def test_조건에_맞는_행이_없으면_빈_결과다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']), {'search': '없는사람'})

    assert res.data['count'] == 0
    assert res.data['results'] == []


# ── 정렬 ─────────────────────────────────────────────────────


def test_기본_정렬은_덜_진행된_것이_먼저다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']))

    statuses = [r['status'] for r in res.data['results']]
    order = {'NOT_STARTED': 0, 'DRAFT': 1, 'SUBMITTED': 2}
    assert statuses == sorted(statuses, key=lambda s: order[s])


def test_진행률로_정렬된다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']), {'ordering': '-progress'})

    progresses = [r['progress'] for r in res.data['results']]
    assert progresses == sorted(progresses, reverse=True)


def test_제출시각으로_정렬된다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']), {'ordering': 'submitted_at'})

    # 미제출(None)이 먼저 온다
    assert res.data['results'][0]['submitted_at'] is None


# ── 페이지네이션 ─────────────────────────────────────────────


def test_페이지네이션이_동작한다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle']), {'page_size': 2})

    assert res.data['count'] == 6
    assert len(res.data['results']) == 2
    assert res.data['next'] is not None


def test_두번째_페이지를_가져온다(admin_client, scenario):
    first = admin_client.get(url(scenario['cycle']), {'page_size': 2, 'page': 1})
    second = admin_client.get(url(scenario['cycle']), {'page_size': 2, 'page': 2})

    assert names(first) != names(second)


def test_상세_쿼리_수가_고정이다(admin_client, scenario, django_assert_num_queries):
    with django_assert_num_queries(5):
        admin_client.get(url(scenario['cycle']))
