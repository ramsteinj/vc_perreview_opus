"""평가자 배정 로직 (specs/05-admin-features.md FR-A-05)."""

from django.db import transaction

from apps.accounts.models import Department, User
from apps.common.exceptions import DomainError

from ..models import CycleStatus, EvaluatorAssignment, TargetType


class CycleNotEditable(DomainError):
    default_detail = '마감된 회차는 수정할 수 없습니다.'
    default_code = 'CYCLE_NOT_EDITABLE'


def ensure_editable(cycle):
    if cycle.status == CycleStatus.CLOSED:
        raise CycleNotEditable()


def assignment_overview(cycle, target_type, *, department=None, search=None):
    """평가 대상 전체 목록에 현재 배정 상태를 결합해 반환한다.

    배정이 없는 대상도 행으로 포함해야 미배정 현황이 드러난다.
    """
    assignments = {}
    queryset = cycle.assignments.filter(target_type=target_type).select_related(
        'primary_evaluator', 'secondary_evaluator'
    )
    for item in queryset:
        key = (
            item.target_user_id if target_type == TargetType.EMPLOYEE else item.target_department_id
        )
        assignments[key] = item

    rows = []
    if target_type == TargetType.EMPLOYEE:
        targets = User.objects.filter(is_active=True).select_related('department')
        if department:
            targets = targets.filter(department_id=department)
        if search:
            from django.db.models import Q

            targets = targets.filter(Q(name__icontains=search) | Q(employee_no__icontains=search))
        targets = targets.order_by('department__code', 'employee_no')

        for target in targets:
            rows.append(_row(assignments.get(target.id), target, target_type))
    else:
        targets = Department.objects.filter(is_active=True)
        if search:
            targets = targets.filter(name__icontains=search)
        targets = targets.order_by('code')

        for target in targets:
            rows.append(_row(assignments.get(target.id), target, target_type))

    return rows


def _row(assignment, target, target_type):
    if target_type == TargetType.EMPLOYEE:
        target_info = {
            'id': target.id,
            'name': target.name,
            'employee_no': target.employee_no,
            'department_name': target.department.name if target.department else None,
        }
    else:
        target_info = {'id': target.id, 'name': target.name, 'code': target.code}

    return {
        'assignment_id': assignment.id if assignment else None,
        'target_type': target_type,
        'target': target_info,
        'primary_evaluator': _evaluator(assignment.primary_evaluator) if assignment else None,
        'secondary_evaluator': (
            _evaluator(assignment.secondary_evaluator)
            if assignment and assignment.secondary_evaluator
            else None
        ),
        'assigned': assignment is not None,
    }


def _evaluator(user):
    return {'id': user.id, 'name': user.name, 'employee_no': user.employee_no}


@transaction.atomic
def bulk_assign(
    cycle,
    target_type,
    *,
    primary_evaluator,
    secondary_evaluator=None,
    department=None,
    target_ids=None,
    overwrite=False,
):
    """여러 대상에 같은 평가자를 일괄 배정한다.

    본인이 대상인 건은 자기 평가가 되므로 건너뛰고 사유와 함께 보고한다.
    """
    ensure_editable(cycle)

    if target_type == TargetType.EMPLOYEE:
        targets = User.objects.filter(is_active=True)
        if department:
            targets = targets.filter(department_id=department)
        if target_ids:
            targets = targets.filter(pk__in=target_ids)
    else:
        targets = Department.objects.filter(is_active=True)
        if target_ids:
            targets = targets.filter(pk__in=target_ids)

    created = 0
    updated = 0
    skipped = []

    for target in targets:
        if target_type == TargetType.EMPLOYEE:
            if target.id == primary_evaluator.id:
                skipped.append(
                    {'target_id': target.id, 'name': target.name, 'reason': 'SELF_EVALUATION'}
                )
                continue
            if secondary_evaluator and target.id == secondary_evaluator.id:
                skipped.append(
                    {'target_id': target.id, 'name': target.name, 'reason': 'SELF_EVALUATION'}
                )
                continue
            lookup = {'target_user': target}
        else:
            lookup = {'target_department': target}

        existing = EvaluatorAssignment.objects.filter(
            cycle=cycle, target_type=target_type, **lookup
        ).first()

        if existing and not overwrite:
            skipped.append(
                {'target_id': target.id, 'name': target.name, 'reason': 'ALREADY_ASSIGNED'}
            )
            continue

        if existing:
            existing.primary_evaluator = primary_evaluator
            existing.secondary_evaluator = secondary_evaluator
            existing.full_clean()
            existing.save()
            updated += 1
        else:
            assignment = EvaluatorAssignment(
                cycle=cycle,
                target_type=target_type,
                primary_evaluator=primary_evaluator,
                secondary_evaluator=secondary_evaluator,
                **lookup,
            )
            assignment.full_clean()
            assignment.save()
            created += 1

    return {'created': created, 'updated': updated, 'skipped': skipped}


def assignments_for_user(user, *, only_open=True):
    """해당 사용자가 평가자로 배정된 건 (사용자 비활성화 경고에 사용)."""
    queryset = EvaluatorAssignment.objects.filter(models_q_evaluator(user)).select_related(
        'cycle', 'target_user', 'target_department'
    )
    if only_open:
        queryset = queryset.filter(cycle__status=CycleStatus.OPEN)
    return queryset


def models_q_evaluator(user):
    from django.db.models import Q

    return Q(primary_evaluator=user) | Q(secondary_evaluator=user)
