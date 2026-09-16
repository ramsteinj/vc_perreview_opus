"""CSV 내보내기 (specs/05-admin-features.md FR-A-07).

공통 규칙:
- 인코딩은 UTF-8 with BOM. BOM이 없으면 Excel에서 한글이 깨진다.
- 줄바꿈은 CRLF, 구분자는 콤마. 값의 이스케이프는 csv 모듈에 맡긴다.
- StreamingHttpResponse + 제너레이터로 메모리를 상수로 유지한다.
"""

import csv
from datetime import datetime
from urllib.parse import quote

from django.db.models import Prefetch
from django.http import StreamingHttpResponse

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
from . import status as status_service

BOM = '﻿'

SKIP_REASON_LABELS = {
    'PRIMARY_NOT_SUBMITTED': '1차 평가 미제출',
    'NO_ASSIGNMENT': '평가자 미배정',
    'NO_ACTIVE_ITEMS': '활성 평가 항목 없음',
    'ZERO_WEIGHT_SUM': '환산 가능한 응답 없음',
}

STATUS_LABELS = {
    status_service.NOT_STARTED: '미시작',
    ResponseStatus.DRAFT: '임시저장',
    ResponseStatus.SUBMITTED: '제출완료',
}

ROUND_LABELS = {EvaluationRound.PRIMARY: '1차', EvaluationRound.SECONDARY: '2차'}
TARGET_TYPE_LABELS = {TargetType.EMPLOYEE: '개인', TargetType.DEPARTMENT: '부서'}


class Echo:
    """csv.writer가 쓴 줄을 그대로 돌려주는 가짜 파일 객체."""

    def write(self, value):
        return value


def _writer():
    # Excel 호환을 위해 CRLF로 끝낸다
    return csv.writer(Echo(), lineterminator='\r\n')


def streaming_response(rows, filename):
    """제너레이터를 CSV 스트리밍 응답으로 감싼다."""
    response = StreamingHttpResponse(rows, content_type='text/csv; charset=utf-8')
    encoded = quote(filename)
    response['Content-Disposition'] = f"attachment; filename*=UTF-8''{encoded}"
    response['Cache-Control'] = 'no-store'
    return response


def build_filename(cycle, suffix):
    safe_name = cycle.name.replace(' ', '_').replace('/', '-')
    stamp = datetime.now().strftime('%Y%m%d')
    return f'{safe_name}_{suffix}_{stamp}.csv'


def _fmt(value):
    """Decimal을 소수 둘째 자리 문자열로. None은 빈 칸."""
    return '' if value is None else f'{value:.2f}'


def _fmt_dt(value):
    return '' if value is None else value.astimezone().strftime('%Y-%m-%d %H:%M')


# ── 7-1. 점수 결과 ──────────────────────────────────────────────
SCORE_HEADERS = [
    '회차',
    '사번',
    '성명',
    '부서코드',
    '부서명',
    '직위',
    '1차 평가자',
    '1차 점수',
    '2차 평가자',
    '2차 점수',
    '개인 평가 점수',
    '부서 성과 점수',
    '부서 가감',
    '최종 점수',
    '산출 시각',
    '비고',
]


def iter_score_rows(cycle, *, department=None, search=None):
    """산출 대상 전체를 순회한다.

    미산출자도 행으로 포함하고 점수 칸은 비운 뒤 비고에 사유를 적는다
    (specs/05-admin-features.md FR-A-07 수용 기준).
    """
    from .scoring import (
        NO_ACTIVE_ITEMS,
        PRIMARY_NOT_SUBMITTED,
        ZERO_WEIGHT_SUM,
    )

    assignments = (
        EvaluatorAssignment.objects.filter(cycle=cycle, target_type=TargetType.EMPLOYEE)
        .select_related(
            'target_user',
            'target_user__department',
            'primary_evaluator',
            'secondary_evaluator',
        )
        .order_by('target_user__employee_no')
    )
    if department:
        assignments = assignments.filter(target_user__department_id=department)
    if search:
        from django.db.models import Q

        assignments = assignments.filter(
            Q(target_user__name__icontains=search) | Q(target_user__employee_no__icontains=search)
        )

    results = {
        r.user_id: r for r in ScoreResult.objects.filter(cycle=cycle).select_related('department')
    }

    has_active_items = EvaluationItem.objects.filter(
        cycle=cycle, target_type=TargetType.EMPLOYEE, is_active=True
    ).exists()

    submitted_primary = set(
        EvaluationResponse.objects.filter(
            assignment__cycle=cycle,
            round=EvaluationRound.PRIMARY,
            status=ResponseStatus.SUBMITTED,
        ).values_list('assignment_id', flat=True)
    )

    for assignment in assignments:
        user = assignment.target_user
        score = results.get(user.id)

        if score is not None:
            note = ''
        elif not has_active_items:
            note = SKIP_REASON_LABELS[NO_ACTIVE_ITEMS]
        elif assignment.id in submitted_primary:
            note = SKIP_REASON_LABELS[ZERO_WEIGHT_SUM]
        else:
            note = SKIP_REASON_LABELS[PRIMARY_NOT_SUBMITTED]

        department_obj = score.department if score else user.department

        yield [
            cycle.name,
            user.employee_no,
            user.name,
            department_obj.code if department_obj else '',
            department_obj.name if department_obj else '',
            user.position,
            assignment.primary_evaluator.name if assignment.primary_evaluator else '',
            _fmt(score.primary_score) if score else '',
            assignment.secondary_evaluator.name if assignment.secondary_evaluator else '',
            _fmt(score.secondary_score) if score else '',
            _fmt(score.individual_score) if score else '',
            _fmt(score.department_score) if score else '',
            _fmt(score.department_adjustment) if score else '',
            _fmt(score.final_score) if score else '',
            _fmt_dt(score.calculated_at) if score else '',
            note,
        ]


def stream_scores_csv(cycle, **filters):
    writer = _writer()
    yield BOM
    yield writer.writerow(SCORE_HEADERS)
    for row in iter_score_rows(cycle, **filters):
        yield writer.writerow(row)


# ── 7-2. 응답 상세 ──────────────────────────────────────────────
RESPONSE_BASE_HEADERS = [
    '사번',
    '성명',
    '부서',
    '대상유형',
    '차수',
    '평가자',
    '평가자 사번',
    '상태',
    '진행률',
    '제출시각',
]


def _item_columns(cycle):
    """항목 컬럼 정의. 같은 코드가 개인·부서에 모두 있으면 접미사로 구분한다."""
    items = list(EvaluationItem.objects.filter(cycle=cycle).order_by('target_type', 'order', 'id'))

    seen = {}
    for item in items:
        seen.setdefault(item.code, set()).add(item.target_type)

    columns = []
    for item in items:
        label = item.code
        if len(seen[item.code]) > 1:
            label = f'{item.code}({TARGET_TYPE_LABELS[item.target_type]})'
        columns.append((item.id, label))
    return columns


def iter_response_rows(cycle, *, department=None, status=None, target_type=None, search=None):
    """기대 응답 행 전체를 순회한다. 미시작 건도 포함한다."""
    columns = _item_columns(cycle)

    responses = {
        (r.assignment_id, r.round): r
        for r in EvaluationResponse.objects.filter(assignment__cycle=cycle)
        .select_related('evaluator')
        .prefetch_related(
            Prefetch('answers', queryset=EvaluationAnswer.objects.select_related('item'))
        )
    }

    rows = status_service.detail(
        cycle,
        department=department,
        status=status,
        target_type=target_type,
        search=search,
        ordering='evaluator',
    )

    for row in rows:
        response = responses.get((row['assignment_id'], row['round']))
        answers = {a.item_id: a for a in response.answers.all()} if response else {}

        base = [
            row['target'].get('employee_no', ''),
            row['target']['name'],
            row['target'].get('department_name') or row['target'].get('code', ''),
            TARGET_TYPE_LABELS[row['target_type']],
            ROUND_LABELS[row['round']],
            row['evaluator']['name'],
            row['evaluator']['employee_no'],
            STATUS_LABELS[row['status']],
            f'{row["progress"]}%',
            _fmt_dt(row['submitted_at']),
        ]

        item_cells = []
        for item_id, _label in columns:
            answer = answers.get(item_id)
            item_cells.append('' if answer is None or answer.score is None else answer.score)
            item_cells.append('' if answer is None else answer.comment)

        overall = response.overall_comment if response else ''
        yield base + item_cells + [overall]


def stream_responses_csv(cycle, **filters):
    writer = _writer()
    headers = list(RESPONSE_BASE_HEADERS)
    for _item_id, label in _item_columns(cycle):
        headers.extend([label, f'{label}_의견'])
    headers.append('종합의견')

    yield BOM
    yield writer.writerow(headers)
    for row in iter_response_rows(cycle, **filters):
        yield writer.writerow(row)


# ── 7-3. 미응답자 ───────────────────────────────────────────────
PENDING_HEADERS = [
    '평가자 사번',
    '평가자 성명',
    '평가자 부서',
    '미응답 건수',
    '미시작',
    '임시저장',
    '평가 대상',
    '대상유형',
    '차수',
    '상태',
    '진행률',
]


def iter_pending_rows(cycle, *, department=None, search=None):
    """미응답자를 대상 단위로 펼친다. Excel에서 바로 필터링할 수 있게."""
    groups = status_service.pending(cycle, department=department, search=search)

    for group in groups:
        evaluator = group['evaluator']
        for target in group['pending_targets']:
            yield [
                evaluator['employee_no'],
                evaluator['name'],
                evaluator['department_name'] or '',
                group['pending_count'],
                group['not_started'],
                group['draft'],
                target['target_name'],
                TARGET_TYPE_LABELS[target['target_type']],
                ROUND_LABELS[target['round']],
                STATUS_LABELS[target['status']],
                f'{target["progress"]}%',
            ]


def stream_pending_csv(cycle, **filters):
    writer = _writer()
    yield BOM
    yield writer.writerow(PENDING_HEADERS)
    for row in iter_pending_rows(cycle, **filters):
        yield writer.writerow(row)
