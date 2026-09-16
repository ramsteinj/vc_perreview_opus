"""도메인 예외와 공통 오류 응답 형식.

모든 오류 응답은 {code, detail, fields} 형태로 통일한다 (specs/07-api.md §1).
"""

from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler as drf_exception_handler


class DomainError(APIException):
    """상태 충돌 등 예상 가능한 도메인 오류의 베이스."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = '요청을 처리할 수 없는 상태입니다.'
    default_code = 'DOMAIN_ERROR'


class LastAdminError(DomainError):
    default_detail = '마지막 관리자 계정의 권한을 해제하거나 비활성화할 수 없습니다.'
    default_code = 'LAST_ADMIN'


class SelfRoleDowngradeError(DomainError):
    default_detail = '본인의 관리자 권한은 스스로 낮출 수 없습니다.'
    default_code = 'SELF_ROLE_DOWNGRADE'


def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    detail = getattr(exc, 'detail', None)
    code = getattr(exc, 'default_code', 'ERROR')
    fields = {}

    if isinstance(exc, ValidationError):
        code = 'VALIDATION_ERROR'
        if isinstance(detail, dict) and 'code' in detail and 'detail' in detail:
            # 시리얼라이저가 도메인 오류 봉투를 직접 넘긴 경우
            code = _scalar(detail['code'])
            message = _scalar(detail['detail'])
        elif isinstance(detail, dict):
            fields = {k: v for k, v in detail.items() if k != 'detail'}
            message = '입력값을 확인해 주세요.'
        else:
            message = _first_message(detail)
    elif isinstance(detail, dict):
        # 뷰가 {'code': ..., 'detail': ..., ...} 형태를 직접 넘긴 경우 그대로 존중한다
        code = detail.get('code', code)
        message = detail.get('detail', '요청을 처리할 수 없습니다.')
        fields = {k: v for k, v in detail.items() if k not in ('code', 'detail')}
    else:
        message = _first_message(detail)
        code = getattr(detail, 'code', code) or code

    payload = {'code': str(code).upper(), 'detail': str(message)}
    if fields:
        payload['fields'] = fields
    response.data = payload
    return response


def _scalar(value):
    """리스트로 감싸인 메시지를 평탄화한다."""
    if isinstance(value, list | tuple) and value:
        return value[0]
    return value


def _first_message(detail):
    if isinstance(detail, list | tuple) and detail:
        return detail[0]
    return detail if detail else '요청을 처리할 수 없습니다.'
