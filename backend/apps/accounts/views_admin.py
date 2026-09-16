"""관리자용 부서/사용자 관리 API (specs/05-admin-features.md FR-A-02, FR-A-03)."""

import logging

from django.db.models import Count, ProtectedError
from django.db.models.deletion import RestrictedError
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .filters import DepartmentFilter, UserFilter
from .models import Department, Role, User
from .permissions import IsAdminRole
from .serializers_admin import (
    AdminUserCreateSerializer,
    AdminUserListSerializer,
    AdminUserUpdateSerializer,
    DepartmentSerializer,
    DepartmentTreeSerializer,
    ResetPasswordSerializer,
)
from .services import generate_temporary_password, is_last_active_admin

audit = logging.getLogger('audit')


@extend_schema(tags=['admin:departments'])
class DepartmentViewSet(viewsets.ModelViewSet):
    """부서 CRUD. 삭제는 기본이 비활성화(소프트 삭제)다."""

    serializer_class = DepartmentSerializer
    permission_classes = [IsAdminRole]
    filterset_class = DepartmentFilter
    search_fields = ['code', 'name']
    ordering_fields = ['code', 'name', 'created_at']
    ordering = ['code']

    def get_queryset(self):
        return (
            Department.objects.select_related('parent')
            .annotate(member_count=Count('members', distinct=True))
            .annotate(child_count=Count('children', distinct=True))
        )

    @extend_schema(
        summary='부서 목록',
        parameters=[
            OpenApiParameter(
                'tree',
                bool,
                description='true면 계층 구조로 반환한다 (페이지네이션 없음).',
            )
        ],
    )
    def list(self, request, *args, **kwargs):
        if request.query_params.get('tree') != 'true':
            return super().list(request, *args, **kwargs)

        # 트리는 단일 쿼리로 모두 읽어와 메모리에서 조립한다 (N+1 방지)
        departments = list(self.filter_queryset(self.get_queryset()))

        children_map = {}
        for dept in departments:
            children_map.setdefault(dept.parent_id, []).append(dept)

        roots = children_map.get(None, [])
        serializer = DepartmentTreeSerializer(
            roots, many=True, context={'children_map': children_map, 'request': request}
        )
        return Response({'count': len(departments), 'results': serializer.data})

    @extend_schema(summary='부서 생성')
    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        audit.info(
            '[AUDIT] actor=%s action=department_create target=%s',
            request.user.employee_no,
            response.data.get('code'),
        )
        return response

    @extend_schema(
        summary='부서 삭제',
        description=(
            '기본은 비활성화(소프트 삭제)다. 하위 부서나 소속 직원이 없는 경우에 한해 '
            '`?hard=true`로 물리 삭제할 수 있다.'
        ),
        parameters=[OpenApiParameter('hard', bool, description='물리 삭제 여부')],
    )
    def destroy(self, request, *args, **kwargs):
        department = self.get_object()
        hard = request.query_params.get('hard') == 'true'

        has_children = department.children.exists()
        has_members = department.members.exists()

        if hard:
            if has_children or has_members:
                return Response(
                    {
                        'code': 'DEPARTMENT_IN_USE',
                        'detail': '하위 부서나 소속 직원이 있어 삭제할 수 없습니다. 비활성화하세요.',
                        'child_count': department.children.count(),
                        'member_count': department.members.count(),
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            try:
                department.delete()
            except (ProtectedError, RestrictedError):
                return Response(
                    {
                        'code': 'DEPARTMENT_IN_USE',
                        'detail': '이 부서를 참조하는 데이터가 있어 삭제할 수 없습니다.',
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            audit.info(
                '[AUDIT] actor=%s action=department_hard_delete target=%s',
                request.user.employee_no,
                department.code,
            )
            return Response(status=status.HTTP_204_NO_CONTENT)

        department.is_active = False
        department.save(update_fields=['is_active', 'updated_at'])
        audit.info(
            '[AUDIT] actor=%s action=department_deactivate target=%s',
            request.user.employee_no,
            department.code,
        )
        return Response(
            {
                'id': department.id,
                'code': department.code,
                'is_active': False,
                'detail': '부서를 비활성화했습니다.',
            }
        )


@extend_schema(tags=['admin:users'])
class AdminUserViewSet(viewsets.ModelViewSet):
    """사용자 CRUD. 삭제는 기본이 비활성화(소프트 삭제)다."""

    permission_classes = [IsAdminRole]
    filterset_class = UserFilter
    search_fields = ['employee_no', 'name']
    ordering_fields = ['employee_no', 'name', 'hired_on', 'date_joined', 'last_login']
    ordering = ['employee_no']

    def get_queryset(self):
        return User.objects.select_related('department')

    def get_serializer_class(self):
        if self.action == 'create':
            return AdminUserCreateSerializer
        if self.action in ('update', 'partial_update'):
            return AdminUserUpdateSerializer
        return AdminUserListSerializer

    @extend_schema(
        summary='사용자 생성',
        description='password를 생략하면 임시 비밀번호를 생성해 응답에 1회만 포함한다.',
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        audit.info(
            '[AUDIT] actor=%s action=user_create target=%s',
            request.user.employee_no,
            user.employee_no,
        )

        data = AdminUserListSerializer(user).data
        generated = getattr(user, '_generated_password', None)
        if generated:
            data['generated_password'] = generated
            data['generated_password_notice'] = (
                '이 비밀번호는 지금만 확인할 수 있습니다. 사용자에게 안전하게 전달하세요.'
            )
        return Response(data, status=status.HTTP_201_CREATED)

    @extend_schema(summary='사용자 수정')
    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        audit.info(
            '[AUDIT] actor=%s action=user_update target=%s',
            request.user.employee_no,
            response.data.get('employee_no'),
        )
        return response

    @extend_schema(
        summary='사용자 삭제(비활성화)',
        description='기본은 비활성화다. 평가 이력이 없는 사용자만 `?hard=true`로 물리 삭제된다.',
        parameters=[OpenApiParameter('hard', bool, description='물리 삭제 여부')],
    )
    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        hard = request.query_params.get('hard') == 'true'

        if is_last_active_admin(user):
            return Response(
                {
                    'code': 'LAST_ADMIN',
                    'detail': '마지막 관리자 계정은 비활성화할 수 없습니다.',
                },
                status=status.HTTP_409_CONFLICT,
            )

        if hard:
            employee_no = user.employee_no
            try:
                user.delete()
            except (ProtectedError, RestrictedError):
                # 평가 이력이 있으면 FK PROTECT가 삭제를 막는다 → 비활성화로 대체
                return Response(
                    {
                        'code': 'USER_IN_USE',
                        'detail': '평가 이력이 있어 삭제할 수 없습니다. 비활성화하세요.',
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            audit.info(
                '[AUDIT] actor=%s action=user_hard_delete target=%s',
                request.user.employee_no,
                employee_no,
            )
            return Response(status=status.HTTP_204_NO_CONTENT)

        user.is_active = False
        user.save(update_fields=['is_active'])
        audit.info(
            '[AUDIT] actor=%s action=user_deactivate target=%s',
            request.user.employee_no,
            user.employee_no,
        )
        return Response(
            {
                'id': user.id,
                'employee_no': user.employee_no,
                'is_active': False,
                'detail': '사용자를 비활성화했습니다.',
            }
        )

    @extend_schema(
        summary='비밀번호 초기화',
        request=ResetPasswordSerializer,
        description='password를 생략하면 임시 비밀번호를 생성해 응답에 1회만 포함한다.',
    )
    @action(detail=True, methods=['post'], url_path='reset-password')
    def reset_password(self, request, pk=None):
        user = self.get_object()
        serializer = ResetPasswordSerializer(
            data=request.data, context={'request': request, 'target_user': user}
        )
        serializer.is_valid(raise_exception=True)

        password = serializer.validated_data.get('password')
        generated = False
        if not password:
            password = generate_temporary_password(user)
            generated = True

        user.set_password(password)
        user.save(update_fields=['password'])

        audit.info(
            '[AUDIT] actor=%s action=user_reset_password target=%s',
            request.user.employee_no,
            user.employee_no,
        )

        data = {
            'id': user.id,
            'employee_no': user.employee_no,
            'detail': '비밀번호를 초기화했습니다.',
        }
        if generated:
            data['generated_password'] = password
            data['generated_password_notice'] = (
                '이 비밀번호는 지금만 확인할 수 있습니다. 사용자에게 안전하게 전달하세요.'
            )
        return Response(data)

    @extend_schema(summary='사용자 활성화')
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=['is_active'])
        audit.info(
            '[AUDIT] actor=%s action=user_activate target=%s',
            request.user.employee_no,
            user.employee_no,
        )
        return Response(AdminUserListSerializer(user).data)

    @extend_schema(summary='선택 항목용 사용자 요약 목록', filters=False)
    @action(detail=False, methods=['get'])
    def options(self, request):
        """평가자 선택 등에 쓰는 경량 목록. 페이지네이션 없이 활성 사용자만 반환한다."""
        queryset = (
            User.objects.filter(is_active=True)
            .select_related('department')
            .order_by('name', 'employee_no')
        )
        search = request.query_params.get('search')
        if search:
            from django.db.models import Q

            queryset = queryset.filter(Q(name__icontains=search) | Q(employee_no__icontains=search))

        return Response(
            [
                {
                    'id': u.id,
                    'employee_no': u.employee_no,
                    'name': u.name,
                    'department_name': u.department.name if u.department else None,
                    'role': u.role,
                }
                for u in queryset[:200]
            ]
        )


# Role choices를 프론트엔드가 하드코딩하지 않도록 노출한다
@extend_schema(tags=['admin:users'], summary='사용자 역할 목록')
class RoleChoicesView(viewsets.ViewSet):
    permission_classes = [IsAdminRole]

    def list(self, request):
        return Response([{'value': v, 'label': label} for v, label in Role.choices])
