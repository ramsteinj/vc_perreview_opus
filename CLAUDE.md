# CLAUDE.md

이 저장소에서 작업할 때 따라야 할 규칙이다.

## 프로젝트

조직 구성원의 성과를 평가하고, 개인 평가 점수에 부서 성과 점수를 가감해
최종 점수(0~100)를 산출하는 인사평가 웹 애플리케이션.

**스택:** Vue 3 (Vite, Bootstrap 5) SPA → Django REST Framework → PostgreSQL

## 요구사항은 specs/에 있다

**코드를 쓰기 전에 해당 기능의 스펙 문서를 먼저 읽는다.**
추측으로 구현하지 않는다. 스펙에 없는 내용을 임의로 만들어 넣지 않는다.

| 작업 대상 | 읽을 문서 |
|-----------|-----------|
| 전체 맥락·용어 | [specs/00-overview.md](specs/00-overview.md) |
| 프로젝트 구조·스택 | [specs/01-architecture.md](specs/01-architecture.md) |
| 모델·필드·제약 | [specs/02-data-model.md](specs/02-data-model.md) |
| 로그인·권한·기본 관리자 | [specs/03-auth.md](specs/03-auth.md) |
| 직원 기능 | [specs/04-employee-features.md](specs/04-employee-features.md) |
| 관리자 기능 | [specs/05-admin-features.md](specs/05-admin-features.md) |
| **점수 계산** | [specs/06-scoring.md](specs/06-scoring.md) |
| API 엔드포인트 | [specs/07-api.md](specs/07-api.md) |
| 화면·라우팅·상태 | [specs/08-frontend.md](specs/08-frontend.md) |
| 보안·성능·테스트 | [specs/09-non-functional.md](specs/09-non-functional.md) |
| 구현 순서 | [specs/10-roadmap.md](specs/10-roadmap.md) |

스펙과 코드가 어긋나면 **스펙이 기준이다.** 스펙을 바꿔야 한다고 판단되면
코드를 먼저 고치지 말고 스펙 변경을 제안한다.

## 디렉터리

```
backend/
  config/settings/{base,dev,prod}.py
  apps/accounts/      User, Department, 인증
  apps/evaluations/   Cycle, Item, Assignment, Response, Answer
  apps/reports/       현황 집계, 점수 산출 결과, CSV
frontend/
  src/{views,components,stores,api,router}/
specs/                요구사항 명세
```

## 반드시 지킬 것

### 1. 점수 계산은 `services/scoring.py`에만 둔다

View, Serializer, 모델 메서드, 프론트엔드 어디에도 계산식을 복제하지 않는다.
계산은 전부 `Decimal`로 한다. `float`를 쓰지 않는다.

```python
from decimal import Decimal, ROUND_HALF_UP
def q2(v: Decimal) -> Decimal:
    return v.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
```

최종 점수는 항상 `clamp(..., 0, 100)`을 거친다.
계산식 전문은 [specs/06-scoring.md](specs/06-scoring.md).

### 2. 계층을 지킨다

```
Backend:   View(HTTP/권한/직렬화) → Service(도메인 로직) → Model(데이터)
Frontend:  View(페이지) → Store(상태) → api/*.js(HTTP)
```

- 뷰에 비즈니스 로직을 넣지 않는다
- 컴포넌트에서 `axios`를 직접 호출하지 않는다

### 3. 중복 응답 방지는 DB 제약이 최종 방어선이다

`EvaluationResponse`의 `UniqueConstraint(assignment, round)`를 제거하거나
우회하지 않는다. 제출 처리는 `transaction.atomic()` + `select_for_update()`로 감싼다.

### 4. 권한은 queryset에서 좁힌다

```python
# 이렇게
def get_queryset(self):
    return EvaluationResponse.objects.filter(evaluator=self.request.user)

# 이것만으로는 부족하다
def has_object_permission(self, request, view, obj):
    return obj.evaluator == request.user
```

### 5. 마이그레이션

- `AUTH_USER_MODEL`은 **첫 마이그레이션 전에** 반드시 설정한다
- 모델을 바꾸면 같은 작업에서 마이그레이션을 생성한다
- 기존 마이그레이션 파일을 손으로 고치지 않는다
- 비밀번호 등 시크릿을 데이터 마이그레이션에 넣지 않는다
  (기본 관리자 계정은 `post_migrate` 시그널로 생성한다)

### 6. N+1 쿼리를 만들지 않는다

목록 API에는 `select_related` / `prefetch_related`를 명시한다.
집계는 Python 루프가 아니라 `annotate` / `aggregate`로 DB에서 계산한다.

### 7. CSV는 UTF-8 BOM으로 내보낸다

BOM(`﻿`)이 없으면 Excel에서 한글이 깨진다. `StreamingHttpResponse`를 쓴다.

### 8. 시크릿을 커밋하지 않는다

`.env`는 `.gitignore`에 있다. `.env.example`만 커밋한다.

## 코드 규약

| 대상 | 규칙 |
|------|------|
| Python | `snake_case`, 클래스 `PascalCase`, line-length 100, `ruff` |
| API JSON 키 | `snake_case` (camelCase로 변환하지 않는다) |
| Vue 컴포넌트 파일 | `PascalCase.vue`, Composition API + `<script setup>` |
| Vue 변수/props | `camelCase` |
| URL 경로 | `kebab-case` |
| 선택지 | `models.TextChoices` |
| 점수/가중치 | `DecimalField` (절대 `FloatField` 아님) |
| FK | `on_delete` 항상 명시. 이력 보존은 `PROTECT` |
| 사용자 노출 문구 | 한국어 |
| 코드 식별자·주석 | 영문 식별자, 주석은 한국어 허용 |

**TypeScript는 사용하지 않는다.** 프론트엔드는 JavaScript로 작성한다.

## 명령어

```bash
# DB
docker compose up -d

# Backend
cd backend && source .venv/bin/activate
python manage.py migrate          # 기본 ADMIN 계정 자동 생성
python manage.py runserver
pytest                            # 테스트
pytest --cov=apps --cov-report=term-missing
ruff check . && ruff format .

# Frontend
cd frontend
npm run dev
npm run build
npm run lint
```

기본 관리자: 성명 `ADMIN` / 사번 `ADMIN` / 비밀번호 `admin1234!`

## 테스트

- **`services/scoring.py`는 커버리지 100%를 유지한다.**
  [specs/06-scoring.md](specs/06-scoring.md) §9의 12개 케이스가 기준선이다
- 점수 계산, 중복 제출, 권한, 가중치 검증을 바꾸면 테스트를 함께 갱신한다
- 테스트 DB는 PostgreSQL을 쓴다. SQLite로 대체하지 않는다 (제약 동작이 다르다)
- 기능을 완료하면 관련 테스트를 실행하고 **결과를 있는 그대로 보고한다**

## 작업 방식

1. [specs/10-roadmap.md](specs/10-roadmap.md)의 Phase 순서를 따른다
2. 한 Phase를 끝내면 체크박스와 진행 상황 표를 갱신한다
3. Phase 완료 시 [README.md](README.md)의 진행 상황도 함께 갱신한다
4. 스펙에 없어 판단이 필요한 지점이 나오면, 임의로 정하지 말고 질문한다.
   진행이 막히지 않는 사소한 선택은 결정하고 그 사실을 알린다

## 자주 틀리는 지점

- `User`에서 `username`, `first_name`, `last_name`을 `None`으로 비활성화했다.
  이 필드들을 참조하는 코드를 쓰지 않는다. 성명은 `name`, 로그인 식별자는 `employee_no`
- 로그인은 사번만이 아니라 **성명까지 함께 검증**한다
- 2차 평가자는 **선택**이다. 미지정·미제출을 0점으로 처리하지 않는다 (1차 100% 반영)
- 응답 현황의 분모는 `EvaluationResponse` 레코드 수가 아니라
  **배정에서 도출되는 기대 응답 수**다. 미시작(레코드 없음) 건이 빠지면 안 된다
- 가중치 합계 100 검증은 **회차 `OPEN` 전이 시점**에 한다. 편집 중에는 막지 않는다
- 평가 항목은 회차에 종속된다. 응답이 있는 항목의 가중치·척도는 변경할 수 없다
