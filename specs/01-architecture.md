# 01. 시스템 아키텍처

## 1. 전체 구조

```
┌─────────────────────────────────────────┐
│  Vue.js 3 SPA (Vite + Bootstrap 5)      │
│  - Vue Router (클라이언트 라우팅)         │
│  - Pinia (상태 관리)                     │
│  - Axios (HTTP 클라이언트)               │
└─────────────────┬───────────────────────┘
                  │ HTTP / JSON (REST)
                  │ Authorization: Bearer <JWT>
                  ▼
┌─────────────────────────────────────────┐
│  Django + Django REST Framework         │
│  - ViewSet / Serializer / Permission    │
│  - SimpleJWT (인증)                      │
│  - 서비스 계층 (점수 계산 등 도메인 로직)  │
└─────────────────┬───────────────────────┘
                  │ Django ORM
                  ▼
┌─────────────────────────────────────────┐
│  PostgreSQL                             │
└─────────────────────────────────────────┘
```

**프론트엔드와 백엔드는 완전히 분리된 배포 단위다.** Django는 템플릿을 렌더링하지 않고
JSON API만 제공한다. (예외: Django Admin은 운영 편의를 위해 유지)

## 2. 기술 스택

### Frontend

| 항목 | 선택 | 비고 |
|------|------|------|
| 프레임워크 | Vue.js 3 | Composition API + `<script setup>` 사용 |
| 빌드 도구 | Vite 5+ | 개발 서버 프록시로 CORS 우회 |
| UI 프레임워크 | Bootstrap 5 | `bootstrap` + `@popperjs/core` npm 설치. CDN 사용 금지 |
| 라우팅 | Vue Router 4 | History 모드 |
| 상태 관리 | Pinia | 인증 상태, 평가 응답 임시 상태 |
| HTTP | Axios | 인터셉터로 JWT 주입 / 401 시 refresh |
| 언어 | JavaScript (ES2022) | TypeScript는 사용하지 않는다 |

### Backend

| 항목 | 선택 | 비고 |
|------|------|------|
| 언어 | Python 3.11+ | |
| 프레임워크 | Django 5.x | |
| API | Django REST Framework 3.15+ | |
| 인증 | djangorestframework-simplejwt | Access/Refresh 토큰 |
| CORS | django-cors-headers | 개발 환경용 |
| 환경변수 | django-environ | `.env` 파일 기반 설정 |
| DB 드라이버 | psycopg[binary] 3.x | |
| API 문서 | drf-spectacular | OpenAPI 3.0 스키마 자동 생성 |
| 필터링 | django-filter | 목록 API 검색/필터 |

### Database

| 항목 | 선택 |
|------|------|
| RDBMS | PostgreSQL 15+ |
| 마이그레이션 | Django Migrations |

## 3. 디렉터리 구조

```
vc_perreview_opus/
├── CLAUDE.md                  # AI 코딩 가이드
├── README.md                  # 프로젝트 소개 / 실행 방법
├── specs/                     # 요구사항 명세 (본 폴더)
├── docker-compose.yml         # PostgreSQL 로컬 구동용
│
├── backend/
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── config/                # Django 프로젝트 설정
│   │   ├── settings/
│   │   │   ├── base.py
│   │   │   ├── dev.py
│   │   │   └── prod.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   └── apps/
│       ├── accounts/          # User, Department, 인증
│       │   ├── models.py
│       │   ├── managers.py
│       │   ├── serializers.py
│       │   ├── views.py
│       │   ├── permissions.py
│       │   ├── backends.py    # 커스텀 인증 백엔드
│       │   ├── apps.py        # 기본 관리자 부트스트랩 시그널
│       │   └── tests/
│       ├── evaluations/       # Cycle, Item, Assignment, Response, Answer
│       │   ├── models.py
│       │   ├── serializers.py
│       │   ├── views.py
│       │   ├── services/      # 도메인 로직 (점수 계산 등)
│       │   │   ├── scoring.py
│       │   │   └── progress.py
│       │   └── tests/
│       └── reports/           # 현황 집계, CSV 내보내기
│           ├── views.py
│           ├── services/
│           │   ├── aggregation.py
│           │   └── csv_export.py
│           └── tests/
│
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── main.js
        ├── App.vue
        ├── router/index.js
        ├── stores/            # Pinia
        │   ├── auth.js
        │   └── evaluation.js
        ├── api/               # Axios 래퍼 (도메인별 모듈)
        │   ├── client.js
        │   ├── auth.js
        │   ├── evaluations.js
        │   └── admin.js
        ├── views/             # 라우트 단위 페이지
        │   ├── LoginView.vue
        │   ├── employee/
        │   └── admin/
        ├── components/        # 재사용 컴포넌트
        └── assets/
            └── main.scss      # Bootstrap 커스터마이즈
```

## 4. 계층 규칙

### Backend

```
View (DRF ViewSet)  ← HTTP 처리, 권한 검사, 직렬화만 담당
    ↓
Service (services/) ← 도메인 로직. 점수 계산, 집계, 상태 전이
    ↓
Model (ORM)         ← 데이터 정의, 단순 제약, 계산 프로퍼티
```

- **점수 계산 로직은 반드시 `services/scoring.py`에 둔다.** View나 Serializer에
  계산식을 인라인으로 작성하지 않는다.
- Serializer는 검증과 변환만 담당한다. 저장 부수효과가 필요하면 Service를 호출한다.
- 모델 간 무결성 제약은 DB 레벨(`UniqueConstraint`, `CheckConstraint`)로 표현한다.

### Frontend

```
View (페이지)  ← 라우트 대응. 레이아웃 조립
    ↓
Store (Pinia)  ← 서버 상태 캐싱, 인증 상태
    ↓
API 모듈       ← Axios 호출만. 컴포넌트에서 axios 직접 호출 금지
```

## 5. 개발 환경 구동

```bash
# 1) PostgreSQL
docker compose up -d

# 2) Backend  (http://localhost:8000)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate          # 이 시점에 기본 ADMIN 계정 자동 생성
python manage.py runserver

# 3) Frontend (http://localhost:5173)
cd frontend
npm install
npm run dev
```

Vite 개발 서버는 `/api` 요청을 `http://localhost:8000`으로 프록시한다.

```js
// vite.config.js
server: {
  proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } }
}
```

## 6. 환경 변수

`backend/.env.example`:

```
DJANGO_SETTINGS_MODULE=config.settings.dev
SECRET_KEY=change-me
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgres://perreview:perreview@localhost:5432/perreview
CORS_ALLOWED_ORIGINS=http://localhost:5173

# 기본 관리자 부트스트랩 (03-auth.md 참조)
DEFAULT_ADMIN_NAME=ADMIN
DEFAULT_ADMIN_EMPLOYEE_NO=ADMIN
DEFAULT_ADMIN_PASSWORD=admin1234!
```
