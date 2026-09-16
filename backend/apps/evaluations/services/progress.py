"""진행률과 응답 집계 (specs/04-employee-features.md FR-E-05)."""

from django.db.models import Q

from ..models import (
    EvaluationItem,
    EvaluationResponse,
    EvaluatorAssignment,
    ResponseStatus,
)


def active_items(assignment):
    """해당 배정에 해당하는 활성 평가 항목 queryset."""
    return EvaluationItem.objects.filter(
        cycle_id=assignment.cycle_id,
        target_type=assignment.target_type,
        is_active=True,
    ).order_by('order', 'id')


def compute_progress(response, *, total_items=None, answered_count=None):
    """진행률(%)을 내림 정수로 반환한다.

    진행률 = (score가 null이 아닌 답변 수 / 활성 항목 총 수) × 100
    항목별 의견과 종합 의견은 진행률에 영향을 주지 않는다.
    """
    if total_items is None:
        total_items = active_items(response.assignment).count()
    if answered_count is None:
        answered_count = response.answers.filter(score__isnull=False, item__is_active=True).count()

    if total_items == 0:
        return {'progress': 0, 'answered_count': 0, 'total_items': 0}

    return {
        'progress': int(answered_count * 100 // total_items),
        'answered_count': answered_count,
        'total_items': total_items,
    }


def missing_item_ids(response):
    """점수가 비어 있는 활성 항목 ID 목록. 제출 검증에 쓴다."""
    answered = set(response.answers.filter(score__isnull=False).values_list('item_id', flat=True))
    return [item.id for item in active_items(response.assignment) if item.id not in answered]


def expected_responses(cycle):
    """회차에서 기대되는 평가지 수.

    분모는 EvaluationResponse 레코드 수가 아니라 배정에서 도출되는 기대 응답 수다.
    아직 작성을 시작하지 않아 레코드가 없는 건도 포함해야 한다.
    1차 배정 1건 + 2차 평가자 지정 1건 = 기대 응답 2건.
    """
    assignments = EvaluatorAssignment.objects.filter(cycle=cycle)
    primary = assignments.count()
    secondary = assignments.filter(secondary_evaluator__isnull=False).count()
    return primary + secondary


def submitted_responses(cycle):
    return EvaluationResponse.objects.filter(
        assignment__cycle=cycle, status=ResponseStatus.SUBMITTED
    ).count()


def pending_responses(cycle):
    """미제출 평가지 수 (미시작 + 임시저장)."""
    return max(expected_responses(cycle) - submitted_responses(cycle), 0)


def assignments_for_evaluator(user, cycle=None, *, only_open=True):
    """사용자가 평가자로 배정된 건을 차수와 함께 펼쳐 반환한다.

    한 배정에서 본인이 1차이면서 동시에 2차일 수는 없으므로 (모델 clean이 막는다)
    배정당 최대 한 행이 나온다.
    """
    from ..models import CycleStatus, EvaluationRound

    queryset = EvaluatorAssignment.objects.filter(
        Q(primary_evaluator=user) | Q(secondary_evaluator=user)
    ).select_related('cycle', 'target_user', 'target_user__department', 'target_department')

    if cycle is not None:
        queryset = queryset.filter(cycle=cycle)
    elif only_open:
        queryset = queryset.filter(cycle__status=CycleStatus.OPEN)

    rows = []
    for assignment in queryset:
        round_value = (
            EvaluationRound.PRIMARY
            if assignment.primary_evaluator_id == user.pk
            else EvaluationRound.SECONDARY
        )
        rows.append((assignment, round_value))
    return rows
