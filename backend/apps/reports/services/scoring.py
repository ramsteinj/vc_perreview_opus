"""점수 산출 (specs/06-scoring.md).

모든 계산은 Decimal로 수행한다. float를 사용하지 않는다.
계산식과 예시는 스펙 문서를 기준으로 하며, 이 모듈이 유일한 구현 위치다.
View나 Serializer, 프론트엔드에 계산식을 복제하지 않는다.
"""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Count, Prefetch

from apps.accounts.models import Department
from apps.evaluations.models import (
    EvaluationAnswer,
    EvaluationItem,
    EvaluationResponse,
    EvaluationRound,
    EvaluatorAssignment,
    ResponseStatus,
    TargetType,
)

from ..models import ScoreResult

ZERO = Decimal('0.00')
HUNDRED = Decimal('100.00')

# 산출 제외 사유 (specs/06-scoring.md §8)
PRIMARY_NOT_SUBMITTED = 'PRIMARY_NOT_SUBMITTED'
NO_ASSIGNMENT = 'NO_ASSIGNMENT'
NO_ACTIVE_ITEMS = 'NO_ACTIVE_ITEMS'
ZERO_WEIGHT_SUM = 'ZERO_WEIGHT_SUM'


def q2(value):
    """소수 둘째 자리에서 ROUND_HALF_UP 반올림한다 (specs/06-scoring.md §7)."""
    if value is None:
        return None
    return dec(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def dec(value):
    """계산 입력을 Decimal로 강제한다.

    모델 기본값이나 외부 입력이 float/int로 들어오면 Decimal 연산에서
    TypeError가 나거나 부동소수점 오차가 섞인다. 계산의 단일 진입점인
    이 모듈에서 한 번 막아 둔다 (CLAUDE.md: float를 쓰지 않는다).
    """
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


# ── ① 평가지 환산 점수 ───────────────────────────────────────────
def sheet_score(answers):
    """평가지 한 장을 0~100으로 환산한다 (specs/06-scoring.md §2).

                    Σ ( item_pct(i) × weight(i) )
    sheet_score = ───────────────────────────────
                           Σ weight(i)

    답변이 있고 score가 null이 아닌 활성 항목만 포함한다.
    Σweight가 0이면 계산 불가로 None을 반환한다.
    """
    weighted_total = Decimal('0')
    weight_sum = Decimal('0')

    for answer in answers:
        if answer.score is None:
            continue
        item = answer.item
        if not item.is_active:
            continue

        item_pct = q2(dec(answer.score) * HUNDRED / dec(item.max_score))
        weight = dec(item.weight)
        weighted_total += item_pct * weight
        weight_sum += weight

    if weight_sum == 0:
        return None
    return q2(weighted_total / weight_sum)


# ── ② 개인 평가 점수 / ③ 부서 성과 점수 ─────────────────────────
def combine_rounds(primary, secondary, cycle):
    """1차·2차 환산 점수를 회차 비율로 결합한다 (specs/06-scoring.md §3).

    2차 평가자가 없거나 제출하지 않았으면 1차 점수를 100% 반영한다.
    미제출을 0점으로 처리하지 않아 피평가자가 불이익을 받지 않게 한다.
    """
    if primary is None:
        return None
    if secondary is None:
        return q2(primary)

    return q2(
        dec(primary) * dec(cycle.primary_weight) / HUNDRED
        + dec(secondary) * dec(cycle.secondary_weight) / HUNDRED
    )


# ── ④ 부서 가감값 ───────────────────────────────────────────────
def department_adjustment(department_score, cycle):
    """부서 성과 점수를 개인 점수에 반영할 가감값 (specs/06-scoring.md §5).

    adjustment = clamp((부서점수 - 기준점) × 계수, -한도, +한도)
    부서 점수가 없으면 0이다.
    """
    if department_score is None:
        return ZERO

    baseline = dec(cycle.dept_baseline_score)
    factor = dec(cycle.dept_adjust_factor)
    limit = dec(cycle.dept_adjust_limit)

    raw = (dec(department_score) - baseline) * factor
    return q2(clamp(raw, -limit, limit))


# ── ⑤ 최종 점수 ─────────────────────────────────────────────────
def final_score(individual_score, adjustment):
    """최종 점수 = clamp(개인 점수 + 부서 가감, 0, 100) (specs/06-scoring.md §6)."""
    return q2(clamp(dec(individual_score) + dec(adjustment), ZERO, HUNDRED))


# ── 산출 파이프라인 ─────────────────────────────────────────────
@dataclass
class CalculationResult:
    total_targets: int = 0
    calculated: int = 0
    skipped_reasons: list = field(default_factory=list)

    @property
    def skipped(self):
        return len(self.skipped_reasons)


def _responses_by_assignment(cycle):
    """제출된 평가지를 (배정, 차수)로 색인한다. 답변과 항목까지 함께 읽는다."""
    queryset = EvaluationResponse.objects.filter(
        assignment__cycle=cycle, status=ResponseStatus.SUBMITTED
    ).prefetch_related(
        Prefetch('answers', queryset=EvaluationAnswer.objects.select_related('item'))
    )
    return {(r.assignment_id, r.round): r for r in queryset}


def _score_for_assignment(assignment, responses, cycle):
    """배정 1건의 1차·2차 환산 점수와 결합 점수를 계산한다."""
    primary_response = responses.get((assignment.id, EvaluationRound.PRIMARY))
    secondary_response = responses.get((assignment.id, EvaluationRound.SECONDARY))

    primary = sheet_score(primary_response.answers.all()) if primary_response else None
    secondary = sheet_score(secondary_response.answers.all()) if secondary_response else None

    return primary, secondary, combine_rounds(primary, secondary, cycle)


def department_scores(cycle, responses=None):
    """부서별 성과 점수 맵 {department_id: Decimal|None} (specs/06-scoring.md §4)."""
    responses = responses if responses is not None else _responses_by_assignment(cycle)

    scores = {}
    assignments = EvaluatorAssignment.objects.filter(cycle=cycle, target_type=TargetType.DEPARTMENT)
    for assignment in assignments:
        _, _, combined = _score_for_assignment(assignment, responses, cycle)
        scores[assignment.target_department_id] = combined
    return scores


def resolve_department_score(department_id, scores, parent_map):
    """부서 점수를 찾는다. 자기 부서에 점수가 없으면 상위 부서에서 상속한다.

    specs/06-scoring.md §4: 가장 가까운 상위 부서의 점수를 상속한다.
    """
    seen = set()
    current = department_id
    while current is not None and current not in seen:
        seen.add(current)
        score = scores.get(current)
        if score is not None:
            return score
        current = parent_map.get(current)
    return None


def _department_parent_map():
    return dict(Department.objects.values_list('id', 'parent_id'))


@transaction.atomic
def calculate_cycle(cycle):
    """회차 전체를 재산출한다 (specs/06-scoring.md §8).

    멱등하다. 같은 입력에 몇 번을 실행해도 같은 결과를 내고 레코드가 중복되지 않는다.
    단일 트랜잭션이므로 일부 실패 시 전체가 롤백된다.
    """
    result = CalculationResult()

    active_item_count = EvaluationItem.objects.filter(
        cycle=cycle, target_type=TargetType.EMPLOYEE, is_active=True
    ).count()

    responses = _responses_by_assignment(cycle)
    dept_scores = department_scores(cycle, responses)
    parent_map = _department_parent_map()

    assignments = (
        EvaluatorAssignment.objects.filter(cycle=cycle, target_type=TargetType.EMPLOYEE)
        .select_related('target_user', 'target_user__department')
        .order_by('target_user__employee_no')
    )

    keep_user_ids = []

    for assignment in assignments:
        result.total_targets += 1
        user = assignment.target_user

        if active_item_count == 0:
            result.skipped_reasons.append(_skip(user, NO_ACTIVE_ITEMS))
            continue

        primary, secondary, individual = _score_for_assignment(assignment, responses, cycle)

        if primary is None:
            # 1차 평가지가 제출되지 않았거나 환산이 불가능하다
            submitted = (assignment.id, EvaluationRound.PRIMARY) in responses
            reason = ZERO_WEIGHT_SUM if submitted else PRIMARY_NOT_SUBMITTED
            result.skipped_reasons.append(_skip(user, reason))
            continue

        dept_score = resolve_department_score(user.department_id, dept_scores, parent_map)
        adjustment = department_adjustment(dept_score, cycle)

        ScoreResult.objects.update_or_create(
            cycle=cycle,
            user=user,
            defaults={
                'department': user.department,
                'primary_score': primary,
                'secondary_score': secondary,
                'individual_score': individual,
                'department_score': dept_score,
                'department_adjustment': adjustment,
                'final_score': final_score(individual, adjustment),
            },
        )
        keep_user_ids.append(user.id)
        result.calculated += 1

    # 재산출에서 제외된 대상의 이전 결과를 남겨두면 화면과 CSV가 어긋난다
    ScoreResult.objects.filter(cycle=cycle).exclude(user_id__in=keep_user_ids).delete()

    return result


def _skip(user, reason):
    return {
        'user_id': user.id,
        'employee_no': user.employee_no,
        'name': user.name,
        'reason': reason,
    }


def department_score_rows(cycle):
    """부서 성과 점수 화면용 행 목록 (specs/05-admin-features.md FR-A-08).

    배정이 있는 부서는 1차·2차 환산 점수와 결합 점수를, 배정이 없거나 미제출인
    부서는 상위 부서에서 상속한 점수를 함께 싣는다.
    """
    from ..models import ScoreResult

    responses = _responses_by_assignment(cycle)
    parent_map = _department_parent_map()

    member_counts = {
        row['department_id']: row['c']
        for row in ScoreResult.objects.filter(cycle=cycle)
        .values('department_id')
        .annotate(c=Count('id'))
    }

    assignments = (
        EvaluatorAssignment.objects.filter(cycle=cycle, target_type=TargetType.DEPARTMENT)
        .select_related('target_department')
        .order_by('target_department__code')
    )

    rows = []
    for assignment in assignments:
        primary, secondary, combined = _score_for_assignment(assignment, responses, cycle)
        department = assignment.target_department
        rows.append(
            {
                'department_id': department.id,
                'department_code': department.code,
                'department_name': department.name,
                'primary_score': primary,
                'secondary_score': secondary,
                'department_score': combined,
                'inherited_score': None,
                'department_adjustment': department_adjustment(combined, cycle),
                'member_count': member_counts.get(department.id, 0),
                'evaluated': combined is not None,
            }
        )

    # 미평가 부서는 상위 부서 점수를 상속해 실제 적용되는 가감을 보여준다
    scores = {row['department_id']: row['department_score'] for row in rows}
    for row in rows:
        if row['department_score'] is None:
            inherited = resolve_department_score(
                parent_map.get(row['department_id']), scores, parent_map
            )
            row['inherited_score'] = inherited
            row['department_adjustment'] = department_adjustment(inherited, cycle)

    return rows
