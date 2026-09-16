"""응답 현황 집계 (specs/05-admin-features.md FR-A-06).

분모는 EvaluationResponse 레코드 수가 아니라 배정에서 도출되는 기대 응답 수다.
아직 작성을 시작하지 않아 레코드가 없는 건(NOT_STARTED)도 반드시 포함해야 한다.

설계 노트: 기대 응답 행은 (배정 × 차수)의 LEFT JOIN 구조라 순수 ORM 한 방으로
표현하려면 UNION이 필요하고, 그러면 select_related와 후속 필터가 모두 막힌다.
대신 경계가 명확한 쿼리 3개(배정 / 평가지 / 항목 수)로 읽어와 메모리에서 조립한다.
운영 목표 규모(1000명 내외, specs/09-non-functional.md §2)에서 수천 행 수준이므로
이 방식이 더 단순하고 미시작 포함 로직이 눈에 보인다.
"""

from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Count, Q
from django.utils import timezone

from apps.evaluations.models import (
    EvaluationItem,
    EvaluationResponse,
    EvaluationRound,
    EvaluatorAssignment,
    ResponseStatus,
    TargetType,
)

NOT_STARTED = 'NOT_STARTED'
STATUS_VALUES = (NOT_STARTED, ResponseStatus.DRAFT, ResponseStatus.SUBMITTED)

# 상세 목록 정렬에서 "덜 진행된 것 먼저"가 되도록 하는 상태 순서
_STATUS_ORDER = {NOT_STARTED: 0, ResponseStatus.DRAFT: 1, ResponseStatus.SUBMITTED: 2}


def _rate(submitted, total):
    if not total:
        return Decimal('0.00')
    value = Decimal(submitted) * 100 / Decimal(total)
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _empty_bucket():
    return {'total': 0, 'submitted': 0, 'draft': 0, 'not_started': 0}


def _tally(bucket, status):
    bucket['total'] += 1
    if status == ResponseStatus.SUBMITTED:
        bucket['submitted'] += 1
    elif status == ResponseStatus.DRAFT:
        bucket['draft'] += 1
    else:
        bucket['not_started'] += 1


def build_expected_rows(cycle):
    """회차의 기대 응답 행 전체를 만든다.

    각 배정은 1차 1행 + (2차 평가자가 있으면) 2차 1행을 만든다.
    """
    assignments = (
        EvaluatorAssignment.objects.filter(cycle=cycle)
        .select_related(
            'primary_evaluator',
            'primary_evaluator__department',
            'secondary_evaluator',
            'secondary_evaluator__department',
            'target_user',
            'target_user__department',
            'target_department',
        )
        .order_by('id')
    )

    responses = {
        (r.assignment_id, r.round): r
        for r in EvaluationResponse.objects.filter(assignment__cycle=cycle).annotate(
            answered=Count(
                'answers',
                filter=Q(answers__score__isnull=False, answers__item__is_active=True),
                distinct=True,
            )
        )
    }

    item_counts = {
        row['target_type']: row['c']
        for row in EvaluationItem.objects.filter(cycle=cycle, is_active=True)
        .values('target_type')
        .annotate(c=Count('id'))
    }

    rows = []
    for assignment in assignments:
        total_items = item_counts.get(assignment.target_type, 0)

        pairs = [(EvaluationRound.PRIMARY, assignment.primary_evaluator)]
        if assignment.secondary_evaluator_id:
            pairs.append((EvaluationRound.SECONDARY, assignment.secondary_evaluator))

        for round_value, evaluator in pairs:
            response = responses.get((assignment.id, round_value))
            if response is None:
                status = NOT_STARTED
                answered = 0
                progress = 0
                submitted_at = None
                response_id = None
            else:
                status = response.status
                answered = response.answered
                progress = int(answered * 100 // total_items) if total_items else 0
                submitted_at = response.submitted_at
                response_id = response.id

            rows.append(
                {
                    'assignment_id': assignment.id,
                    'response_id': response_id,
                    'round': round_value,
                    'target_type': assignment.target_type,
                    'status': status,
                    'progress': progress,
                    'answered_count': answered,
                    'total_items': total_items,
                    'submitted_at': submitted_at,
                    'evaluator': {
                        'id': evaluator.id,
                        'employee_no': evaluator.employee_no,
                        'name': evaluator.name,
                        'department_id': evaluator.department_id,
                        'department_name': (
                            evaluator.department.name if evaluator.department else None
                        ),
                    },
                    'target': _serialize_target(assignment),
                }
            )

    return rows


def _serialize_target(assignment):
    if assignment.target_user_id:
        target = assignment.target_user
        return {
            'id': target.id,
            'name': target.name,
            'employee_no': target.employee_no,
            'department_name': target.department.name if target.department else None,
        }
    target = assignment.target_department
    return {'id': target.id, 'name': target.name, 'code': target.code}


def summary(cycle, rows=None):
    """전체·차수별·유형별·부서별 집계.

    부서 집계는 평가자의 소속 부서를 기준으로 한다. 이 화면의 목적이
    독려 대상을 찾는 것이므로 제출 책임자인 평가자를 기준으로 묶는다.
    """
    rows = rows if rows is not None else build_expected_rows(cycle)

    overall = _empty_bucket()
    by_round = {value: _empty_bucket() for value in EvaluationRound.values}
    by_target_type = {value: _empty_bucket() for value in TargetType.values}
    by_department = {}

    for row in rows:
        status = row['status']
        _tally(overall, status)
        _tally(by_round[row['round']], status)
        _tally(by_target_type[row['target_type']], status)

        key = row['evaluator']['department_id']
        if key not in by_department:
            by_department[key] = {
                'department_id': key,
                'department_name': row['evaluator']['department_name'] or '미배정',
                **_empty_bucket(),
            }
        _tally(by_department[key], status)

    today = timezone.localdate()
    return {
        'cycle': {
            'id': cycle.id,
            'name': cycle.name,
            'status': cycle.status,
            'starts_on': cycle.starts_on,
            'ends_on': cycle.ends_on,
            'days_left': (cycle.ends_on - today).days,
        },
        'overall': {
            'total_responses': overall['total'],
            'submitted': overall['submitted'],
            'draft': overall['draft'],
            'not_started': overall['not_started'],
            'submission_rate': _rate(overall['submitted'], overall['total']),
        },
        'by_round': {
            key: {**bucket, 'rate': _rate(bucket['submitted'], bucket['total'])}
            for key, bucket in by_round.items()
        },
        'by_target_type': {
            key: {**bucket, 'rate': _rate(bucket['submitted'], bucket['total'])}
            for key, bucket in by_target_type.items()
        },
        'by_department': sorted(
            (
                {**bucket, 'rate': _rate(bucket['submitted'], bucket['total'])}
                for bucket in by_department.values()
            ),
            key=lambda b: (b['rate'], -b['total']),
        ),
    }


def detail(
    cycle,
    *,
    department=None,
    status=None,
    round_value=None,
    target_type=None,
    search=None,
    ordering=None,
    rows=None,
):
    """상세 목록. 필터는 조합해서 적용된다."""
    rows = rows if rows is not None else build_expected_rows(cycle)

    if department:
        department = int(department)
        rows = [r for r in rows if r['evaluator']['department_id'] == department]
    if status:
        wanted = {s.strip().upper() for s in str(status).split(',') if s.strip()}
        rows = [r for r in rows if r['status'] in wanted]
    if round_value:
        rows = [r for r in rows if r['round'] == round_value]
    if target_type:
        rows = [r for r in rows if r['target_type'] == target_type]
    if search:
        needle = search.strip().lower()
        rows = [
            r
            for r in rows
            if needle in r['evaluator']['name'].lower()
            or needle in r['evaluator']['employee_no'].lower()
            or needle in r['target']['name'].lower()
        ]

    return _sort_detail(rows, ordering)


def _sort_detail(rows, ordering):
    ordering = ordering or 'status'
    descending = ordering.startswith('-')
    field = ordering.lstrip('-')

    keys = {
        'status': lambda r: (_STATUS_ORDER[r['status']], r['evaluator']['name']),
        'progress': lambda r: (r['progress'], r['evaluator']['name']),
        'submitted_at': lambda r: (
            r['submitted_at'] is not None,
            r['submitted_at'] or timezone.now(),
        ),
        'evaluator': lambda r: (r['evaluator']['name'], r['evaluator']['employee_no']),
        'target': lambda r: r['target']['name'],
    }
    key = keys.get(field, keys['status'])
    return sorted(rows, key=key, reverse=descending)


def pending(cycle, *, department=None, search=None, rows=None):
    """미응답자(제출하지 않은 평가자)를 평가자 단위로 묶는다."""
    rows = rows if rows is not None else build_expected_rows(cycle)

    grouped = {}
    for row in rows:
        if row['status'] == ResponseStatus.SUBMITTED:
            continue

        evaluator = row['evaluator']
        if department and evaluator['department_id'] != int(department):
            continue
        if search:
            needle = search.strip().lower()
            if (
                needle not in evaluator['name'].lower()
                and needle not in evaluator['employee_no'].lower()
            ):
                continue

        entry = grouped.setdefault(
            evaluator['id'],
            {
                'evaluator': {
                    'id': evaluator['id'],
                    'employee_no': evaluator['employee_no'],
                    'name': evaluator['name'],
                    'department_name': evaluator['department_name'],
                },
                'pending_count': 0,
                'not_started': 0,
                'draft': 0,
                'pending_targets': [],
            },
        )

        entry['pending_count'] += 1
        if row['status'] == NOT_STARTED:
            entry['not_started'] += 1
        else:
            entry['draft'] += 1

        entry['pending_targets'].append(
            {
                'response_id': row['response_id'],
                'target_name': row['target']['name'],
                'target_type': row['target_type'],
                'round': row['round'],
                'status': row['status'],
                'progress': row['progress'],
            }
        )

    results = sorted(grouped.values(), key=lambda e: (-e['pending_count'], e['evaluator']['name']))
    return results
