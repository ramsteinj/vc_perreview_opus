"""E2E 테스트 전용 설정 (specs/11-e2e-testing.md).

개발 설정을 그대로 쓰되, 개발 DB·개발 서버와 섞이지 않도록 전용 DB와 포트를 쓴다.
DB는 tests/scripts/start-backend.sh가 DATABASE_URL로 주입한다.
"""

from .dev import *  # noqa: F403

# E2E는 한 IP(127.0.0.1)에서 수십 번 로그인·내려받기를 하므로
# 운영용 요청 제한(login 30/hour, export 10/hour)을 그대로 두면 테스트가 막힌다.
# 사번 단위 로그인 잠금(LOGIN_ATTEMPT_LIMIT)은 그대로 둔다.
REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    'DEFAULT_THROTTLE_RATES': {
        'login': '100000/hour',
        'export': '100000/hour',
    },
}

CORS_ALLOWED_ORIGINS = ['http://localhost:5174', 'http://127.0.0.1:5174']
