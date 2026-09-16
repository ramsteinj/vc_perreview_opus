# 07. REST API 명세

**Base URL:** `/api`
**인증:** `Authorization: Bearer <access_token>` (로그인·토큰 갱신 제외)
**Content-Type:** `application/json` (CSV 내보내기 제외)

## 1. 공통 규약

### 응답 형식

목록 응답은 DRF 페이지네이션 형식을 따른다.

```json
{ "count": 128, "next": "...?page=2", "previous": null, "results": [ ... ] }
```

### 오류 형식

```json
{ "code": "ALREADY_SUBMITTED", "detail": "이미 제출된 평가입니다.", "fields": {} }
```

| 상태 | 의미 |
|------|------|
| 400 | 검증 실패 (`fields`에 필드별 오류) |
| 401 | 미인증 / 토큰 만료 |
| 403 | 권한 없음 |
| 404 | 대상 없음 (권한 없는 리소스도 404로 숨김 처리 가능) |
| 409 | 상태 충돌 (중복 제출, 회차 마감 등) |
| 429 | 요청 제한 초과 |

### 공통 오류 코드

`ALREADY_SUBMITTED`, `INCOMPLETE_ANSWERS`, `CYCLE_NOT_OPEN`, `CYCLE_DEADLINE_PASSED`,
`WEIGHT_SUM_INVALID`, `ITEM_IN_USE`, `EVALUATOR_DUPLICATE`, `SELF_EVALUATION`,
`LAST_ADMIN`, `NO_ACTIVE_ITEMS`

### 공통 쿼리 파라미터

| 파라미터 | 설명 |
|----------|------|
| `page`, `page_size` | 페이지네이션 (기본 25, 최대 200) |
| `ordering` | 정렬 (`-final_score` 형식) |
| `search` | 검색 |

---

## 2. 인증 (`/api/auth`)

| Method | Path | 권한 | 설명 |
|--------|------|------|------|
| POST | `/auth/login/` | AllowAny | 성명+사번+비밀번호 로그인 |
| POST | `/auth/refresh/` | AllowAny | access 토큰 갱신 |
| POST | `/auth/logout/` | 인증 | refresh 토큰 블랙리스트 등록 |
| GET | `/auth/me/` | 인증 | 내 프로필 |
| POST | `/auth/change-password/` | 인증 | 내 비밀번호 변경 |

### POST `/auth/login/`

```json
// Request
{ "name": "홍길동", "employee_no": "20230101", "password": "********" }

// 200
{
  "access": "eyJ...",
  "refresh": "eyJ...",
  "user": {
    "id": 7, "employee_no": "20230101", "name": "홍길동",
    "role": "EMPLOYEE", "department": { "id": 3, "name": "개발1팀" },
    "password_is_default": false
  }
}

// 401
{ "code": "INVALID_CREDENTIALS", "detail": "성명, 사번 또는 비밀번호가 올바르지 않습니다." }
```

---

## 3. 직원용 (`/api/my`)

| Method | Path | 설명 |
|--------|------|------|
| GET | `/my/assignments/` | 내가 평가자로 배정된 목록 (진행 중 회차) |
| GET | `/my/responses/{id}/` | 평가지 상세 (항목 + 내 답변) |
| POST | `/my/responses/` | 평가지 생성 (최초 진입 시) |
| PUT | `/my/responses/{id}/` | 임시 저장 (부분 저장 허용, upsert) |
| POST | `/my/responses/{id}/submit/` | 제출 |

### GET `/my/assignments/`

```json
{
  "cycle": { "id": 3, "name": "2026년 상반기 평가",
             "ends_on": "2026-09-30", "status": "OPEN" },
  "summary": { "total": 7, "submitted": 3, "draft": 2, "not_started": 2 },
  "results": [
    {
      "assignment_id": 41,
      "round": "PRIMARY",
      "target_type": "EMPLOYEE",
      "target": { "id": 12, "name": "김철수",
                  "employee_no": "20210133", "department_name": "개발1팀" },
      "response_id": 88,
      "status": "DRAFT",
      "progress": 67,
      "answered_count": 2,
      "total_items": 3,
      "submitted_at": null,
      "editable": true
    }
  ]
}
```

`response_id`가 `null`이면 아직 작성을 시작하지 않은 상태다.
클라이언트는 `POST /my/responses/`로 평가지를 먼저 생성한다.

### POST `/my/responses/`

```json
// Request
{ "assignment": 41, "round": "PRIMARY" }

// 201 — 이미 존재하면 기존 평가지를 200으로 반환한다 (get_or_create)
{ "id": 88, "status": "DRAFT", "progress": 0, ... }
```

### GET `/my/responses/{id}/`

```json
{
  "id": 88,
  "round": "PRIMARY",
  "status": "DRAFT",
  "editable": true,
  "progress": 67,
  "answered_count": 2,
  "total_items": 3,
  "overall_comment": "",
  "submitted_at": null,
  "updated_at": "2026-09-16T14:32:11Z",
  "cycle": { "id": 3, "name": "2026년 상반기 평가", "ends_on": "2026-09-30" },
  "target": { "name": "김철수", "employee_no": "20210133",
              "department_name": "개발1팀" },
  "items": [
    { "id": 1, "code": "PERF", "title": "업무 성과",
      "description": "업무 목표 달성도와 산출물의 품질",
      "weight": "50.00", "max_score": 5, "order": 1,
      "answer": { "score": 4, "comment": "" } },
    { "id": 3, "code": "ATTITUDE", "title": "태도",
      "weight": "20.00", "max_score": 5, "order": 3,
      "answer": { "score": null, "comment": "" } }
  ]
}
```

### PUT `/my/responses/{id}/` (임시 저장)

```json
// Request — 전달된 항목만 upsert. score: null 허용
{
  "answers": [
    { "item": 1, "score": 4, "comment": "" },
    { "item": 3, "score": null, "comment": "" }
  ],
  "overall_comment": "전반적으로 우수합니다."
}

// 200
{ "id": 88, "status": "DRAFT", "progress": 67,
  "answered_count": 2, "total_items": 3, "updated_at": "..." }

// 409 — 이미 제출됨 / 회차 마감
{ "code": "ALREADY_SUBMITTED", "detail": "이미 제출된 평가입니다." }
```

### POST `/my/responses/{id}/submit/`

```json
// 200
{ "id": 88, "status": "SUBMITTED", "progress": 100,
  "submitted_at": "2026-09-16T14:40:02Z" }

// 400
{ "code": "INCOMPLETE_ANSWERS", "detail": "응답하지 않은 항목이 있습니다.",
  "missing_items": [3] }

// 409
{ "code": "ALREADY_SUBMITTED", "detail": "이미 제출된 평가입니다." }
```

---

## 4. 관리자 — 마스터 데이터 (`/api/admin`)

| Method | Path | 설명 |
|--------|------|------|
| GET/POST | `/admin/departments/` | 부서 목록(`?tree=true`)/생성 |
| GET/PATCH/DELETE | `/admin/departments/{id}/` | 부서 상세/수정/삭제(소프트) |
| GET/POST | `/admin/users/` | 사용자 목록/생성 |
| GET/PATCH/DELETE | `/admin/users/{id}/` | 사용자 상세/수정/비활성화 |
| POST | `/admin/users/{id}/reset-password/` | 비밀번호 초기화 |
| POST | `/admin/users/bulk-import/` | CSV 일괄 등록 (multipart) |

### GET `/admin/users/`

쿼리: `?search=홍길동&department=3&role=EMPLOYEE&is_active=true&ordering=employee_no`

---

## 5. 관리자 — 평가 설정 (`/api/admin`)

| Method | Path | 설명 |
|--------|------|------|
| GET/POST | `/admin/cycles/` | 회차 목록/생성 |
| GET/PATCH | `/admin/cycles/{id}/` | 회차 상세/수정 |
| POST | `/admin/cycles/{id}/open/` | `OPEN` 전이 (`?confirm=true`) |
| POST | `/admin/cycles/{id}/close/` | `CLOSED` 전이 + 자동 산출 |
| POST | `/admin/cycles/{id}/clone-items/` | 다른 회차의 항목 복제 |
| GET/POST | `/admin/items/` | 평가 항목 목록/생성 (`?cycle=3&target_type=EMPLOYEE`) |
| GET/PATCH/DELETE | `/admin/items/{id}/` | 항목 상세/수정/삭제 |
| POST | `/admin/items/reorder/` | 순서 일괄 변경 |
| GET | `/admin/items/weight-check/` | 가중치 합계 검증 (`?cycle=3`) |
| GET/POST | `/admin/assignments/` | 평가자 배정 목록/생성 |
| GET/PATCH/DELETE | `/admin/assignments/{id}/` | 배정 상세/수정/삭제 |
| POST | `/admin/assignments/bulk/` | 일괄 배정 |

### GET `/admin/items/weight-check/?cycle=3`

```json
{
  "EMPLOYEE":   { "sum": "100.00", "valid": true,  "item_count": 3 },
  "DEPARTMENT": { "sum": "95.00",  "valid": false, "item_count": 4 }
}
```

### POST `/admin/assignments/`

```json
{
  "cycle": 3,
  "target_type": "EMPLOYEE",
  "target_user": 12,
  "primary_evaluator": 5,
  "secondary_evaluator": 2      // 생략 또는 null 허용
}
```

### POST `/admin/assignments/bulk/`

```json
{
  "cycle": 3,
  "target_type": "EMPLOYEE",
  "department": 3,               // 이 부서 전원 대상
  "primary_evaluator": 5,
  "secondary_evaluator": null,
  "overwrite": false             // true면 기존 배정 덮어쓰기
}
```

---

## 6. 관리자 — 현황 / 점수 / 내보내기

| Method | Path | 설명 |
|--------|------|------|
| GET | `/admin/cycles/{id}/status/summary/` | 응답 현황 요약 |
| GET | `/admin/cycles/{id}/status/detail/` | 응답 현황 상세 |
| GET | `/admin/cycles/{id}/status/pending/` | 미응답자 목록 |
| GET | `/admin/responses/{id}/` | 타인 평가지 열람 (읽기 전용) |
| POST | `/admin/responses/{id}/reopen/` | 평가지 반려 |
| POST | `/admin/cycles/{id}/calculate/` | 점수 산출/재산출 |
| GET | `/admin/cycles/{id}/scores/` | 최종 점수 목록 |
| GET | `/admin/cycles/{id}/department-scores/` | 부서 성과 점수 목록 |
| GET | `/admin/cycles/{id}/export/scores.csv` | 점수 CSV |
| GET | `/admin/cycles/{id}/export/responses.csv` | 응답 상세 CSV |
| GET | `/admin/cycles/{id}/export/pending.csv` | 미응답자 CSV |

응답 예시는 [05-admin-features.md](05-admin-features.md) FR-A-06 ~ FR-A-09 참조.

### GET `/admin/cycles/{id}/scores/`

쿼리: `?department=3&ordering=-final_score&search=김철수`

```json
{
  "count": 121,
  "results": [
    {
      "user": { "id": 12, "employee_no": "20210133", "name": "김철수",
                "department_name": "개발1팀", "position": "선임" },
      "primary_score": "82.00",
      "secondary_score": "90.00",
      "individual_score": "84.40",
      "department_score": "89.20",
      "department_adjustment": "3.84",
      "final_score": "88.24",
      "calculated_at": "2026-09-16T10:22:31Z"
    }
  ]
}
```

---

## 7. OpenAPI 스키마

`drf-spectacular`로 자동 생성한다.

| Path | 설명 |
|------|------|
| `/api/schema/` | OpenAPI 3.0 YAML |
| `/api/schema/swagger-ui/` | Swagger UI (개발 환경 전용) |

모든 ViewSet에 `@extend_schema`로 요약·태그·예시를 붙인다.

---

## 8. URL 라우팅

```python
# config/urls.py
urlpatterns = [
    path('admin/', admin.site.urls),               # Django Admin
    path('api/auth/', include('apps.accounts.urls')),
    path('api/my/', include('apps.evaluations.urls_my')),
    path('api/admin/', include('apps.evaluations.urls_admin')),
    path('api/admin/', include('apps.reports.urls')),
    path('api/schema/', SpectacularAPIView.as_view()),
]
```
