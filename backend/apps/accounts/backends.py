"""커스텀 인증 백엔드 (specs/03-auth.md §1).

로그인은 사번 + 성명 + 비밀번호를 모두 검증한다.
실패 사유는 호출부에 구분해서 알리지 않는다 (사용자 열거 방지).
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmployeeNoNameBackend(ModelBackend):
    def authenticate(self, request, employee_no=None, name=None, password=None, **kwargs):
        if employee_no is None or password is None:
            return None

        user_model = get_user_model()
        try:
            user = user_model.objects.get(employee_no=employee_no)
        except user_model.DoesNotExist:
            # 타이밍 공격 완화: 사용자가 없어도 해시 연산 비용을 동일하게 소모한다
            user_model().set_password(password)
            return None

        if (user.name or '').strip() != (name or '').strip():
            return None

        if not user.check_password(password):
            return None

        if not self.user_can_authenticate(user):
            return None

        return user
