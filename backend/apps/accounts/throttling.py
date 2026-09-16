"""로그인 시도 제한 (specs/03-auth.md §6).

동일 사번에 대해 LOGIN_ATTEMPT_WINDOW_SECONDS 내
LOGIN_ATTEMPT_LIMIT회 실패하면 남은 윈도우 동안 차단한다.
"""

from django.conf import settings
from django.core.cache import cache

_KEY_PREFIX = 'login-attempt:'


def _key(employee_no):
    return f'{_KEY_PREFIX}{employee_no}'


def is_locked(employee_no):
    if not employee_no:
        return False
    return cache.get(_key(employee_no), 0) >= settings.LOGIN_ATTEMPT_LIMIT


def record_failure(employee_no):
    """실패 횟수를 1 증가시키고 현재 횟수를 반환한다."""
    if not employee_no:
        return 0
    key = _key(employee_no)
    # add()는 키가 없을 때만 설정된다. 이후 incr로 윈도우를 연장하지 않고 누적한다.
    if cache.add(key, 1, timeout=settings.LOGIN_ATTEMPT_WINDOW_SECONDS):
        return 1
    try:
        return cache.incr(key)
    except ValueError:
        # incr 직전에 만료된 경우
        cache.set(key, 1, timeout=settings.LOGIN_ATTEMPT_WINDOW_SECONDS)
        return 1


def reset(employee_no):
    if employee_no:
        cache.delete(_key(employee_no))
