"""직원용 평가 응답 API (specs/04-employee-features.md, specs/07-api.md §3)."""

import logging

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CycleStatus, EvaluationResponse, ResponseStatus
from .serializers_my import (
    DraftSaveSerializer,
    MyResponseDetailSerializer,
    MyResponseSummarySerializer,
    ResponseCreateSerializer,
    serialize_cycle,
    serialize_target,
)
from .services import progress as progress_service
from .services import response as response_service

audit = logging.getLogger('audit')


class MyAssignmentsView(APIView):
    """내가 평가자로 배정된 대상 목록 (진행 중 회차)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(summary='내 평가 목록', tags=['my'])
    def get(self, request):
        rows = progress_service.assignments_for_evaluator(request.user, only_open=True)

        # 평가지를 한 번에 읽어 N+1을 피한다
        assignment_ids = [assignment.id for assignment, _ in rows]
        responses = {
            (r.assignment_id, r.round): r
            for r in EvaluationResponse.objects.filter(
                assignment_id__in=assignment_ids, evaluator=request.user
            ).prefetch_related('answers')
        }

        today = timezone.localdate()
        results = []
        summary = {'total': 0, 'submitted': 0, 'draft': 0, 'not_started': 0}
        cycle = None

        for assignment, round_value in rows:
            cycle = cycle or assignment.cycle
            response = responses.get((assignment.id, round_value))

            total_items = progress_service.active_items(assignment).count()
            if response is None:
                progress = {'progress': 0, 'answered_count': 0, 'total_items': total_items}
                state = 'NOT_STARTED'
            else:
                answered = sum(1 for a in response.answers.all() if a.score is not None)
                progress = progress_service.compute_progress(
                    response, total_items=total_items, answered_count=answered
                )
                state = response.status

            editable = (
                assignment.cycle.status == CycleStatus.OPEN
                and assignment.cycle.ends_on >= today
                and state != ResponseStatus.SUBMITTED
            )

            summary['total'] += 1
            if state == ResponseStatus.SUBMITTED:
                summary['submitted'] += 1
            elif state == ResponseStatus.DRAFT:
                summary['draft'] += 1
            else:
                summary['not_started'] += 1

            results.append(
                {
                    'assignment_id': assignment.id,
                    'round': round_value,
                    'target_type': assignment.target_type,
                    'target': serialize_target(assignment),
                    'cycle': serialize_cycle(assignment.cycle),
                    'response_id': response.id if response else None,
                    'status': state,
                    'progress': progress['progress'],
                    'answered_count': progress['answered_count'],
                    'total_items': progress['total_items'],
                    'submitted_at': response.submitted_at if response else None,
                    'editable': editable,
                }
            )

        results.sort(key=lambda r: (r['status'] == ResponseStatus.SUBMITTED, r['target']['name']))

        return Response(
            {
                'cycle': serialize_cycle(cycle) if cycle else None,
                'summary': summary,
                'results': results,
            }
        )


@extend_schema(tags=['my'])
class MyResponseViewSet(viewsets.GenericViewSet):
    """내 평가지 조회·임시저장·제출.

    queryset을 evaluator=request.user로 좁혀 타인의 평가지 접근을 원천 차단한다.
    객체 단위 권한 검사에만 의존하지 않는다 (specs/09-non-functional.md §1).
    """

    permission_classes = [IsAuthenticated]
    serializer_class = MyResponseDetailSerializer

    def get_queryset(self):
        return EvaluationResponse.objects.filter(evaluator=self.request.user).select_related(
            'assignment',
            'assignment__cycle',
            'assignment__target_user',
            'assignment__target_user__department',
            'assignment__target_department',
        )

    def _detail_response(self, response, http_status=status.HTTP_200_OK):
        detail = response_service.build_detail(response)
        serializer = MyResponseDetailSerializer(response, context={'detail': detail})
        return Response(serializer.data, status=http_status)

    def _summary_response(self, response):
        detail = response_service.build_detail(response)
        response.progress = detail['progress']['progress']
        response.answered_count = detail['progress']['answered_count']
        response.total_items = detail['progress']['total_items']
        return Response(MyResponseSummarySerializer(response).data)

    @extend_schema(summary='평가지 상세')
    def retrieve(self, request, pk=None):
        return self._detail_response(self.get_object())

    @extend_schema(
        summary='평가지 생성',
        request=ResponseCreateSerializer,
        description='이미 존재하면 기존 평가지를 200으로 반환한다 (멱등).',
    )
    def create(self, request):
        serializer = ResponseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment = serializer.validated_data['assignment']

        response, created = response_service.get_or_create_response(assignment, request.user)
        return self._detail_response(
            response, status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    @extend_schema(
        summary='임시 저장',
        request=DraftSaveSerializer,
        description='전달된 항목만 upsert한다. score가 null이어도 저장된다.',
    )
    def update(self, request, pk=None):
        response = self.get_object()
        serializer = DraftSaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        response_service.save_draft(
            response,
            answers=serializer.validated_data.get('answers'),
            overall_comment=serializer.validated_data.get('overall_comment'),
        )
        return self._summary_response(response)

    @extend_schema(summary='제출')
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        # 소유권 확인을 위해 queryset을 먼저 거친다
        self.get_object()
        response = response_service.submit(pk, request.user)

        audit.info(
            '[AUDIT] actor=%s action=response_submit response=%s',
            request.user.employee_no,
            response.id,
        )
        return self._summary_response(response)
