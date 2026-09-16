"""평가 설정 관리 API (specs/05-admin-features.md FR-A-04, FR-A-05, FR-A-10)."""

import logging

from django.db.models import Count
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminRole

from .models import EvaluationCycle, EvaluationItem, EvaluatorAssignment, TargetType
from .serializers import (
    BulkAssignSerializer,
    CloneItemsSerializer,
    EvaluationCycleSerializer,
    EvaluationItemSerializer,
    EvaluatorAssignmentSerializer,
    ItemReorderSerializer,
)
from .services import assignment as assignment_service
from .services import cycle as cycle_service
from .services import item as item_service

audit = logging.getLogger('audit')


@extend_schema(tags=['admin:cycles'])
class EvaluationCycleViewSet(viewsets.ModelViewSet):
    serializer_class = EvaluationCycleSerializer
    permission_classes = [IsAdminRole]
    filterset_fields = ['year', 'status']
    search_fields = ['name']
    ordering_fields = ['year', 'starts_on', 'ends_on', 'created_at']
    ordering = ['-year', '-starts_on']

    def get_queryset(self):
        return EvaluationCycle.objects.annotate(
            item_count=Count('items', distinct=True),
            assignment_count=Count('assignments', distinct=True),
        )

    @extend_schema(summary='가중치 합계 검증')
    @action(detail=True, methods=['get'], url_path='weight-check')
    def weight_check(self, request, pk=None):
        summary = cycle_service.weight_summary(self.get_object())
        return Response(
            {
                key: {
                    'sum': str(value['sum']),
                    'item_count': value['item_count'],
                    'valid': value['valid'],
                }
                for key, value in summary.items()
            }
        )

    @extend_schema(summary='미배정 대상 조회')
    @action(detail=True, methods=['get'], url_path='unassigned')
    def unassigned(self, request, pk=None):
        data = cycle_service.unassigned_targets(self.get_object())
        return Response(
            {
                'employee_count': len(data['employees']),
                'department_count': len(data['departments']),
                **data,
            }
        )

    @extend_schema(
        summary='회차 열기(OPEN)',
        parameters=[
            OpenApiParameter('confirm', bool, description='미배정 대상이 있어도 진행한다.')
        ],
    )
    @action(detail=True, methods=['post'])
    def open(self, request, pk=None):
        cycle = self.get_object()
        confirm = request.query_params.get('confirm') == 'true'
        result = cycle_service.open_cycle(cycle, confirm=confirm)
        audit.info(
            '[AUDIT] actor=%s action=cycle_open target=%s', request.user.employee_no, cycle.name
        )
        return Response({**self.get_serializer(self.get_object()).data, **result})

    @extend_schema(
        summary='회차 마감(CLOSED)',
        parameters=[
            OpenApiParameter('confirm', bool, description='미제출 평가지가 있어도 진행한다.')
        ],
    )
    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        cycle = self.get_object()
        confirm = request.query_params.get('confirm') == 'true'
        result = cycle_service.close_cycle(cycle, confirm=confirm)
        audit.info(
            '[AUDIT] actor=%s action=cycle_close target=%s', request.user.employee_no, cycle.name
        )
        return Response({**self.get_serializer(self.get_object()).data, **result})

    @extend_schema(summary='마감 회차를 다시 열기')
    @action(detail=True, methods=['post'])
    def reopen(self, request, pk=None):
        cycle = self.get_object()
        cycle_service.reopen_cycle(cycle)
        audit.info(
            '[AUDIT] actor=%s action=cycle_reopen target=%s', request.user.employee_no, cycle.name
        )
        return Response(self.get_serializer(self.get_object()).data)

    @extend_schema(summary='다른 회차의 평가 항목 복제', request=CloneItemsSerializer)
    @action(detail=True, methods=['post'], url_path='clone-items')
    def clone_items(self, request, pk=None):
        target_cycle = self.get_object()
        serializer = CloneItemsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = item_service.clone_items(
            serializer.validated_data['source_cycle'],
            target_cycle,
            target_type=serializer.validated_data.get('target_type'),
            replace=serializer.validated_data['replace'],
        )
        audit.info(
            '[AUDIT] actor=%s action=cycle_clone_items target=%s',
            request.user.employee_no,
            target_cycle.name,
        )
        return Response(result)

    def destroy(self, request, *args, **kwargs):
        cycle = self.get_object()
        if cycle.assignments.exists() or cycle.items.exists():
            return Response(
                {
                    'code': 'CYCLE_IN_USE',
                    'detail': '평가 항목이나 배정이 있는 회차는 삭제할 수 없습니다.',
                    'item_count': cycle.items.count(),
                    'assignment_count': cycle.assignments.count(),
                },
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)


@extend_schema(tags=['admin:items'])
class EvaluationItemViewSet(viewsets.ModelViewSet):
    serializer_class = EvaluationItemSerializer
    permission_classes = [IsAdminRole]
    filterset_fields = ['cycle', 'target_type', 'is_active']
    search_fields = ['code', 'title']
    ordering_fields = ['order', 'code', 'weight']
    ordering = ['order', 'id']
    pagination_class = None  # 항목은 회차당 소수이며 편집 화면에서 전체를 다룬다

    def get_queryset(self):
        return EvaluationItem.objects.select_related('cycle')

    def perform_update(self, serializer):
        changed = set(serializer.validated_data.keys())
        item_service.ensure_item_mutable(serializer.instance, changed)
        serializer.save()

    def perform_destroy(self, instance):
        item_service.ensure_item_mutable(instance)
        instance.delete()

    @extend_schema(summary='항목 순서 일괄 변경', request=ItemReorderSerializer)
    @action(detail=False, methods=['post'])
    def reorder(self, request):
        serializer = ItemReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = item_service.reorder_items(
            serializer.validated_data['cycle'], serializer.validated_data['item_ids']
        )
        return Response({'updated': updated})


@extend_schema(tags=['admin:assignments'])
class EvaluatorAssignmentViewSet(viewsets.ModelViewSet):
    serializer_class = EvaluatorAssignmentSerializer
    permission_classes = [IsAdminRole]
    filterset_fields = ['cycle', 'target_type', 'primary_evaluator', 'secondary_evaluator']
    ordering = ['id']

    def get_queryset(self):
        return EvaluatorAssignment.objects.select_related(
            'cycle',
            'target_user',
            'target_user__department',
            'target_department',
            'primary_evaluator',
            'primary_evaluator__department',
            'secondary_evaluator',
            'secondary_evaluator__department',
        )

    @extend_schema(
        summary='배정 현황 (미배정 대상 포함)',
        parameters=[
            OpenApiParameter('cycle', int, required=True),
            OpenApiParameter('target_type', str, required=True),
            OpenApiParameter('department', int),
            OpenApiParameter('search', str),
        ],
        filters=False,
    )
    @action(detail=False, methods=['get'])
    def overview(self, request):
        cycle_id = request.query_params.get('cycle')
        target_type = request.query_params.get('target_type', TargetType.EMPLOYEE)

        if not cycle_id:
            return Response(
                {'code': 'CYCLE_REQUIRED', 'detail': 'cycle 파라미터가 필요합니다.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cycle = EvaluationCycle.objects.get(pk=cycle_id)
        rows = assignment_service.assignment_overview(
            cycle,
            target_type,
            department=request.query_params.get('department'),
            search=request.query_params.get('search'),
        )
        assigned = sum(1 for row in rows if row['assigned'])
        return Response(
            {
                'count': len(rows),
                'assigned': assigned,
                'unassigned': len(rows) - assigned,
                'results': rows,
            }
        )

    @extend_schema(summary='일괄 배정', request=BulkAssignSerializer)
    @action(detail=False, methods=['post'])
    def bulk(self, request):
        serializer = BulkAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        result = assignment_service.bulk_assign(
            data['cycle'],
            data['target_type'],
            primary_evaluator=data['primary_evaluator'],
            secondary_evaluator=data.get('secondary_evaluator'),
            department=data['department'].pk if data.get('department') else None,
            target_ids=data.get('target_ids'),
            overwrite=data['overwrite'],
        )
        audit.info(
            '[AUDIT] actor=%s action=assignment_bulk cycle=%s created=%s updated=%s',
            request.user.employee_no,
            data['cycle'].name,
            result['created'],
            result['updated'],
        )
        return Response(result)
