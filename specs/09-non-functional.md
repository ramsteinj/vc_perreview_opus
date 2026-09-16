# 09. 비기능 요구사항

## 1. 보안

### 인증 / 인가

- 모든 API는 기본 `IsAuthenticated`. 공개 엔드포인트만 명시적으로 `AllowAny`
- 관리자 API는 `IsAdminRole`로 이중 방어 (라우터 레벨 + ViewSet 레벨)
- **평가지 조회/수정은 `queryset`을 `filter(evaluator=request.user)`로 좁힌다.**
  객체 권한 검사(`has_object_permission`)에만 의존하지 않는다

### 데이터 보호

- 평가 점수와 의견은 민감 정보다. 피평가자 본인도 타인의 평가 내용을 볼 수 없다
- 로그에 비밀번호·토큰·평가 코멘트를 남기지 않는다
- 응답 직렬화에서 `password` 필드를 절대 노출하지 않는다 (`write_only`)

### 전송 / 설정

- 운영 환경은 HTTPS 강제 (`SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS=31536000`)
- `DEBUG=False`, `ALLOWED_HOSTS` 명시
- `SECRET_KEY`는 환경 변수로만 주입. 저장소에 커밋하지 않는다
- `CORS_ALLOWED_ORIGINS`를 화이트리스트로 제한. `CORS_ALLOW_ALL_ORIGINS`를 쓰지 않는다

### 요청 제한

| 대상 | 제한 |
|------|------|
| 로그인 | 사번당 10분에 5회 |
| 인증된 일반 API | 사용자당 1000 req/hour |
| CSV 내보내기 | 사용자당 10 req/hour |

DRF `ScopedRateThrottle`로 구현한다.

### 감사 로그

다음 동작은 `django.db.models.signals` 또는 서비스 계층에서 로그를 남긴다.

- 로그인 성공/실패
- 사용자 생성·수정·비활성화
- 회차 상태 전이 (OPEN / CLOSED)
- 평가지 반려 (reopen) — 사유 포함
- 점수 산출 실행
- CSV 내보내기

로그 형식: `[AUDIT] actor=<employee_no> action=<action> target=<id> detail=<...>`

## 2. 성능

### 목표

| 항목 | 목표 |
|------|------|
| 일반 조회 API (p95) | < 300ms |
| 평가지 저장 | < 200ms |
| 점수 산출 (1000명) | < 10s |
| CSV 내보내기 (1000명) | < 5s |
| 동시 사용자 | 200명 |

### 규칙

- **목록 API에서 N+1 쿼리를 허용하지 않는다.** `select_related` /
  `prefetch_related`를 명시한다
- 현황 집계는 Python 루프가 아니라 `annotate` + `aggregate`로 DB에서 계산한다
- CSV 내보내기는 `StreamingHttpResponse` + `iterator()`로 메모리를 상수로 유지한다
- 점수 산출은 회차 전체 데이터를 한 번에 `prefetch`한 뒤 메모리에서 계산한다
- 테스트에 `assertNumQueries`를 사용해 쿼리 수 회귀를 막는다

### 인덱스

[02-data-model.md](02-data-model.md) §7 참조.

## 3. 데이터 무결성

- 상태 전이와 점수 산출은 `transaction.atomic()`으로 감싼다
- 동시성이 중요한 지점(제출, 산출)은 `select_for_update()`를 사용한다
- 중복 방지는 애플리케이션 검증이 아니라 **DB `UniqueConstraint`가 최종 방어선**이다
- 이력 보존이 필요한 FK는 `PROTECT`. `CASCADE`는 종속 데이터에만 사용한다

## 4. 오류 처리

- DRF 커스텀 `exception_handler`로 모든 오류를 `{code, detail, fields}` 형식으로 통일
- 예상 가능한 도메인 오류는 커스텀 예외 클래스로 표현한다

```python
class DomainError(APIException):
    status_code = 409
    default_code = 'DOMAIN_ERROR'

class AlreadySubmitted(DomainError):
    default_detail = '이미 제출된 평가입니다.'
    default_code = 'ALREADY_SUBMITTED'
```

- 500 오류는 사용자에게 내부 정보를 노출하지 않는다. 서버 로그에만 스택트레이스를 남긴다

## 5. 테스트

### 커버리지 목표

| 영역 | 목표 |
|------|------|
| `services/scoring.py` | **100%** |
| `services/` 전체 | 90% 이상 |
| API 뷰 | 주요 경로 + 권한 + 오류 경로 |
| 전체 | 80% 이상 |

### 필수 테스트

| 영역 | 내용 |
|------|------|
| 점수 계산 | [06-scoring.md](06-scoring.md) §9의 12개 케이스 |
| 인증 | 성명 불일치, 비활성 계정, 시도 제한 |
| 부트스트랩 | 빈 DB 생성, 중복 미생성, 기존 관리자 존재 시 스킵 |
| 중복 제출 | 동시 제출, 재제출 거부 |
| 권한 | 타인 평가지 접근 차단, 직원의 관리자 API 접근 차단 |
| 가중치 | 합계 100 검증, 사용 중 항목 변경 차단 |
| CSV | BOM 확인, 쉼표 포함 값 이스케이프 |

### 도구

- `pytest` + `pytest-django` + `pytest-cov`
- `factory_boy`로 테스트 픽스처 구성
- DB는 실제 PostgreSQL 사용 (SQLite로 대체하지 않는다 — 제약 조건 동작이 다르다)

## 6. 코드 품질

### Backend

| 도구 | 용도 |
|------|------|
| `ruff` | 린트 + 포맷 (line-length 100) |
| `mypy` | 선택적 타입 체크 (`services/`만이라도) |

### Frontend

| 도구 | 용도 |
|------|------|
| `eslint` (`plugin:vue/vue3-recommended`) | 린트 |
| `prettier` | 포맷 |

### 명명 규칙

| 대상 | 규칙 |
|------|------|
| Python 모듈/함수/변수 | `snake_case` |
| Python 클래스 | `PascalCase` |
| Django 모델 필드 | `snake_case` |
| API JSON 키 | `snake_case` (Django 관례 유지, 변환하지 않음) |
| Vue 컴포넌트 파일 | `PascalCase.vue` |
| Vue props/변수 | `camelCase` |
| URL 경로 | `kebab-case` |

## 7. 운영

### 로깅

- 구조화 로그 (JSON) 권장. 최소한 `logging.config.dictConfig`로 포맷 통일
- 레벨: 개발 `DEBUG`, 운영 `INFO`
- 감사 로그는 별도 로거(`audit`)로 분리한다

### 백업

- PostgreSQL 일 1회 전체 백업
- 회차 마감 후 `ScoreResult` 스냅샷은 삭제하지 않는다 (이력 보존)

### 배포

```
Frontend:  npm run build  →  dist/  →  Nginx 정적 서빙
Backend:   gunicorn config.wsgi  (Nginx 리버스 프록시)
Static:    python manage.py collectstatic  (Django Admin용)
DB:        PostgreSQL 15+
```

- SPA 라우팅을 위해 Nginx에 `try_files $uri $uri/ /index.html;` 설정
- `/api`와 `/admin`은 gunicorn으로 프록시

### 헬스체크

```
GET /api/health/   →  { "status": "ok", "db": "ok" }
```

## 8. 브라우저 지원

Chrome / Edge / Safari 최신 2개 버전. IE는 지원하지 않는다.
