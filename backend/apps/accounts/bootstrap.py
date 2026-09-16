"""기본 관리자 계정 부트스트랩 (specs/03-auth.md §5).

판정 기준: role=ADMIN인 활성 사용자가 하나도 없을 때만 생성한다.
관리자가 이미 있으면(사번이 ADMIN이 아니더라도) 아무것도 하지 않는다.
"""

import logging

logger = logging.getLogger(__name__)


def create_default_admin(sender=None, **kwargs):
    from django.conf import settings
    from django.contrib.auth import get_user_model

    from .models import Role

    user_model = get_user_model()
    employee_no = settings.DEFAULT_ADMIN_EMPLOYEE_NO

    if user_model.objects.filter(role=Role.ADMIN, is_active=True).exists():
        return None

    if user_model.objects.filter(employee_no=employee_no).exists():
        logger.info('사번 %s 계정이 이미 존재하여 기본 관리자를 생성하지 않습니다.', employee_no)
        return None

    admin = user_model.objects.create_user(
        employee_no=employee_no,
        name=settings.DEFAULT_ADMIN_NAME,
        password=settings.DEFAULT_ADMIN_PASSWORD,
        role=Role.ADMIN,
        is_staff=True,
        is_superuser=True,
    )
    logger.warning(
        '기본 관리자 계정을 생성했습니다 (사번: %s). 최초 로그인 후 비밀번호를 변경하세요.',
        employee_no,
    )
    return admin


def uses_default_password(user):
    """해당 사용자의 비밀번호가 부트스트랩 기본값 그대로인지 확인한다."""
    from django.conf import settings

    from .models import Role

    if user.role != Role.ADMIN:
        return False
    return user.check_password(settings.DEFAULT_ADMIN_PASSWORD)
