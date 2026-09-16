"""평가지 작성·저장·제출 (specs/04-employee-features.md FR-E-03 ~ FR-E-06)."""

from django.db import transaction
from django.utils import timezone

from apps.common.exceptions import DomainError

from ..models import (
    CycleStatus,
    EvaluationAnswer,
    EvaluationResponse,
    EvaluationRound,
    ResponseStatus,
)
from .progress import active_items, compute_progress, missing_item_ids


class AlreadySubmitted(DomainError):
    default_detail = '이미 제출된 평가입니다. 수정이 필요하면 관리자에게 문의하세요.'
    default_code = 'ALREADY_SUBMITTED'


class CycleNotOpen(DomainError):
    default_detail = '진행 중인 평가 회차가 아닙니다.'
    default_code = 'CYCLE_NOT_OPEN'


class CycleDeadlinePassed(DomainError):
    default_detail = '응답 마감일이 지났습니다.'
    default_code = 'CYCLE_DEADLINE_PASSED'


class IncompleteAnswers(DomainError):
    status_code = 400
    default_detail = '응답하지 않은 항목이 있습니다.'
    default_code = 'INCOMPLETE_ANSWERS'


class NotAssignedEvaluator(DomainError):
    status_code = 403
    default_detail = '이 평가의 평가자가 아닙니다.'
    default_code = 'NOT_ASSIGNED_EVALUATOR'


def resolve_round(assignment, user):
    """사용자가 이 배정에서 맡은 차수를 판정한다."""
    if assignment.primary_evaluator_id == user.pk:
        return EvaluationRound.PRIMARY
    if assignment.secondary_evaluator_id == user.pk:
        return EvaluationRound.SECONDARY
    raise NotAssignedEvaluator()


def ensure_writable(response):
    """작성·제출이 가능한 상태인지 확인한다."""
    if response.is_submitted:
        raise AlreadySubmitted()

    cycle = response.assignment.cycle
    if cycle.status != CycleStatus.OPEN:
        raise CycleNotOpen()
    if cycle.ends_on < timezone.localdate():
        raise CycleDeadlinePassed()


def get_or_create_response(assignment, user):
    """평가지를 가져오거나 만든다. 이미 있으면 그대로 돌려준다 (멱등)."""
    round_value = resolve_round(assignment, user)

    cycle = assignment.cycle
    if cycle.status != CycleStatus.OPEN:
        raise CycleNotOpen()

    response, created = EvaluationResponse.objects.get_or_create(
        assignment=assignment,
        round=round_value,
        defaults={'evaluator': user, 'status': ResponseStatus.DRAFT},
    )

    # 평가자가 교체된 뒤 기존 DRAFT가 남아 있을 수 있다
    if not created and response.evaluator_id != user.pk:
        if response.status == ResponseStatus.DRAFT:
            response.evaluator = user
            response.save(update_fields=['evaluator', 'updated_at'])
        else:
            raise NotAssignedEvaluator()

    return response, created


@transaction.atomic
def save_draft(response, *, answers=None, overall_comment=None):
    """임시 저장. 전달된 항목만 upsert하며 부분 저장을 허용한다."""
    ensure_writable(response)

    if overall_comment is not None:
        response.overall_comment = overall_comment
        response.save(update_fields=['overall_comment', 'updated_at'])

    if answers:
        allowed = {item.id: item for item in active_items(response.assignment)}

        for entry in answers:
            item = allowed.get(entry['item'])
            if item is None:
                # 다른 회차·대상 유형의 항목이거나 비활성 항목이면 무시한다
                continue

            score = entry.get('score')
            if score is not None and (score < 1 or score > item.max_score):
                raise IncompleteAnswers(
                    f'{item.title} 항목의 점수는 1 ~ {item.max_score} 사이여야 합니다.',
                    code='SCORE_OUT_OF_RANGE',
                )

            EvaluationAnswer.objects.update_or_create(
                response=response,
                item=item,
                defaults={'score': score, 'comment': entry.get('comment', '')},
            )

    response.refresh_from_db()
    return response


def submit(response_id, user):
    """평가지를 제출한다.

    select_for_update로 행을 잠가 더블 클릭·다중 탭에서 오는 동시 요청을 직렬화한다.
    """
    with transaction.atomic():
        response = (
            EvaluationResponse.objects.select_for_update()
            .select_related('assignment', 'assignment__cycle')
            .get(pk=response_id)
        )

        if response.evaluator_id != user.pk:
            raise NotAssignedEvaluator()

        ensure_writable(response)

        missing = missing_item_ids(response)
        if missing:
            raise IncompleteAnswers(context={'missing_items': missing})

        response.status = ResponseStatus.SUBMITTED
        response.submitted_at = timezone.now()
        response.save(update_fields=['status', 'submitted_at', 'updated_at'])

    return response


def reopen(response, *, reason=''):
    """제출된 평가지를 DRAFT로 되돌린다 (관리자 반려. Phase 5에서 API 연결)."""
    response.status = ResponseStatus.DRAFT
    response.submitted_at = None
    response.save(update_fields=['status', 'submitted_at', 'updated_at'])
    return response


def build_detail(response):
    """항목과 내 답변을 결합한 평가지 상세 구조."""
    items = list(active_items(response.assignment))
    answers = {a.item_id: a for a in response.answers.all()}

    answered_count = sum(
        1 for item in items if answers.get(item.id) and answers[item.id].score is not None
    )
    progress = compute_progress(response, total_items=len(items), answered_count=answered_count)

    cycle = response.assignment.cycle
    editable = (
        not response.is_submitted
        and cycle.status == CycleStatus.OPEN
        and cycle.ends_on >= timezone.localdate()
    )

    return {
        'items': items,
        'answers': answers,
        'progress': progress,
        'editable': editable,
    }
