# 03. 인증 / 인가 / 기본 관리자 부트스트랩

## 1. 로그인 방식

로그인은 **성명 + 사번 + 비밀번호** 세 가지를 모두 요구한다.

```
POST /api/auth/login/
{
  "name": "홍길동",
  "employee_no": "20230101",
  "password": "********"
}
```

### 검증 순서

1. `employee_no`로 사용자를 조회한다. 없으면 실패.
2. `is_active`가 `False`면 실패.
3. `user.name`과 요청의 `name`이 **정확히 일치**하는지 확인한다. 불일치 시 실패.
   - 비교 전 양쪽 모두 `strip()`으로 공백을 제거한다.
   - 대소문자는 구분한다 (한글 성명 기준이므로 실질적 영향 없음).
4. `check_password()`로 비밀번호를 검증한다. 실패 시 실패.

### 실패 응답

어떤 단계에서 실패했는지 **구분하지 않는다.** 사용자 열거(user enumeration)를
막기 위해 모든 실패는 동일한 응답을 반환한다.

```
401 Unauthorized
{ "detail": "성명, 사번 또는 비밀번호가 올바르지 않습니다." }
```

타이밍 공격 완화를 위해, 사용자가 존재하지 않는 경우에도 더미 해시에 대해
`check_password()`를 호출한다 (Django의 `set_unusable_password` 패턴 활용).

### 커스텀 인증 백엔드

```python
# apps/accounts/backends.py
class EmployeeNoNameBackend(ModelBackend):
    def authenticate(self, request, employee_no=None, name=None, password=None, **kwargs):
        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(employee_no=employee_no)
        except UserModel.DoesNotExist:
            UserModel().set_password(password)   # 타이밍 공격 완화
            return None
        if (user.name or '').strip() != (name or '').strip():
            return None
        if not user.check_password(password) or not self.user_can_authenticate(user):
            return None
        return user
```

```python
# settings
AUTHENTICATION_BACKENDS = ['apps.accounts.backends.EmployeeNoNameBackend']
AUTH_USER_MODEL = 'accounts.User'
```

## 2. 토큰 (SimpleJWT)

| 토큰 | 수명 | 저장 위치 |
|------|------|-----------|
| `access` | 30분 | 메모리 (Pinia store) |
| `refresh` | 7일 | `localStorage` |

```python
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}
```

**토큰 페이로드에 포함하는 커스텀 클레임:** `employee_no`, `name`, `role`.
프론트엔드는 이 값으로 초기 UI를 렌더링하되, **권한 판단은 서버가 최종 결정**한다.

로그아웃은 `POST /api/auth/logout/`에서 refresh 토큰을 블랙리스트에 등록한다.
`rest_framework_simplejwt.token_blacklist` 앱을 `INSTALLED_APPS`에 추가한다.

## 3. 비밀번호 정책

- Django 기본 validator 4종 활성화
  (`UserAttributeSimilarity`, `MinimumLength(10)`, `CommonPassword`, `NumericPassword`)
- 최소 10자
- 관리자가 사용자를 생성할 때 초기 비밀번호를 지정하거나, 시스템이 임시 비밀번호를
  생성해 응답으로 1회 반환한다.
- `must_change_password` 플래그는 **1차 범위에 포함하지 않는다.** 필요 시 추가.

## 4. 권한 (Permission)

| 권한 클래스 | 규칙 |
|------------|------|
| `IsAdminRole` | `request.user.role == 'ADMIN'` |
| `IsAuthenticated` | 로그인한 모든 사용자 |
| `IsResponseEvaluator` | 해당 `EvaluationResponse.evaluator == request.user` |

### 엔드포인트별 권한 요약

| 영역 | 직원 | 관리자 |
|------|------|--------|
| 본인 프로필 조회 | O | O |
| 본인에게 배정된 평가 목록 | O | O |
| 본인이 작성한 평가지 읽기/수정 | O | O |
| 타인의 평가지 | X | 읽기 전용 O |
| 사용자/부서/항목/배정 관리 | X | O |
| 응답 현황·점수·CSV | X | O |

**핵심 규칙:** 평가지 조회/수정 API는 `queryset`을 항상
`filter(evaluator=request.user)`로 좁힌다. 객체 단위 권한 검사에만 의존하지 않는다.

## 5. 기본 관리자 계정 부트스트랩

### 요구사항

앱 시작 시 기본 관리자 계정이 없으면 다음 값으로 생성한다.

| 항목 | 값 |
|------|-----|
| 성명 | `ADMIN` |
| 사번 | `ADMIN` |
| 비밀번호 | `admin1234!` |
| role | `ADMIN` |
| is_staff / is_superuser | `True` |

### 구현 방식

`post_migrate` 시그널에서 실행한다. 마이그레이션 파일에 데이터를 넣지 않는 이유는,
비밀번호 해시가 마이그레이션 히스토리에 박제되고 롤백 시 처리가 까다롭기 때문이다.

```python
# apps/accounts/apps.py
class AccountsConfig(AppConfig):
    name = 'apps.accounts'

    def ready(self):
        from django.db.models.signals import post_migrate
        from .bootstrap import create_default_admin
        post_migrate.connect(create_default_admin, sender=self)
```

```python
# apps/accounts/bootstrap.py
def create_default_admin(sender, **kwargs):
    from django.conf import settings
    from django.contrib.auth import get_user_model

    User = get_user_model()
    employee_no = settings.DEFAULT_ADMIN_EMPLOYEE_NO

    if User.objects.filter(role=Role.ADMIN).exists():
        return                      # 관리자가 이미 있으면 아무것도 하지 않는다

    if User.objects.filter(employee_no=employee_no).exists():
        return

    User.objects.create_user(
        employee_no=employee_no,
        name=settings.DEFAULT_ADMIN_NAME,
        password=settings.DEFAULT_ADMIN_PASSWORD,
        role=Role.ADMIN,
        is_staff=True,
        is_superuser=True,
    )
    logger.warning('기본 관리자 계정을 생성했습니다. 최초 로그인 후 비밀번호를 변경하세요.')
```

### 판정 기준

"기본 관리자 계정이 없을 경우"의 판정은 **`role=ADMIN`인 활성 사용자가 하나도
없을 때**로 한다. 관리자가 이미 존재하면(사번이 `ADMIN`이 아니더라도) 생성하지 않는다.
이렇게 하면 운영 중 실수로 기본 계정이 되살아나는 일을 막을 수 있다.

### 별도 관리 명령

시그널 외에 수동 실행용 명령도 제공한다.

```bash
python manage.py create_default_admin [--force]
```

### 보안 주의

- 기본 비밀번호는 `settings`에서 환경 변수로 오버라이드할 수 있어야 한다.
- **운영 환경(`DEBUG=False`)에서 기본 비밀번호가 그대로면 startup 로그에 경고를 남긴다.**
- 최초 로그인 후 비밀번호 변경을 안내하는 배너를 프론트엔드에 노출한다
  (관리자 계정의 비밀번호가 기본값과 일치하는 경우, 서버가 `/api/auth/me/` 응답에
  `password_is_default: true`를 내려준다).

## 6. 로그인 시도 제한

동일 `employee_no`에 대해 **10분 내 5회** 실패 시 10분간 차단한다.
Django 캐시(`locmem` → 운영은 Redis)에 카운터를 둔다. 성공 시 카운터를 초기화한다.

```
429 Too Many Requests
{ "detail": "로그인 시도가 너무 많습니다. 10분 후 다시 시도하세요." }
```
