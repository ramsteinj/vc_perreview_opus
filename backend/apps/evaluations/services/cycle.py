"""평가 회차 상태 전이와 검증 (specs/05-admin-features.md FR-A-10)."""

from decimal import Decimal

from django.db.models import Count, Sum

from apps.common.exceptions import DomainError

from ..models import CycleStatus, EvaluationItem, TargetType

WEIGHT_TOTAL = Decimal('100.00')


class WeightSumInvalid(DomainError):
    status_code = 400
    default_detail = '평가 항목의 가중치 합계가 100이 아닙니다.'
    default_code = 'WEIGHT_SUM_INVALID'


class NoActiveItems(DomainError):
    status_code = 400
    default_detail = '활성화된 평가 항목이 없습니다.'
    default_code = 'NO_ACTIVE_ITEMS'


class InvalidTransition(DomainError):
    default_detail = '허용되지 않는 상태 전이입니다.'
    default_code = 'INVALID_TRANSITION'


class ConfirmationRequired(DomainError):
    default_detail = '확인이 필요합니다.'
    default_code = 'CONFIRMATION_REQUIRED'


def weight_summary(cycle):
    """대상 유형별 활성 항목의 가중치 합계와 유효성을 반환한다."""
    rows = (
        EvaluationItem.objects.filter(cycle=cycle, is_active=True)
        .values('target_type')
        .annotate(total=Sum('weight'), count=Count('id'))
    )
    by_type = {row['target_type']: row for row in rows}

    summary = {}
    for target_type in TargetType.values:
        row = by_type.get(target_type)
        total = row['total'] if row else Decimal('0.00')
        count = row['count'] if row else 0
        summary[target_type] = {
            'sum': total.quantize(Decimal('0.01')),
            'item_count': count,
            'valid': count > 0 and total == WEIGHT_TOTAL,
        }
    return summary


def unassigned_targets(cycle):
    """1차 평가자가 배정되지 않은 대상 목록을 반환한다."""
    from apps.accounts.models import Department, User

    assigned_user_ids = set(
        cycle.assignments.filter(target_type=TargetType.EMPLOYEE).values_list(
            'target_user_id', flat=True
        )
    )
    assigned_dept_ids = set(
        cycle.assignments.filter(target_type=TargetType.DEPARTMENT).values_list(
            'target_department_id', flat=True
        )
    )

    users = (
        User.objects.filter(is_active=True)
        .exclude(pk__in=assigned_user_ids)
        .select_related('department')
        .order_by('employee_no')
    )
    departments = (
        Department.objects.filter(is_active=True).exclude(pk__in=assigned_dept_ids).order_by('code')
    )

    return {
        'employees': [
            {
                'id': u.id,
                'employee_no': u.employee_no,
                'name': u.name,
                'department_name': u.department.name if u.department else None,
            }
            for u in users
        ],
        'departments': [{'id': d.id, 'code': d.code, 'name': d.name} for d in departments],
    }


def validate_for_open(cycle):
    """OPEN 전이 전 검증. 차단 사유는 예외로, 경고는 반환값으로 전달한다."""
    summary = weight_summary(cycle)

    employee = summary[TargetType.EMPLOYEE]
    department = summary[TargetType.DEPARTMENT]

    if employee['item_count'] == 0 and department['item_count'] == 0:
        raise NoActiveItems()

    invalid = {}
    # 개인 항목은 반드시 있어야 하고 합계가 100이어야 한다
    if employee['item_count'] == 0:
        raise NoActiveItems('개인 평가 항목이 하나도 없습니다.')
    if not employee['valid']:
        invalid['EMPLOYEE'] = {'sum': str(employee['sum']), 'item_count': employee['item_count']}

    # 부서 항목은 선택이지만, 하나라도 있으면 합계가 100이어야 한다
    if department['item_count'] > 0 and not department['valid']:
        invalid['DEPARTMENT'] = {
            'sum': str(department['sum']),
            'item_count': department['item_count'],
        }

    if invalid:
        raise WeightSumInvalid(context={'invalid': invalid})

    return {'unassigned': unassigned_targets(cycle)}


def open_cycle(cycle, *, confirm=False):
    """회차를 OPEN으로 전이한다. 미배정 대상이 있으면 confirm을 요구한다."""
    if cycle.status == CycleStatus.OPEN:
        raise InvalidTransition('이미 진행 중인 회차입니다.', code='ALREADY_OPEN')
    if cycle.status == CycleStatus.CLOSED:
        raise InvalidTransition('마감된 회차는 다시 열 수 없습니다.', code='CYCLE_CLOSED')

    result = validate_for_open(cycle)
    unassigned = result['unassigned']
    pending = len(unassigned['employees']) + len(unassigned['departments'])

    if pending and not confirm:
        raise ConfirmationRequired(
            f'1차 평가자가 배정되지 않은 대상이 {pending}건 있습니다. '
            '그대로 진행하려면 확인이 필요합니다.',
            code='UNASSIGNED_TARGETS',
            context={'unassigned': unassigned},
        )

    cycle.status = CycleStatus.OPEN
    cycle.save(update_fields=['status', 'updated_at'])
    return {'unassigned_count': pending}


def close_cycle(cycle, *, confirm=False):
    """회차를 CLOSED로 전이한다. 미제출 평가지가 있으면 confirm을 요구한다."""
    if cycle.status == CycleStatus.CLOSED:
        raise InvalidTransition('이미 마감된 회차입니다.', code='ALREADY_CLOSED')
    if cycle.status == CycleStatus.DRAFT:
        raise InvalidTransition('진행 중인 회차만 마감할 수 있습니다.', code='CYCLE_NOT_OPEN')

    # 미제출 평가지 집계는 Phase 4(EvaluationResponse)에서 채운다
    pending = _count_pending_responses(cycle)
    if pending and not confirm:
        raise ConfirmationRequired(
            f'제출되지 않은 평가지가 {pending}건 있습니다.',
            code='PENDING_RESPONSES',
            context={'pending_count': pending},
        )

    cycle.status = CycleStatus.CLOSED
    cycle.save(update_fields=['status', 'updated_at'])
    return {'pending_count': pending}


def reopen_cycle(cycle):
    """마감된 회차를 다시 진행 중으로 되돌린다 (관리자 전용, 감사 로그 대상)."""
    if cycle.status != CycleStatus.CLOSED:
        raise InvalidTransition('마감된 회차만 되돌릴 수 있습니다.', code='NOT_CLOSED')
    cycle.status = CycleStatus.OPEN
    cycle.save(update_fields=['status', 'updated_at'])


def _count_pending_responses(cycle):
    """미제출 평가지 수 (미시작 + 임시저장).

    분모는 배정에서 도출되는 기대 응답 수다 (specs/05-admin-features.md FR-A-06).
    """
    from .progress import pending_responses

    return pending_responses(cycle)
