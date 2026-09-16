"""점수 계산 테스트.

specs/06-scoring.md §9의 12개 필수 케이스를 모두 포함한다.
scoring.py는 커버리지 100%를 유지해야 한다 (CLAUDE.md).
"""

from decimal import Decimal

import pytest

from apps.accounts.models import Department, User
from apps.evaluations.models import (
    CycleStatus,
    EvaluationAnswer,
    EvaluationCycle,
    EvaluationItem,
    EvaluationResponse,
    EvaluatorAssignment,
    ResponseStatus,
    TargetType,
)
from apps.reports.models import ScoreResult
from apps.reports.services import scoring

pytestmark = pytest.mark.django_db

D = Decimal


# ── 픽스처 ───────────────────────────────────────────────────


@pytest.fixture
def cycle(db):
    return EvaluationCycle.objects.create(
        name='산출 회차',
        year=2026,
        starts_on='2026-01-01',
        ends_on='2099-12-31',
        status=CycleStatus.OPEN,
    )


@pytest.fixture
def dept(db):
    return Department.objects.create(code='DEV1', name='개발1팀')


@pytest.fixture
def emp_items(cycle):
    """가중치 50 / 30 / 20, 5점 척도."""
    return [
        EvaluationItem.objects.create(
            cycle=cycle,
            target_type=TargetType.EMPLOYEE,
            code=f'E{i}',
            title=f'개인{i}',
            weight=w,
            max_score=5,
            order=i,
        )
        for i, w in enumerate((50, 30, 20), start=1)
    ]


@pytest.fixture
def dept_items(cycle):
    return [
        EvaluationItem.objects.create(
            cycle=cycle,
            target_type=TargetType.DEPARTMENT,
            code=f'D{i}',
            title=f'부서{i}',
            weight=w,
            max_score=5,
            order=i,
        )
        for i, w in enumerate((60, 40), start=1)
    ]


@pytest.fixture
def people(db, dept):
    return {
        'manager': User.objects.create_user(
            employee_no='M001', name='박팀장', password='pass123456!', department=dept
        ),
        'director': User.objects.create_user(
            employee_no='D001', name='최본부장', password='pass123456!'
        ),
        'member': User.objects.create_user(
            employee_no='T001', name='김철수', password='pass123456!', department=dept
        ),
    }


def make_assignment(cycle, target, primary, secondary=None):
    return EvaluatorAssignment.objects.create(
        cycle=cycle,
        target_type=TargetType.EMPLOYEE,
        target_user=target,
        primary_evaluator=primary,
        secondary_evaluator=secondary,
    )


def submit_sheet(assignment, evaluator, round_value, items, scores):
    """항목별 점수로 평가지를 만들고 제출 상태로 둔다."""
    response = EvaluationResponse.objects.create(
        assignment=assignment,
        evaluator=evaluator,
        round=round_value,
        status=ResponseStatus.SUBMITTED,
    )
    for item, score in zip(items, scores, strict=True):
        EvaluationAnswer.objects.create(response=response, item=item, score=score)
    return response


# ══ 케이스 1: 평가지 환산 점수 ═══════════════════════════════


def test_케이스1_3개_항목_가중_평균(cycle, emp_items, people):
    """(80×50 + 100×30 + 60×20) / 100 = 82.00"""
    assignment = make_assignment(cycle, people['member'], people['manager'])
    response = submit_sheet(assignment, people['manager'], 'PRIMARY', emp_items, [4, 5, 3])

    assert scoring.sheet_score(response.answers.all()) == D('82.00')


def test_환산_점수는_척도를_반영한다(cycle, people):
    """10점 척도에서 7점은 70%다."""
    item = EvaluationItem.objects.create(
        cycle=cycle,
        target_type=TargetType.EMPLOYEE,
        code='X',
        title='10점척도',
        weight=100,
        max_score=10,
    )
    assignment = make_assignment(cycle, people['member'], people['manager'])
    response = submit_sheet(assignment, people['manager'], 'PRIMARY', [item], [7])

    assert scoring.sheet_score(response.answers.all()) == D('70.00')


def test_비활성_항목은_환산에서_제외된다(cycle, emp_items, people):
    """항목이 사후 비활성화되면 남은 항목의 가중치로 정규화된다."""
    assignment = make_assignment(cycle, people['member'], people['manager'])
    response = submit_sheet(assignment, people['manager'], 'PRIMARY', emp_items, [4, 5, 3])

    emp_items[2].is_active = False
    emp_items[2].save()
    response.refresh_from_db()

    # (80×50 + 100×30) / 80 = 7000/80 = 87.50
    assert scoring.sheet_score(response.answers.all()) == D('87.50')


def test_점수가_없는_답변은_제외된다(cycle, emp_items, people):
    assignment = make_assignment(cycle, people['member'], people['manager'])
    response = EvaluationResponse.objects.create(
        assignment=assignment, evaluator=people['manager'], round='PRIMARY'
    )
    EvaluationAnswer.objects.create(response=response, item=emp_items[0], score=4)
    EvaluationAnswer.objects.create(response=response, item=emp_items[1], score=None)

    # 80×50 / 50 = 80.00
    assert scoring.sheet_score(response.answers.all()) == D('80.00')


def test_가중치_합이_0이면_None이다(cycle, emp_items, people):
    """ZERO_WEIGHT_SUM의 근거. 답변이 하나도 채워지지 않은 상태."""
    assignment = make_assignment(cycle, people['member'], people['manager'])
    response = EvaluationResponse.objects.create(
        assignment=assignment, evaluator=people['manager'], round='PRIMARY'
    )
    EvaluationAnswer.objects.create(response=response, item=emp_items[0], score=None)

    assert scoring.sheet_score(response.answers.all()) is None


# ══ 케이스 2·3·4: 개인 평가 점수 ═════════════════════════════


def test_케이스2_2차_평가자_없으면_1차_100퍼센트(cycle, emp_items, people):
    assignment = make_assignment(cycle, people['member'], people['manager'])
    submit_sheet(assignment, people['manager'], 'PRIMARY', emp_items, [4, 5, 3])

    scoring.calculate_cycle(cycle)

    score = ScoreResult.objects.get(cycle=cycle, user=people['member'])
    assert score.primary_score == D('82.00')
    assert score.secondary_score is None
    assert score.individual_score == D('82.00')


def test_케이스3_2차_지정되었으나_미제출이면_1차_100퍼센트(cycle, emp_items, people):
    """미제출을 0점으로 처리하지 않아야 피평가자가 불이익을 받지 않는다."""
    assignment = make_assignment(cycle, people['member'], people['manager'], people['director'])
    submit_sheet(assignment, people['manager'], 'PRIMARY', emp_items, [4, 5, 3])

    scoring.calculate_cycle(cycle)

    score = ScoreResult.objects.get(cycle=cycle, user=people['member'])
    assert score.secondary_score is None
    assert score.individual_score == D('82.00')


def test_2차가_임시저장이면_반영되지_않는다(cycle, emp_items, people):
    assignment = make_assignment(cycle, people['member'], people['manager'], people['director'])
    submit_sheet(assignment, people['manager'], 'PRIMARY', emp_items, [4, 5, 3])

    draft = EvaluationResponse.objects.create(
        assignment=assignment, evaluator=people['director'], round='SECONDARY'
    )
    for item in emp_items:
        EvaluationAnswer.objects.create(response=draft, item=item, score=5)

    scoring.calculate_cycle(cycle)

    score = ScoreResult.objects.get(cycle=cycle, user=people['member'])
    assert score.individual_score == D('82.00')


def test_케이스4_1차와_2차를_70대30으로_결합한다(cycle, emp_items, people):
    """82.00 × 0.70 + 90.00 × 0.30 = 57.40 + 27.00 = 84.40"""
    assignment = make_assignment(cycle, people['member'], people['manager'], people['director'])
    submit_sheet(assignment, people['manager'], 'PRIMARY', emp_items, [4, 5, 3])
    submit_sheet(assignment, people['director'], 'SECONDARY', emp_items, [4, 5, 5])

    scoring.calculate_cycle(cycle)

    score = ScoreResult.objects.get(cycle=cycle, user=people['member'])
    assert score.primary_score == D('82.00')
    assert score.secondary_score == D('90.00')
    assert score.individual_score == D('84.40')


def test_반영_비율을_바꾸면_결합_결과가_바뀐다(cycle, emp_items, people):
    cycle.primary_weight = D('50.00')
    cycle.secondary_weight = D('50.00')
    cycle.save()

    assignment = make_assignment(cycle, people['member'], people['manager'], people['director'])
    submit_sheet(assignment, people['manager'], 'PRIMARY', emp_items, [4, 5, 3])
    submit_sheet(assignment, people['director'], 'SECONDARY', emp_items, [4, 5, 5])

    scoring.calculate_cycle(cycle)

    # (82 + 90) / 2 = 86.00
    assert ScoreResult.objects.get(cycle=cycle).individual_score == D('86.00')


# ══ 케이스 5·6·7: 부서 가감 ══════════════════════════════════


@pytest.mark.parametrize(
    ('dept_score', 'expected'),
    [
        (D('90.00'), D('4.00')),  # 케이스 5
        (D('70.00'), D('0.00')),
        (D('45.00'), D('-5.00')),
        (D('100.00'), D('6.00')),
        (D('0.00'), D('-10.00')),  # 케이스 6: 하한 적용
    ],
)
def test_케이스5_6_부서_가감_계산(cycle, dept_score, expected):
    """adjustment = clamp((부서점수 - 70) × 0.2, -10, +10)"""
    assert scoring.department_adjustment(dept_score, cycle) == expected


def test_케이스7_부서_평가지_미제출이면_가감이_0이다(cycle, emp_items, dept_items, people, dept):
    """부서 평가자가 배정되어 있어도 미제출이면 가감이 없다."""
    EvaluatorAssignment.objects.create(
        cycle=cycle,
        target_type=TargetType.DEPARTMENT,
        target_department=dept,
        primary_evaluator=people['director'],
    )
    assignment = make_assignment(cycle, people['member'], people['manager'])
    submit_sheet(assignment, people['manager'], 'PRIMARY', emp_items, [4, 5, 3])

    scoring.calculate_cycle(cycle)

    score = ScoreResult.objects.get(cycle=cycle, user=people['member'])
    assert score.department_score is None
    assert score.department_adjustment == D('0.00')
    assert score.final_score == D('82.00')


def test_부서_점수가_최종_점수에_반영된다(cycle, emp_items, dept_items, people, dept):
    """부서 항목 5/5, 5/5 → 100.00 → 가감 (100-70)×0.2 = +6.00"""
    dept_assignment = EvaluatorAssignment.objects.create(
        cycle=cycle,
        target_type=TargetType.DEPARTMENT,
        target_department=dept,
        primary_evaluator=people['director'],
    )
    submit_sheet(dept_assignment, people['director'], 'PRIMARY', dept_items, [5, 5])

    assignment = make_assignment(cycle, people['member'], people['manager'])
    submit_sheet(assignment, people['manager'], 'PRIMARY', emp_items, [4, 5, 3])

    scoring.calculate_cycle(cycle)

    score = ScoreResult.objects.get(cycle=cycle, user=people['member'])
    assert score.department_score == D('100.00')
    assert score.department_adjustment == D('6.00')
    assert score.final_score == D('88.00')


def test_부서_평가도_1차_2차를_결합한다(cycle, emp_items, dept_items, people, dept):
    """부서 1차 100.00, 2차 60.00 → 100×0.7 + 60×0.3 = 88.00"""
    dept_assignment = EvaluatorAssignment.objects.create(
        cycle=cycle,
        target_type=TargetType.DEPARTMENT,
        target_department=dept,
        primary_evaluator=people['director'],
        secondary_evaluator=people['manager'],
    )
    submit_sheet(dept_assignment, people['director'], 'PRIMARY', dept_items, [5, 5])
    submit_sheet(dept_assignment, people['manager'], 'SECONDARY', dept_items, [3, 3])

    assignment = make_assignment(cycle, people['member'], people['manager'])
    submit_sheet(assignment, people['manager'], 'PRIMARY', emp_items, [4, 5, 3])

    scoring.calculate_cycle(cycle)

    score = ScoreResult.objects.get(cycle=cycle, user=people['member'])
    assert score.department_score == D('88.00')
    assert score.department_adjustment == D('3.60')


# ══ 케이스 8·9: 상·하한 ══════════════════════════════════════


def test_케이스8_개인_98에_가감_4면_100이_상한이다(cycle):
    assert scoring.final_score(D('98.00'), D('4.00')) == D('100.00')


def test_케이스9_개인_3에_가감_마이너스5면_0이_하한이다(cycle):
    assert scoring.final_score(D('3.00'), D('-5.00')) == D('0.00')


def test_상한이_DB_제약과_일치한다(cycle, emp_items, dept_items, people, dept):
    """최종 점수가 100을 넘는 레코드는 DB CheckConstraint로도 막힌다."""
    dept_assignment = EvaluatorAssignment.objects.create(
        cycle=cycle,
        target_type=TargetType.DEPARTMENT,
        target_department=dept,
        primary_evaluator=people['director'],
    )
    submit_sheet(dept_assignment, people['director'], 'PRIMARY', dept_items, [5, 5])

    assignment = make_assignment(cycle, people['member'], people['manager'])
    submit_sheet(assignment, people['manager'], 'PRIMARY', emp_items, [5, 5, 5])

    scoring.calculate_cycle(cycle)

    score = ScoreResult.objects.get(cycle=cycle, user=people['member'])
    # 개인 100.00 + 가감 6.00 → 상한 100.00
    assert score.individual_score == D('100.00')
    assert score.final_score == D('100.00')


# ══ 케이스 10: 미제출 제외 ═══════════════════════════════════


def test_케이스10_1차_미제출은_산출에서_제외된다(cycle, emp_items, people):
    make_assignment(cycle, people['member'], people['manager'])

    result = scoring.calculate_cycle(cycle)

    assert result.total_targets == 1
    assert result.calculated == 0
    assert result.skipped == 1
    assert result.skipped_reasons[0]['reason'] == scoring.PRIMARY_NOT_SUBMITTED
    assert result.skipped_reasons[0]['employee_no'] == 'T001'
    assert not ScoreResult.objects.filter(cycle=cycle).exists()


def test_활성_항목이_없으면_제외된다(cycle, people):
    make_assignment(cycle, people['member'], people['manager'])

    result = scoring.calculate_cycle(cycle)

    assert result.skipped_reasons[0]['reason'] == scoring.NO_ACTIVE_ITEMS


def test_제출했지만_환산이_불가능하면_ZERO_WEIGHT_SUM이다(cycle, emp_items, people):
    """제출 후 모든 항목이 비활성화된 예외 상황."""
    assignment = make_assignment(cycle, people['member'], people['manager'])
    submit_sheet(assignment, people['manager'], 'PRIMARY', emp_items, [4, 5, 3])

    # 개인 항목을 하나 남기고 비활성화하면 활성 항목 수는 유지되지만
    # 제출된 평가지의 답변은 모두 비활성 항목을 가리키게 만든다
    extra = EvaluationItem.objects.create(
        cycle=cycle,
        target_type=TargetType.EMPLOYEE,
        code='E9',
        title='나중항목',
        weight=100,
        max_score=5,
    )
    for item in emp_items:
        item.is_active = False
        item.save()

    result = scoring.calculate_cycle(cycle)

    assert extra.is_active is True
    assert result.skipped_reasons[0]['reason'] == scoring.ZERO_WEIGHT_SUM


# ══ 케이스 11: 멱등성 ════════════════════════════════════════


def test_케이스11_두_번_산출해도_결과가_같고_중복되지_않는다(cycle, emp_items, people):
    assignment = make_assignment(cycle, people['member'], people['manager'])
    submit_sheet(assignment, people['manager'], 'PRIMARY', emp_items, [4, 5, 3])

    first = scoring.calculate_cycle(cycle)
    snapshot = ScoreResult.objects.get(cycle=cycle, user=people['member'])
    values = (
        snapshot.primary_score,
        snapshot.individual_score,
        snapshot.department_adjustment,
        snapshot.final_score,
    )

    second = scoring.calculate_cycle(cycle)
    third = scoring.calculate_cycle(cycle)

    assert ScoreResult.objects.filter(cycle=cycle).count() == 1
    assert first.calculated == second.calculated == third.calculated == 1

    again = ScoreResult.objects.get(cycle=cycle, user=people['member'])
    assert (
        again.primary_score,
        again.individual_score,
        again.department_adjustment,
        again.final_score,
    ) == values


def test_재산출에서_제외된_대상의_이전_결과는_삭제된다(cycle, emp_items, people):
    """반려 등으로 산출 대상에서 빠지면 화면·CSV와 어긋나지 않게 정리한다."""
    assignment = make_assignment(cycle, people['member'], people['manager'])
    response = submit_sheet(assignment, people['manager'], 'PRIMARY', emp_items, [4, 5, 3])

    scoring.calculate_cycle(cycle)
    assert ScoreResult.objects.filter(cycle=cycle).count() == 1

    response.status = ResponseStatus.DRAFT
    response.submitted_at = None
    response.save()

    result = scoring.calculate_cycle(cycle)

    assert result.calculated == 0
    assert not ScoreResult.objects.filter(cycle=cycle).exists()


# ══ 케이스 12: 상위 부서 점수 상속 ═══════════════════════════


def test_케이스12_자기_부서에_점수가_없으면_상위_부서를_상속한다(
    cycle, emp_items, dept_items, people
):
    hq = Department.objects.create(code='HQ', name='본사')
    div = Department.objects.create(code='DIV', name='개발본부', parent=hq)
    team = Department.objects.create(code='TEAM', name='개발1팀', parent=div)

    member = User.objects.create_user(
        employee_no='T900', name='말단직원', password='pass123456!', department=team
    )

    # 본사만 평가됨 → 개발1팀은 본사 점수를 상속해야 한다
    hq_assignment = EvaluatorAssignment.objects.create(
        cycle=cycle,
        target_type=TargetType.DEPARTMENT,
        target_department=hq,
        primary_evaluator=people['director'],
    )
    submit_sheet(hq_assignment, people['director'], 'PRIMARY', dept_items, [4, 4])

    assignment = make_assignment(cycle, member, people['manager'])
    submit_sheet(assignment, people['manager'], 'PRIMARY', emp_items, [4, 5, 3])

    scoring.calculate_cycle(cycle)

    score = ScoreResult.objects.get(cycle=cycle, user=member)
    assert score.department_score == D('80.00')  # 4/5 → 80%
    assert score.department_adjustment == D('2.00')  # (80-70)×0.2


def test_가장_가까운_상위_부서가_우선한다(cycle, emp_items, dept_items, people):
    hq = Department.objects.create(code='HQ', name='본사')
    div = Department.objects.create(code='DIV', name='개발본부', parent=hq)
    team = Department.objects.create(code='TEAM', name='개발1팀', parent=div)

    member = User.objects.create_user(
        employee_no='T901', name='직원', password='pass123456!', department=team
    )

    for department, scores in [(hq, [2, 2]), (div, [5, 5])]:
        a = EvaluatorAssignment.objects.create(
            cycle=cycle,
            target_type=TargetType.DEPARTMENT,
            target_department=department,
            primary_evaluator=people['director'],
        )
        submit_sheet(a, people['director'], 'PRIMARY', dept_items, scores)

    assignment = make_assignment(cycle, member, people['manager'])
    submit_sheet(assignment, people['manager'], 'PRIMARY', emp_items, [4, 5, 3])

    scoring.calculate_cycle(cycle)

    # 개발본부(100.00)가 본사(40.00)보다 가깝다
    assert ScoreResult.objects.get(cycle=cycle, user=member).department_score == D('100.00')


def test_부서가_없는_직원은_가감이_0이다(cycle, emp_items, people):
    member = User.objects.create_user(employee_no='T902', name='무소속', password='pass123456!')
    assignment = make_assignment(cycle, member, people['manager'])
    submit_sheet(assignment, people['manager'], 'PRIMARY', emp_items, [4, 5, 3])

    scoring.calculate_cycle(cycle)

    score = ScoreResult.objects.get(cycle=cycle, user=member)
    assert score.department_score is None
    assert score.department_adjustment == D('0.00')


def test_부서_트리가_순환해도_무한_루프에_빠지지_않는다(cycle):
    """clean()이 막지만 데이터가 직접 조작된 경우에도 방어한다."""
    scores = {}
    parent_map = {1: 2, 2: 1}

    assert scoring.resolve_department_score(1, scores, parent_map) is None


# ══ 반올림 ═══════════════════════════════════════════════════


def test_ROUND_HALF_UP으로_반올림한다():
    assert scoring.q2(D('82.005')) == D('82.01')
    assert scoring.q2(D('82.004')) == D('82.00')
    assert scoring.q2(D('-3.005')) == D('-3.01')


def test_q2는_None을_통과시킨다():
    assert scoring.q2(None) is None


def test_float를_쓰지_않는다(cycle, emp_items, people):
    """모든 점수 필드가 Decimal이어야 한다."""
    assignment = make_assignment(cycle, people['member'], people['manager'])
    submit_sheet(assignment, people['manager'], 'PRIMARY', emp_items, [4, 5, 3])

    scoring.calculate_cycle(cycle)

    score = ScoreResult.objects.get(cycle=cycle)
    for value in (
        score.primary_score,
        score.individual_score,
        score.department_adjustment,
        score.final_score,
    ):
        assert isinstance(value, Decimal)


def test_combine_rounds는_1차가_없으면_None이다(cycle):
    assert scoring.combine_rounds(None, D('90.00'), cycle) is None
