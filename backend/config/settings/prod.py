"""운영 환경 설정. Render 배포 기준이다 (specs/12-deploy-render.md)."""

from .base import *  # noqa: F403

DEBUG = False

# 운영에서는 반드시 환경 변수로 주입한다
SECRET_KEY = env('SECRET_KEY')  # noqa: F405

# 공개 서버에 기본 관리자 비밀번호(admin1234!)가 그대로 쓰이지 않도록 기본값을 두지 않는다
DEFAULT_ADMIN_PASSWORD = env('DEFAULT_ADMIN_PASSWORD')  # noqa: F405

ALLOWED_HOSTS = env('ALLOWED_HOSTS')  # noqa: F405
# Render는 서비스의 onrender.com 호스트명을 이 변수로 넣어준다. 헬스체크도 이 Host로 온다
RENDER_EXTERNAL_HOSTNAME = env('RENDER_EXTERNAL_HOSTNAME', default='')  # noqa: F405
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS = [*ALLOWED_HOSTS, RENDER_EXTERNAL_HOSTNAME]

# 프론트엔드(정적 사이트)가 다른 도메인에서 API를 호출한다
CORS_ALLOWED_ORIGINS = env('CORS_ALLOWED_ORIGINS')  # noqa: F405

# DB가 재시작되어도(무료 플랜은 수시로 재시작될 수 있다) 끊긴 연결을 재사용하지 않는다
DATABASES['default']['CONN_MAX_AGE'] = 60  # noqa: F405
DATABASES['default']['CONN_HEALTH_CHECKS'] = True  # noqa: F405

# Django Admin 정적 파일을 gunicorn에서 직접 서빙한다 (별도 웹 서버 없음)
MIDDLEWARE = [  # noqa: F405
    *MIDDLEWARE[:2],  # noqa: F405  corsheaders, SecurityMiddleware
    'whitenoise.middleware.WhiteNoiseMiddleware',
    *MIDDLEWARE[2:],  # noqa: F405
]
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

# 로컬에서 운영 설정을 HTTP로 점검할 때만 끈다
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=True)  # noqa: F405
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
