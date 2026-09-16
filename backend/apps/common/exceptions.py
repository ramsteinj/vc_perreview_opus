"""도메인 예외와 공통 오류 응답 형식.

모든 오류 응답은 {code, detail} 형태로 통일한다 (specs/07-api.md §1).
필드별 검증 오류는 `fields`에, 도메인 오류의 추가 맥락(missing_items, unassigned 등)은
최상위 키로 싣는다.
"""

from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler as drf_exception_handler


class DomainError(APIException):
    """상태 충돌 등 예상 가능한 도메인 오류의 베이스.

    `context`는 응답 최상위에 그대로 실린다. DRF는 `detail`의 모든 말단 값을
    ErrorDetail(str 하위 클래스)로 감싸므로, 숫자·리스트 구조를 보존해야 하는
    추가 맥락(item_count, unassigned 등)은 detail이 아니라 context로 전달한다.
    """

    status_code = status.HTTP_409_CONFLICT
    default_detail = '요청을 처리할 수 없는 상태입니다.'
    default_code = 'DOMAIN_ERROR'

    def __init__(self, detail=None, code=None, context=None):
        super().__init__(detail, code)
        self.context = dict(context) if context else {}


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
    extra = {}

    if isinstance(exc, ValidationError):
        code = 'VALIDATION_ERROR'
        if _is_domain_envelope(detail):
            # 시리얼라이저가 도메인 오류 봉투를 직접 넘긴 경우
            code = _scalar(detail['code'])
            message = _scalar(detail['detail'])
            extra = _extra_context(detail)
        elif isinstance(detail, dict):
            fields = {k: v for k, v in detail.items() if k != 'detail'}
            message = '입력값을 확인해 주세요.'
        else:
            message = _first_message(detail)
    elif isinstance(detail, dict):
        # 뷰/서비스가 {'code': ..., 'detail': ..., ...} 형태를 넘긴 경우
        code = detail.get('code', code)
        message = detail.get('detail', '요청을 처리할 수 없습니다.')
        extra = _extra_context(detail)
    else:
        message = _first_message(detail)
        code = getattr(detail, 'code', code) or code

    # DomainError.context는 DRF를 거치지 않으므로 원래 자료형이 유지된다
    extra = {**extra, **getattr(exc, 'context', {})}

    payload = {'code': str(code).upper(), 'detail': str(message)}
    if fields:
        payload['fields'] = fields
    payload.update(extra)
    response.data = payload
    return response


def _is_domain_envelope(detail):
    return isinstance(detail, dict) and 'code' in detail and 'detail' in detail


def _extra_context(detail):
    """code/detail 외의 키를 최상위 맥락으로 되돌린다 (DRF가 감싼 리스트를 벗긴다)."""
    return {key: _unwrap(value) for key, value in detail.items() if key not in ('code', 'detail')}


def _unwrap(value):
    """DRF ErrorDetail 래핑을 풀어 원래 자료구조로 되돌린다."""
    if isinstance(value, list | tuple):
        return [_unwrap(v) for v in value]
    if isinstance(value, dict):
        return {k: _unwrap(v) for k, v in value.items()}
    if isinstance(value, str):
        return str(value)
    return value


def _scalar(value):
    """리스트로 감싸인 메시지를 평탄화한다."""
    if isinstance(value, list | tuple) and value:
        return value[0]
    return value


def _first_message(detail):
    if isinstance(detail, list | tuple) and detail:
        return detail[0]
    return detail if detail else '요청을 처리할 수 없습니다.'
