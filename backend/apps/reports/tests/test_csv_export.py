"""CSV 내보내기 테스트 (specs/05-admin-features.md FR-A-07)."""

import csv
import io

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def url(cycle, kind):
    return f'/api/admin/cycles/{cycle.id}/export/{kind}.csv'


def read_csv(response):
    """스트리밍 응답을 디코딩해 (헤더, 행들)로 돌려준다."""
    raw = b''.join(response.streaming_content).decode('utf-8-sig')
    rows = list(csv.reader(io.StringIO(raw)))
    return rows[0], rows[1:]


def raw_bytes(response):
    return b''.join(response.streaming_content)


# ── 권한 / 공통 규칙 ─────────────────────────────────────────


def test_직원은_다운로드할_수_없다(manager_client, scenario):
    assert manager_client.get(url(scenario['cycle'], 'scores')).status_code == 403


def test_비인증이면_401이다(scenario):
    assert APIClient().get(url(scenario['cycle'], 'scores')).status_code == 401


def test_지원하지_않는_종류는_404다(admin_client, scenario):
    assert admin_client.get(url(scenario['cycle'], 'unknown')).status_code == 404


@pytest.mark.parametrize('kind', ['scores', 'responses', 'pending'])
def test_BOM으로_시작한다(admin_client, scenario, kind):
    """수용 기준: Excel에서 열었을 때 한글이 정상 표시된다.

    BOM이 없으면 Excel이 CP949로 해석해 한글이 깨진다.
    """
    res = admin_client.get(url(scenario['cycle'], kind))

    assert res.status_code == 200
    assert raw_bytes(res).startswith(b'\xef\xbb\xbf')


@pytest.mark.parametrize('kind', ['scores', 'responses', 'pending'])
def test_콘텐츠_타입과_파일명_헤더(admin_client, scenario, kind):
    res = admin_client.get(url(scenario['cycle'], kind))

    assert res['Content-Type'] == 'text/csv; charset=utf-8'
    assert res['Content-Disposition'].startswith("attachment; filename*=UTF-8''")
    # 한글 회차명이 퍼센트 인코딩되어야 한다
    assert '%' in res['Content-Disposition']


@pytest.mark.parametrize('kind', ['scores', 'responses', 'pending'])
def test_줄바꿈은_CRLF다(admin_client, scenario, kind):
    res = admin_client.get(url(scenario['cycle'], kind))

    body = raw_bytes(res)
    assert b'\r\n' in body


@pytest.mark.parametrize('kind', ['scores', 'responses', 'pending'])
def test_한글_헤더가_깨지지_않는다(admin_client, scenario, kind):
    res = admin_client.get(url(scenario['cycle'], kind))
    header, _ = read_csv(res)

    joined = ','.join(header)
    assert '사번' in joined or '평가자 사번' in joined


def test_성명에_쉼표가_있어도_컬럼이_밀리지_않는다(admin_client, scenario):
    """수용 기준: 성명에 쉼표가 포함되어도 컬럼이 밀리지 않는다."""
    member = scenario['member1']
    member.name = '김,철수'
    member.position = '선임, 파트리드'
    member.save()

    res = admin_client.get(url(scenario['cycle'], 'scores'))
    header, rows = read_csv(res)

    target = next(r for r in rows if r[1] == member.employee_no)
    assert len(target) == len(header)
    assert target[2] == '김,철수'
    assert target[5] == '선임, 파트리드'


def test_따옴표와_줄바꿈이_있어도_안전하다(admin_client, scenario):
    response = scenario['submitted_response']
    response.overall_comment = '그는 "우수"하다.\n다음 줄'
    response.save()

    res = admin_client.get(url(scenario['cycle'], 'responses'))
    header, rows = read_csv(res)

    assert all(len(row) == len(header) for row in rows)
    assert any('우수' in (row[-1] or '') for row in rows)


# ── 7-1. 점수 결과 ───────────────────────────────────────────


def test_점수_CSV_헤더가_스펙과_일치한다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle'], 'scores'))
    header, _ = read_csv(res)

    assert header[:6] == ['회차', '사번', '성명', '부서코드', '부서명', '직위']
    assert '최종 점수' in header
    assert header[-1] == '비고'


def test_산출된_점수가_담긴다(admin_client, scenario):
    admin_client.post(f"/api/admin/cycles/{scenario['cycle'].id}/calculate/")

    res = admin_client.get(url(scenario['cycle'], 'scores'))
    header, rows = read_csv(res)

    row = next(r for r in rows if r[2] == '김철수')
    assert row[header.index('1차 점수')] == '80.00'
    assert row[header.index('개인 평가 점수')] == '80.00'
    assert row[header.index('최종 점수')] == '80.00'
    assert row[header.index('비고')] == ''


def test_미산출자는_점수가_비고_사유와_함께_비어있다(admin_client, scenario):
    """수용 기준: 미산출자는 점수 컬럼이 비어 있고 비고에 사유가 표시된다."""
    admin_client.post(f"/api/admin/cycles/{scenario['cycle'].id}/calculate/")

    res = admin_client.get(url(scenario['cycle'], 'scores'))
    header, rows = read_csv(res)

    # 이영희는 1차가 임시저장이라 산출되지 않는다
    row = next(r for r in rows if r[2] == '이영희')
    assert row[header.index('최종 점수')] == ''
    assert row[header.index('개인 평가 점수')] == ''
    assert row[header.index('비고')] == '1차 평가 미제출'


def test_산출_전에도_전체_대상이_행으로_나온다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle'], 'scores'))
    _, rows = read_csv(res)

    # 개인 배정 3건
    assert len(rows) == 3
    assert all(row[-1] != '' for row in rows)


def test_평가자_이름이_담긴다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle'], 'scores'))
    header, rows = read_csv(res)

    row = next(r for r in rows if r[2] == '김철수')
    assert row[header.index('1차 평가자')] == '박팀장'
    assert row[header.index('2차 평가자')] == '최본부장'


def test_부서로_필터된다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle'], 'scores'), {'department': scenario['dev'].id})
    _, rows = read_csv(res)

    names = {row[2] for row in rows}
    assert names == {'김철수', '이영희'}


def test_검색으로_필터된다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle'], 'scores'), {'search': '정민수'})
    _, rows = read_csv(res)

    assert len(rows) == 1
    assert rows[0][2] == '정민수'


# ── 7-2. 응답 상세 ───────────────────────────────────────────


def test_응답_CSV에_항목_컬럼이_동적으로_붙는다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle'], 'responses'))
    header, _ = read_csv(res)

    # 개인 항목 E1,E2 + 부서 항목 D1,D2
    for code in ('E1', 'E2', 'D1', 'D2'):
        assert code in header
        assert f'{code}_의견' in header
    assert header[-1] == '종합의견'


def test_항목별_원점수가_담긴다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle'], 'responses'))
    header, rows = read_csv(res)

    row = next(r for r in rows if r[1] == '김철수' and r[4] == '1차')
    assert row[header.index('E1')] == '4'
    assert row[header.index('E2')] == '4'


def test_미시작_건도_행으로_포함된다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle'], 'responses'))
    header, rows = read_csv(res)

    statuses = [row[header.index('상태')] for row in rows]
    assert '미시작' in statuses
    assert len(rows) == 6  # 기대 응답 수


def test_진행률이_퍼센트로_표기된다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle'], 'responses'))
    header, rows = read_csv(res)

    row = next(r for r in rows if r[1] == '이영희')
    assert row[header.index('진행률')] == '50%'


def test_상태로_필터된다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle'], 'responses'), {'status': 'NOT_STARTED'})
    _, rows = read_csv(res)

    assert len(rows) == 2


def test_대상유형으로_필터된다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle'], 'responses'), {'target_type': 'DEPARTMENT'})
    header, rows = read_csv(res)

    assert len(rows) == 2
    assert all(row[header.index('대상유형')] == '부서' for row in rows)


def test_같은_코드가_두_유형에_있으면_접미사로_구분한다(admin_client, scenario):
    from apps.evaluations.models import EvaluationItem, TargetType

    EvaluationItem.objects.create(
        cycle=scenario['cycle'],
        target_type=TargetType.DEPARTMENT,
        code='E1',
        title='중복코드',
        weight=10,
    )

    res = admin_client.get(url(scenario['cycle'], 'responses'))
    header, _ = read_csv(res)

    assert 'E1(개인)' in header
    assert 'E1(부서)' in header


# ── 7-3. 미응답자 ────────────────────────────────────────────


def test_미응답자_CSV는_대상_단위로_펼쳐진다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle'], 'pending'))
    header, rows = read_csv(res)

    assert header[0] == '평가자 사번'
    # 박팀장 2건 + 최본부장 2건
    assert len(rows) == 4

    manager_rows = [r for r in rows if r[1] == '박팀장']
    assert len(manager_rows) == 2
    assert manager_rows[0][3] == '2'  # 미응답 건수


def test_미응답자_CSV가_부서로_필터된다(admin_client, scenario):
    res = admin_client.get(url(scenario['cycle'], 'pending'), {'department': scenario['dev'].id})
    _, rows = read_csv(res)

    assert {row[1] for row in rows} == {'박팀장'}


def test_모두_제출되면_미응답자_CSV는_헤더만_남는다(admin_client, scenario):
    from apps.evaluations.models import EvaluationAnswer, EvaluationResponse, ResponseStatus

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

    res = admin_client.get(url(scenario['cycle'], 'pending'))
    _, rows = read_csv(res)

    assert rows == []
