from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@extend_schema(summary='헬스체크', tags=['system'], auth=[])
@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        db_status = 'ok'
    except Exception:  # noqa: BLE001 - 헬스체크는 원인과 무관하게 down으로 보고한다
        db_status = 'down'
    return Response({'status': 'ok', 'db': db_status})
