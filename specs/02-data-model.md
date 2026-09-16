# 02. 데이터 모델

## 1. ERD (논리 구조)

```
Department ──┬──< User (department)
             │
             └──< EvaluatorAssignment (target_department)
                          │
User ──< EvaluatorAssignment (target_user / primary_evaluator / secondary_evaluator)
                          │
EvaluationCycle ──┬──< EvaluationItem
                  ├──< EvaluatorAssignment
                  ├──< EvaluationResponse ──< EvaluationAnswer >── EvaluationItem
                  └──< ScoreResult >── User
```

## 2. 앱 배치

| 앱 | 모델 |
|----|------|
| `accounts` | `Department`, `User` |
| `evaluations` | `EvaluationCycle`, `EvaluationItem`, `EvaluatorAssignment`, `EvaluationResponse`, `EvaluationAnswer` |
| `reports` | `ScoreResult` |

---

## 3. accounts 앱

### 3.1 Department (부서)

| 필드 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `id` | BigAutoField | PK | |
| `code` | CharField(20) | unique, not null | 부서 코드 |
| `name` | CharField(100) | not null | 부서명 |
| `parent` | FK(self) | null, `on_delete=PROTECT`, `related_name='children'` | 상위 부서 (조직도 트리) |
| `is_active` | BooleanField | default=True | 비활성 부서는 신규 배정 대상에서 제외 |
| `created_at` / `updated_at` | DateTimeField | auto | |

- 삭제는 **소프트 삭제**(`is_active=False`)를 기본으로 한다. 소속 직원이나 평가 이력이
  있는 부서는 물리 삭제할 수 없다 (`PROTECT`).
- `parent` 순환 참조는 `clean()`에서 검증한다.

### 3.2 User (사용자 / 직원 / 관리자)

Django는 `AUTH_USER_MODEL`로 **단 하나의 커스텀 사용자 모델**만 지원한다.
따라서 직원과 관리자를 별도 테이블로 나누지 않고, `AbstractUser`를 상속한 단일
`User` 모델에 `role` 필드를 두어 구분한다.

```python
# apps/accounts/models.py
class User(AbstractUser):
    username = None                      # 사용하지 않음
    first_name = None
    last_name = None

    employee_no = models.CharField('사번', max_length=20, unique=True)
    name = models.CharField('성명', max_length=50)
    department = models.ForeignKey(Department, on_delete=models.PROTECT,
                                   null=True, blank=True, related_name='members')
    position = models.CharField('직위', max_length=50, blank=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.EMPLOYEE)
    hired_on = models.DateField('입사일', null=True, blank=True)

    USERNAME_FIELD = 'employee_no'
    REQUIRED_FIELDS = ['name']

    objects = UserManager()
```

| 필드 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `employee_no` | CharField(20) | unique, not null | 사번. `USERNAME_FIELD` |
| `name` | CharField(50) | not null | 성명. 로그인 시 함께 검증 |
| `department` | FK(Department) | null, `PROTECT` | 소속 부서 |
| `position` | CharField(50) | blank | 직위 (예: 팀장, 선임) |
| `role` | CharField(10) | `EMPLOYEE` / `ADMIN` | 시스템 권한 |
| `hired_on` | DateField | null | 입사일 |
| `is_active` | BooleanField | default=True | 퇴사 시 False |
| `is_staff` / `is_superuser` | BooleanField | AbstractUser 상속 | Django Admin 접근용 |
| `password` | CharField | AbstractUser 상속 | PBKDF2 해시 |
| `date_joined` / `last_login` | DateTimeField | AbstractUser 상속 | |

**제거하는 상속 필드:** `username`, `first_name`, `last_name` (`= None`으로 비활성)
— 한국식 성명은 분리하지 않고 `name` 단일 필드를 사용한다.

**`role`과 `is_staff` 관계:** `role=ADMIN`으로 저장할 때 `is_staff=True`를 함께
설정한다 (`save()` 오버라이드). `is_superuser`는 별도로 관리한다.

**커스텀 매니저 (`managers.py`):**

```python
class UserManager(BaseUserManager):
    def create_user(self, employee_no, name, password=None, **extra):
        if not employee_no:
            raise ValueError('사번은 필수입니다.')
        user = self.model(employee_no=employee_no, name=name, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, employee_no, name, password=None, **extra):
        extra.setdefault('role', Role.ADMIN)
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        return self.create_user(employee_no, name, password, **extra)
```

**삭제 정책:** 평가 이력이 있는 사용자는 물리 삭제하지 않고 `is_active=False`로
비활성화한다. API의 `DELETE`는 소프트 삭제로 동작한다. (05-admin-features.md §2.3)

---

## 4. evaluations 앱

### 4.1 EvaluationCycle (평가 회차)

| 필드 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `id` | BigAutoField | PK | |
| `name` | CharField(100) | not null | 예: "2026년 상반기 평가" |
| `year` | PositiveSmallIntegerField | not null | 평가 연도 |
| `starts_on` | DateField | not null | 응답 시작일 |
| `ends_on` | DateField | not null | 응답 마감일 |
| `status` | CharField(10) | `DRAFT` / `OPEN` / `CLOSED` | 회차 상태 |
| `primary_weight` | DecimalField(5,2) | default=70.00 | 1차 평가자 반영 비율(%) |
| `secondary_weight` | DecimalField(5,2) | default=30.00 | 2차 평가자 반영 비율(%) |
| `dept_baseline_score` | DecimalField(5,2) | default=70.00 | 부서 가감 기준점 |
| `dept_adjust_factor` | DecimalField(5,2) | default=0.20 | 부서 가감 계수 |
| `dept_adjust_limit` | DecimalField(5,2) | default=10.00 | 부서 가감 상·하한 (±) |
| `created_at` / `updated_at` | DateTimeField | auto | |

- 제약: `starts_on <= ends_on`, `primary_weight + secondary_weight == 100`
- 상태 전이: `DRAFT → OPEN → CLOSED`. 역방향은 관리자만 가능하며 감사 로그를 남긴다.
- **`OPEN` 상태에서만** 직원이 응답을 작성/제출할 수 있다.
- **`CLOSED` 상태에서만** 최종 점수를 확정 산출한다.
- 가중치/계수 필드의 의미와 계산식은 [06-scoring.md](06-scoring.md) 참조.

### 4.2 EvaluationItem (평가 항목)

| 필드 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `id` | BigAutoField | PK | |
| `cycle` | FK(EvaluationCycle) | `CASCADE`, `related_name='items'` | 소속 회차 |
| `target_type` | CharField(12) | `EMPLOYEE` / `DEPARTMENT` | 개인 평가 항목 / 부서 평가 항목 |
| `code` | CharField(30) | not null | 항목 코드 |
| `title` | CharField(200) | not null | 문항 제목 |
| `description` | TextField | blank | 평가 기준 설명 |
| `weight` | DecimalField(5,2) | > 0 | 가중치(%) |
| `max_score` | PositiveSmallIntegerField | default=5 | 척도 상한 (5점 척도 기본) |
| `order` | PositiveIntegerField | default=0 | 표시 순서 |
| `is_active` | BooleanField | default=True | |

- `UniqueConstraint(cycle, target_type, code)`
- **가중치 합계 규칙:** 동일 `cycle` + `target_type`의 활성 항목 `weight` 합계는
  정확히 `100.00`이어야 한다. 회차를 `OPEN`으로 전이할 때 검증하며, 불일치 시 거부한다.
  (편집 중에는 합계가 100이 아니어도 저장 가능)
- 응답이 하나라도 존재하는 항목은 `weight`/`max_score` 변경과 삭제를 차단한다.
  변경이 필요하면 회차를 복제해 새 회차를 만든다.

### 4.3 EvaluatorAssignment (평가자 배정)

부서 또는 직원 1건에 대해 1차/2차 평가자를 지정한다.

| 필드 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `id` | BigAutoField | PK | |
| `cycle` | FK(EvaluationCycle) | `CASCADE` | |
| `target_type` | CharField(12) | `EMPLOYEE` / `DEPARTMENT` | 평가 대상 유형 |
| `target_user` | FK(User) | null, `PROTECT`, `related_name='as_target'` | `target_type=EMPLOYEE`일 때 필수 |
| `target_department` | FK(Department) | null, `PROTECT` | `target_type=DEPARTMENT`일 때 필수 |
| `primary_evaluator` | FK(User) | not null, `PROTECT`, `related_name='primary_assignments'` | 1차 평가자 (필수) |
| `secondary_evaluator` | FK(User) | null, `PROTECT`, `related_name='secondary_assignments'` | 2차 평가자 (선택) |
| `created_at` / `updated_at` | DateTimeField | auto | |

**제약 조건:**

- `UniqueConstraint(cycle, target_type, target_user)` — `target_user` not null 조건부
- `UniqueConstraint(cycle, target_type, target_department)` — `target_department` not null 조건부
- `CheckConstraint`: `target_type=EMPLOYEE`면 `target_user` not null & `target_department` null,
  `target_type=DEPARTMENT`면 그 반대
- `clean()` 검증: `primary_evaluator != secondary_evaluator`
- `clean()` 검증: `target_type=EMPLOYEE`일 때 `primary_evaluator != target_user`
  (본인이 본인을 평가할 수 없음)

### 4.4 EvaluationResponse (평가지)

평가자 1명이 대상 1개에 대해 작성하는 응답지 한 장. **중복 응답 방지의 단위.**

| 필드 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `id` | BigAutoField | PK | |
| `assignment` | FK(EvaluatorAssignment) | `CASCADE`, `related_name='responses'` | |
| `evaluator` | FK(User) | `PROTECT`, `related_name='responses'` | 작성자 |
| `round` | CharField(10) | `PRIMARY` / `SECONDARY` | 1차 / 2차 |
| `status` | CharField(10) | `DRAFT` / `SUBMITTED` | |
| `submitted_at` | DateTimeField | null | 제출 시각 |
| `overall_comment` | TextField | blank | 종합 의견 |
| `created_at` / `updated_at` | DateTimeField | auto | |

**제약 조건:**

- `UniqueConstraint(assignment, round)` — **중복 응답 방지의 핵심.**
  하나의 배정·차수 조합에 평가지는 단 하나만 존재한다.
- `evaluator`는 `assignment`의 해당 차수 평가자와 일치해야 한다 (Service에서 검증).
- `status=SUBMITTED`인 평가지는 수정할 수 없다. 관리자가 반려(`reopen`)하면
  `DRAFT`로 되돌아가고 `submitted_at`은 `null`로 초기화된다.

### 4.5 EvaluationAnswer (항목별 답변)

| 필드 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `id` | BigAutoField | PK | |
| `response` | FK(EvaluationResponse) | `CASCADE`, `related_name='answers'` | |
| `item` | FK(EvaluationItem) | `PROTECT` | |
| `score` | PositiveSmallIntegerField | null | 1 ~ `item.max_score` |
| `comment` | TextField | blank | 항목별 의견 |
| `updated_at` | DateTimeField | auto | |

- `UniqueConstraint(response, item)`
- `score`는 임시 저장 중에는 `null`을 허용한다. **제출 시점에는 모든 활성 항목의
  `score`가 채워져 있어야 한다.**
- `item.cycle`은 `response.assignment.cycle`과 같아야 한다 (Service 검증).
- `item.target_type`은 `response.assignment.target_type`과 같아야 한다.

---

## 5. reports 앱

### 5.1 ScoreResult (산출된 점수 스냅샷)

회차 마감 후 산출한 최종 점수를 저장한다. 계산 결과를 캐싱하고 이력을 보존하는 목적.

| 필드 | 타입 | 제약 | 설명 |
|------|------|------|------|
| `id` | BigAutoField | PK | |
| `cycle` | FK(EvaluationCycle) | `CASCADE` | |
| `user` | FK(User) | `PROTECT` | 피평가자 |
| `department` | FK(Department) | null, `PROTECT` | 산출 시점의 소속 부서 (스냅샷) |
| `primary_score` | DecimalField(6,2) | null | 1차 평가지 환산 점수 (0~100) |
| `secondary_score` | DecimalField(6,2) | null | 2차 평가지 환산 점수 (0~100) |
| `individual_score` | DecimalField(6,2) | not null | 개인 평가 점수 (0~100) |
| `department_score` | DecimalField(6,2) | null | 부서 성과 점수 (0~100) |
| `department_adjustment` | DecimalField(6,2) | default=0 | 부서 가감값 (±) |
| `final_score` | DecimalField(6,2) | not null | 최종 점수 (0~100) |
| `calculated_at` | DateTimeField | auto_now | 산출 시각 |

- `UniqueConstraint(cycle, user)`
- 재계산 시 기존 레코드를 갱신한다 (`update_or_create`).
- 계산식은 [06-scoring.md](06-scoring.md) 참조.

---

## 6. 공통 규약

- 모든 모델은 `created_at`(`auto_now_add`), `updated_at`(`auto_now`)을 갖는
  `TimeStampedModel` 추상 베이스를 상속한다 (`ScoreResult`는 예외).
- 모든 FK는 `on_delete`를 명시한다. 이력 보존이 필요한 관계는 `PROTECT`,
  종속 데이터는 `CASCADE`.
- 금액/점수는 `FloatField`가 아닌 `DecimalField`를 사용한다.
- 선택지(choices)는 `models.TextChoices`로 정의한다.

```python
class Role(models.TextChoices):
    EMPLOYEE = 'EMPLOYEE', '직원'
    ADMIN = 'ADMIN', '관리자'

class TargetType(models.TextChoices):
    EMPLOYEE = 'EMPLOYEE', '개인'
    DEPARTMENT = 'DEPARTMENT', '부서'

class EvaluationRound(models.TextChoices):
    PRIMARY = 'PRIMARY', '1차'
    SECONDARY = 'SECONDARY', '2차'

class ResponseStatus(models.TextChoices):
    DRAFT = 'DRAFT', '임시저장'
    SUBMITTED = 'SUBMITTED', '제출완료'

class CycleStatus(models.TextChoices):
    DRAFT = 'DRAFT', '준비중'
    OPEN = 'OPEN', '진행중'
    CLOSED = 'CLOSED', '마감'
```

## 7. 인덱스

```python
# EvaluationResponse
indexes = [
    models.Index(fields=['evaluator', 'status']),      # 내 평가 목록 조회
    models.Index(fields=['assignment', 'round']),
]
# EvaluatorAssignment
indexes = [
    models.Index(fields=['cycle', 'target_type']),
    models.Index(fields=['primary_evaluator']),
    models.Index(fields=['secondary_evaluator']),
]
# ScoreResult
indexes = [models.Index(fields=['cycle', 'department'])]
```
