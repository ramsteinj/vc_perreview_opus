# vc_perreview_opus

조직 구성원의 성과를 평가하고, 개인 평가 점수에 부서 성과 점수를 가감해
최종 점수(0~100)를 산출하는 인사평가 웹 애플리케이션.

> performance review app created by Claude Code

## 주요 기능

### 직원

- 성명 · 사번 · 비밀번호 기반 로그인
- 배정된 평가 대상에 대한 평가 문항 응답
- 임시 저장(자동 저장 포함) 및 진행률 표시
- 중복 응답 방지

### 관리자

- 사용자 추가 · 수정 · 삭제
- 부서 관리 (계층 구조)
- 부서 / 직원 평가 항목 관리 및 항목별 가중치 부여
- 부서 / 직원 1차 · 2차 평가자 지정 (2차는 선택)
- 응답 현황 조회 — 요약 · 상세 · 미응답자 모니터링
- 구성원 평가 CSV(Excel) 다운로드
- 부서 성과 점수 계산
- 부서 성과 점수를 개인 평가 점수에 자동 가감하여 최종 점수 산출 (0~100)

## 기술 스택

```
Vue.js 3 SPA  (Vite · Bootstrap 5)
      │  HTTP / JSON
      ▼
Django REST Framework
      │  Django ORM
      ▼
PostgreSQL
```

| 영역 | 기술 |
|------|------|
| Frontend | Vue.js 3, Vite, Vue Router, Pinia, Bootstrap 5, Axios |
| Backend | Python 3.11+, Django 5, Django REST Framework, SimpleJWT |
| Database | PostgreSQL 15+ |

## 시작하기

### 사전 요구사항

- Python 3.11+
- Node.js 18.18+ (Vite 5 기준)
- Docker (PostgreSQL 구동용) 또는 로컬 PostgreSQL 15+

### 1. 데이터베이스

```bash
docker compose up -d
```

> 호스트에 이미 PostgreSQL이 떠 있는 경우가 많아 컨테이너는 **5433** 포트로 노출한다.
> `DATABASE_URL`의 포트도 5433이다.

### 2. 백엔드

```bash
cd backend
python -m venv .venv               # python3-venv가 없으면: uv venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt    # uv 사용 시: uv pip install -r requirements.txt
cp .env.example .env
python manage.py migrate           # 이 시점에 기본 관리자 계정이 자동 생성된다
python manage.py runserver         # http://localhost:8000
```

### 3. 프론트엔드

```bash
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

### 4. 로그인

| 항목 | 값 |
|------|-----|
| 성명 | `ADMIN` |
| 사번 | `ADMIN` |
| 비밀번호 | `admin1234!` |

> ⚠️ 최초 로그인 후 비밀번호를 반드시 변경하세요.

## 점수 산출 방식

```
① 평가지 환산 점수 = Σ(항목점수/척도 × 100 × 가중치) / Σ가중치
② 개인 평가 점수   = 1차 × 70% + 2차 × 30%      (2차 미지정/미제출 시 1차 100%)
③ 부서 성과 점수   = 부서 평가 항목에 ①② 동일 적용
④ 부서 가감값     = clamp((부서점수 − 기준점 70) × 계수 0.2, −10, +10)
⑤ 최종 점수       = clamp(개인 평가 점수 + 부서 가감값, 0, 100)
```

기준점 · 계수 · 가감 한도 · 1차/2차 비율은 평가 회차별로 관리자가 설정한다.
상세 규칙과 예시는 [specs/06-scoring.md](specs/06-scoring.md) 참조.

## 문서

| 문서 | 내용 |
|------|------|
| [CLAUDE.md](CLAUDE.md) | AI 코딩 가이드 / 개발 규칙 |
| [specs/00-overview.md](specs/00-overview.md) | 프로젝트 개요, 용어집 |
| [specs/01-architecture.md](specs/01-architecture.md) | 아키텍처, 기술 스택, 디렉터리 구조 |
| [specs/02-data-model.md](specs/02-data-model.md) | 데이터 모델, 제약 조건 |
| [specs/03-auth.md](specs/03-auth.md) | 인증 · 인가, 기본 관리자 부트스트랩 |
| [specs/04-employee-features.md](specs/04-employee-features.md) | 직원 기능 요구사항 |
| [specs/05-admin-features.md](specs/05-admin-features.md) | 관리자 기능 요구사항 |
| [specs/06-scoring.md](specs/06-scoring.md) | 점수 계산 규칙 |
| [specs/07-api.md](specs/07-api.md) | REST API 명세 |
| [specs/08-frontend.md](specs/08-frontend.md) | 화면 구성, 라우팅, 상태 관리 |
| [specs/09-non-functional.md](specs/09-non-functional.md) | 보안 · 성능 · 테스트 · 운영 |
| [specs/10-roadmap.md](specs/10-roadmap.md) | 구현 단계 및 체크리스트 |

## 프로젝트 구조

```
vc_perreview_opus/
├── CLAUDE.md              # AI 코딩 가이드
├── README.md
├── specs/                 # 요구사항 명세
├── backend/               # Django REST Framework
│   ├── config/            # 프로젝트 설정
│   └── apps/
│       ├── accounts/      # 사용자 · 부서 · 인증
│       ├── evaluations/   # 회차 · 항목 · 배정 · 응답
│       └── reports/       # 현황 집계 · 평가지 반려 · 점수 산출 · CSV
└── frontend/              # Vue 3 SPA
    └── src/{views,components,stores,api,router}/
```

## 개발 명령어

```bash
# Backend
pytest                                          # 테스트
pytest --cov=apps --cov-report=term-missing     # 커버리지
ruff check . && ruff format .                   # 린트 · 포맷

# Frontend
npm run build                                   # 프로덕션 빌드
npm run lint                                    # 린트
```

API 문서(개발 환경): http://localhost:8000/api/schema/swagger-ui/

## 진행 상황

| Phase | 내용 | 상태 |
|-------|------|------|
| 1 | 기반 구축 (프로젝트 설정 · 인증 · 기본 관리자) | ✅ 완료 |
| 2 | 마스터 데이터 관리 (부서 · 사용자) | ✅ 완료 |
| 3 | 평가 설정 (회차 · 항목 · 가중치 · 평가자 배정) | ✅ 완료 |
| 4 | 평가 응답 (작성 · 임시저장 · 진행률 · 제출) | ✅ 완료 |
| 5 | 현황 모니터링 (요약 · 상세 · 미응답자) | ✅ 완료 |
| 6 | 점수 산출 (개인 · 부서 · 최종 합산) | ✅ 완료 |
| 7 | CSV 내보내기 및 마무리 | ⬜ 미착수 |

현재 단계: **Phase 6 완료.** 개인 평가 점수에 부서 성과 가감을 반영해 최종 점수(0~100)를
산출합니다. 남은 단계는 Phase 7(CSV 내보내기 및 마무리)입니다.
