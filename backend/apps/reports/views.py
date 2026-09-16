"""응답 현황 조회와 평가지 반려 (specs/05-admin-features.md FR-A-06)."""

import logging

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status as http_status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminRole
from apps.common.pagination import StandardPagination
from apps.evaluations.models import (
    EvaluationCycle,
    EvaluationResponse,
    EvaluatorAssignment,
    ResponseStatus,
    TargetType,
)
from apps.evaluations.services import response as response_service

from .models import ScoreResult
from .serializers import (
    AdjustParametersSerializer,
    AdminResponseDetailSerializer,
    DepartmentScoreRowSerializer,
    ReopenSerializer,
    ScoreResultSerializer,
)
from .services import scoring as scoring_service
from .services import status as status_service

audit = logging.getLogger('audit')


class _CycleScopedView(APIView):
    permission_classes = [IsAdminRole]

    def get_cycle(self, pk):
        from django.shortcuts import get_object_or_404

        return get_object_or_404(EvaluationCycle, pk=pk)


@extend_schema(tags=['admin:status'])
class StatusSummaryView(_CycleScopedView):
    @extend_schema(summary='응답 현황 요약')
    def get(self, request, pk):
        cycle = self.get_cycle(pk)
        return Response(status_service.summary(cycle))


@extend_schema(tags=['admin:status'])
class StatusDetailView(_CycleScopedView):
    @extend_schema(
        summary='응답 현황 상세',
        parameters=[
            OpenApiParameter('department', int, description='평가자 소속 부서'),
            OpenApiParameter(
                'status', str, description='NOT_STARTED / DRAFT / SUBMITTED (쉼표로 복수 지정)'
            ),
            OpenApiParameter('round', str, description='PRIMARY / SECONDARY'),
            OpenApiParameter('target_type', str, description='EMPLOYEE / DEPARTMENT'),
            OpenApiParameter('search', str, description='평가자명·사번·대상명'),
            OpenApiParameter(
                'ordering', str, description='status / progress / submitted_at (- 접두사로 역순)'
            ),
        ],
    )
    def get(self, request, pk):
        cycle = self.get_cycle(pk)
        rows = status_service.detail(
            cycle,
            department=request.query_params.get('department'),
            status=request.query_params.get('status'),
            round_value=request.query_params.get('round'),
            target_type=request.query_params.get('target_type'),
            search=request.query_params.get('search'),
            ordering=request.query_params.get('ordering'),
        )

        paginator = StandardPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response(page)


@extend_schema(tags=['admin:status'])
class StatusPendingView(_CycleScopedView):
    @extend_schema(
        summary='미응답자 목록 (평가자별)',
        parameters=[
            OpenApiParameter('department', int, description='평가자 소속 부서'),
            OpenApiParameter('search', str, description='평가자명·사번'),
        ],
    )
    def get(self, request, pk):
        cycle = self.get_cycle(pk)
        results = status_service.pending(
            cycle,
            department=request.query_params.get('department'),
            search=request.query_params.get('search'),
        )
        return Response(
            {
                'count': len(results),
                'pending_total': sum(r['pending_count'] for r in results),
                'results': results,
            }
        )


@extend_schema(tags=['admin:responses'])
class AdminResponseViewSet(viewsets.GenericViewSet):
    """관리자의 평가지 열람(읽기 전용)과 반려."""

    permission_classes = [IsAdminRole]
    serializer_class = AdminResponseDetailSerializer

    def get_queryset(self):
        return EvaluationResponse.objects.select_related(
            'assignment',
            'assignment__cycle',
            'assignment__target_user',
            'assignment__target_user__department',
            'assignment__target_department',
            'evaluator',
            'evaluator__department',
        )

    @extend_schema(summary='평가지 열람 (읽기 전용)')
    def retrieve(self, request, pk=None):
        response = self.get_object()
        detail = response_service.build_detail(response)
        serializer = AdminResponseDetailSerializer(response, context={'detail': detail})
        return Response(serializer.data)

    @extend_schema(summary='평가지 반려', request=ReopenSerializer)
    @action(detail=True, methods=['post'])
    def reopen(self, request, pk=None):
        response = self.get_object()

        if response.status != ResponseStatus.SUBMITTED:
            return Response(
                {
                    'code': 'NOT_SUBMITTED',
                    'detail': '제출된 평가지만 반려할 수 있습니다.',
                },
                status=http_status.HTTP_409_CONFLICT,
            )

        serializer = ReopenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get('reason', '')

        response_service.reopen(response, reason=reason)

        audit.info(
            '[AUDIT] actor=%s action=response_reopen response=%s reason=%s',
            request.user.employee_no,
            response.id,
            reason or '(사유 없음)',
        )

        return Response(
            {
                'id': response.id,
                'status': response.status,
                'submitted_at': None,
                'detail': '평가지를 반려했습니다. 평가자가 다시 수정할 수 있습니다.',
                'recalculation_required': _has_score_result(response),
            }
        )


def _has_score_result(response):
    """이미 산출된 점수가 있으면 재산출이 필요하다."""
    target_user_id = response.assignment.target_user_id
    if target_user_id is None:
        return False
    return ScoreResult.objects.filter(
        cycle_id=response.assignment.cycle_id, user_id=target_user_id
    ).exists()


@extend_schema(tags=['admin:scores'])
class ScoreCalculateView(_CycleScopedView):
    @extend_schema(
        summary='점수 산출 / 재산출',
        description='멱등하다. 같은 입력에 몇 번을 실행해도 같은 결과를 낸다.',
    )
    def post(self, request, pk):
        cycle = self.get_cycle(pk)
        result = scoring_service.calculate_cycle(cycle)

        audit.info(
            '[AUDIT] actor=%s action=score_calculate cycle=%s calculated=%s skipped=%s',
            request.user.employee_no,
            cycle.name,
            result.calculated,
            result.skipped,
        )

        from django.utils import timezone

        return Response(
            {
                'cycle_id': cycle.id,
                'calculated_at': timezone.now(),
                'total_targets': result.total_targets,
                'calculated': result.calculated,
                'skipped': result.skipped,
                'skipped_reasons': result.skipped_reasons,
                'is_provisional': cycle.status != 'CLOSED',
            }
        )


@extend_schema(tags=['admin:scores'])
class ScoreListView(_CycleScopedView):
    @extend_schema(
        summary='최종 점수 목록',
        parameters=[
            OpenApiParameter('department', int),
            OpenApiParameter('search', str, description='성명 · 사번'),
            OpenApiParameter('ordering', str, description='final_score / individual_score 등'),
        ],
    )
    def get(self, request, pk):
        cycle = self.get_cycle(pk)

        queryset = ScoreResult.objects.filter(cycle=cycle).select_related('user', 'department')

        department = request.query_params.get('department')
        if department:
            queryset = queryset.filter(department_id=department)

        search = request.query_params.get('search')
        if search:
            from django.db.models import Q

            queryset = queryset.filter(
                Q(user__name__icontains=search) | Q(user__employee_no__icontains=search)
            )

        allowed = {
            'final_score',
            'individual_score',
            'department_score',
            'user__employee_no',
            'user__name',
        }
        ordering = request.query_params.get('ordering', '-final_score')
        if ordering.lstrip('-') not in allowed:
            ordering = '-final_score'
        queryset = queryset.order_by(ordering, 'user__employee_no')

        # 산출되지 않은 대상을 함께 알려줘야 화면이 전체 그림을 보여줄 수 있다
        expected = EvaluatorAssignment.objects.filter(
            cycle=cycle, target_type=TargetType.EMPLOYEE
        ).count()

        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        data = paginator.get_paginated_response(ScoreResultSerializer(page, many=True).data)
        data.data['total_targets'] = expected
        data.data['not_calculated'] = max(
            expected - ScoreResult.objects.filter(cycle=cycle).count(), 0
        )
        data.data['is_provisional'] = cycle.status != 'CLOSED'
        return data


@extend_schema(tags=['admin:scores'])
class DepartmentScoreView(_CycleScopedView):
    @extend_schema(summary='부서 성과 점수 목록')
    def get(self, request, pk):
        cycle = self.get_cycle(pk)
        rows = scoring_service.department_score_rows(cycle)

        parameters = AdjustParametersSerializer(
            {
                'baseline': cycle.dept_baseline_score,
                'factor': cycle.dept_adjust_factor,
                'limit': cycle.dept_adjust_limit,
            }
        ).data

        return Response(
            {
                'cycle_id': cycle.id,
                'parameters': parameters,
                'count': len(rows),
                'results': DepartmentScoreRowSerializer(rows, many=True).data,
            }
        )
