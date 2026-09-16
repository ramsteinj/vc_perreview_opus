import logging

from django.conf import settings
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from . import throttling
from .serializers import ChangePasswordSerializer, LoginSerializer, UserBriefSerializer

audit = logging.getLogger('audit')

INVALID_CREDENTIALS_DETAIL = '성명, 사번 또는 비밀번호가 올바르지 않습니다.'


def issue_tokens(user):
    """access/refresh 토큰을 발급한다. access에 커스텀 클레임을 심는다."""
    refresh = RefreshToken.for_user(user)
    refresh['employee_no'] = user.employee_no
    refresh['name'] = user.name
    refresh['role'] = user.role

    access = refresh.access_token
    access['employee_no'] = user.employee_no
    access['name'] = user.name
    access['role'] = user.role

    return {'access': str(access), 'refresh': str(refresh)}


class LoginView(APIView):
    """성명 + 사번 + 비밀번호 로그인 (specs/03-auth.md §1)."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = 'login'

    @extend_schema(
        summary='로그인',
        tags=['auth'],
        request=LoginSerializer,
        responses={200: UserBriefSerializer},
        auth=[],
        examples=[
            OpenApiExample(
                '로그인 요청',
                value={'name': 'ADMIN', 'employee_no': 'ADMIN', 'password': 'admin1234!'},
                request_only=True,
            )
        ],
    )
    def post(self, request):
        employee_no = str(request.data.get('employee_no', '')).strip()

        if throttling.is_locked(employee_no):
            audit.info('[AUDIT] action=login_blocked employee_no=%s', employee_no)
            return Response(
                {
                    'code': 'TOO_MANY_ATTEMPTS',
                    'detail': '로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요.',
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        serializer = LoginSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            attempts = throttling.record_failure(employee_no)
            audit.info(
                '[AUDIT] action=login_failed employee_no=%s attempts=%s', employee_no, attempts
            )
            if attempts >= settings.LOGIN_ATTEMPT_LIMIT:
                return Response(
                    {
                        'code': 'TOO_MANY_ATTEMPTS',
                        'detail': '로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요.',
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            return Response(
                {'code': 'INVALID_CREDENTIALS', 'detail': INVALID_CREDENTIALS_DETAIL},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = serializer.validated_data['user']
        throttling.reset(employee_no)
        audit.info('[AUDIT] action=login_success employee_no=%s', user.employee_no)

        tokens = issue_tokens(user)
        return Response({**tokens, 'user': UserBriefSerializer(user).data})


class RefreshView(APIView):
    """refresh 토큰으로 access 토큰을 갱신한다."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(summary='토큰 갱신', tags=['auth'], auth=[])
    def post(self, request):
        raw = request.data.get('refresh')
        if not raw:
            return Response(
                {'code': 'TOKEN_REQUIRED', 'detail': 'refresh 토큰이 필요합니다.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            refresh = RefreshToken(raw)
        except TokenError:
            return Response(
                {'code': 'TOKEN_INVALID', 'detail': '세션이 만료되었습니다. 다시 로그인해 주세요.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        data = {'access': str(refresh.access_token)}

        if getattr(settings, 'SIMPLE_JWT', {}).get('ROTATE_REFRESH_TOKENS'):
            if settings.SIMPLE_JWT.get('BLACKLIST_AFTER_ROTATION'):
                try:
                    refresh.blacklist()
                except AttributeError:
                    pass
            from django.contrib.auth import get_user_model

            user_model = get_user_model()
            try:
                user = user_model.objects.get(pk=refresh['user_id'], is_active=True)
            except user_model.DoesNotExist:
                return Response(
                    {
                        'code': 'TOKEN_INVALID',
                        'detail': '세션이 만료되었습니다. 다시 로그인해 주세요.',
                    },
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            data = issue_tokens(user)

        return Response(data)


class LogoutView(APIView):
    """refresh 토큰을 블랙리스트에 등록한다."""

    permission_classes = [IsAuthenticated]

    @extend_schema(summary='로그아웃', tags=['auth'])
    def post(self, request):
        raw = request.data.get('refresh')
        if raw:
            try:
                RefreshToken(raw).blacklist()
            except (TokenError, AttributeError):
                # 이미 만료·폐기된 토큰이면 로그아웃은 성공으로 간주한다
                pass
        audit.info('[AUDIT] action=logout employee_no=%s', request.user.employee_no)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """내 프로필."""

    permission_classes = [IsAuthenticated]

    @extend_schema(summary='내 프로필', tags=['auth'], responses={200: UserBriefSerializer})
    def get(self, request):
        return Response(UserBriefSerializer(request.user).data)


class ChangePasswordView(APIView):
    """내 비밀번호 변경."""

    permission_classes = [IsAuthenticated]

    @extend_schema(summary='비밀번호 변경', tags=['auth'], request=ChangePasswordSerializer)
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        audit.info('[AUDIT] action=change_password employee_no=%s', request.user.employee_no)
        return Response({'detail': '비밀번호가 변경되었습니다.'})
