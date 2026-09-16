# 10. 구현 로드맵 및 체크리스트

각 단계는 **동작하는 상태로 끝난다.** 다음 단계로 넘어가기 전에 해당 단계의
체크박스를 모두 채운다.

---

## Phase 1 — 기반 구축

**목표:** 로그인이 되고 기본 관리자 계정으로 진입할 수 있다.

### Backend

- [x] Django 프로젝트 생성 (`config/settings/{base,dev,prod}.py` 분리)
- [x] PostgreSQL 연결 (`docker-compose.yml`, `DATABASE_URL`)
- [x] `accounts` 앱: `Department`, `User(AbstractUser)`, `UserManager`
- [x] `AUTH_USER_MODEL = 'accounts.User'` 설정 후 **최초 마이그레이션**
- [x] 커스텀 인증 백엔드 (`EmployeeNoNameBackend`)
- [x] SimpleJWT 설정 + 커스텀 클레임
- [x] `POST /api/auth/login/`, `/refresh/`, `/logout/`, `GET /me/`
- [x] 기본 관리자 부트스트랩 (`post_migrate` 시그널 + 관리 명령)
- [x] 로그인 시도 제한
- [x] `drf-spectacular` 스키마 노출

### Frontend

- [x] Vite + Vue 3 프로젝트 생성, `/api` 프록시 설정
- [x] Bootstrap 5 npm 설치 + SCSS 커스터마이즈
- [x] `stores/auth.js`, `api/client.js` (인터셉터 포함)
- [x] `LoginView.vue`
- [x] 라우터 + 내비게이션 가드 + 레이아웃 셸

### 완료 조건

- [x] 빈 DB에 `migrate` 후 `ADMIN / ADMIN / admin1234!`로 로그인된다
- [x] 새로고침해도 로그인 상태가 유지된다
- [x] 성명을 틀리면 로그인이 실패한다

---

## Phase 2 — 마스터 데이터 관리

**목표:** 관리자가 부서와 사용자를 관리할 수 있다.

### Backend

- [x] `DepartmentViewSet` (트리 조회 포함)
- [x] `UserViewSet` (생성/수정/소프트 삭제/비밀번호 초기화)
- [x] `IsAdminRole` 권한 클래스
- [x] 마지막 관리자 비활성화 차단
- [x] 필터/검색/페이지네이션

### Frontend

- [x] `AdminLayout.vue` + 사이드 내비게이션
- [x] `DepartmentListView.vue` (트리 표시, 생성/수정/삭제)
- [x] `UserListView.vue` (목록/검색/필터/생성/수정/비활성화)
- [x] `DataTable.vue`, `BaseModal.vue`, `ToastHost.vue` 공용 컴포넌트

### 완료 조건

- [x] 부서 트리를 만들고 직원을 소속시킬 수 있다
- [x] 순환 참조 부서 생성이 차단된다
- [x] 생성한 직원 계정으로 로그인된다

---

## Phase 3 — 평가 설정

**목표:** 회차를 만들고 항목·가중치·평가자를 설정해 `OPEN`할 수 있다.

### Backend

- [x] `EvaluationCycle` 모델 + ViewSet + 상태 전이 액션
- [x] `EvaluationItem` 모델 + ViewSet + `reorder` + `weight-check`
- [x] 가중치 합계 100 검증 (OPEN 전이 시)
- [x] 사용 중 항목 변경 차단
- [x] `EvaluatorAssignment` 모델 + ViewSet + `bulk` 배정
- [x] 자기 평가 / 1·2차 중복 검증
- [x] 항목 복제 (`clone-items`)

### Frontend

- [x] `CycleListView.vue` (생성/수정/상태 전이)
- [x] `ItemEditorView.vue` (탭, 인라인 편집, 가중치 합계 실시간 표시, 드래그 정렬)
- [x] `AssignmentEditorView.vue` (1차/2차 선택, 미배정 요약, 일괄 배정)
- [x] `UserSelect.vue`

### 완료 조건

- [x] 가중치 합계가 100이 아니면 OPEN 전이가 거부된다
- [x] 2차 평가자 없이 배정을 저장할 수 있다
- [x] 본인을 본인의 평가자로 지정하면 거부된다

---

## Phase 4 — 평가 응답 (직원)

**목표:** 직원이 평가지를 작성하고 제출할 수 있다.

### Backend

- [x] `EvaluationResponse`, `EvaluationAnswer` 모델 + 제약 조건
- [x] `GET /api/my/assignments/` (진행률 포함)
- [x] `POST /api/my/responses/` (get_or_create)
- [x] `GET/PUT /api/my/responses/{id}/` (부분 저장 upsert)
- [x] `POST /api/my/responses/{id}/submit/` (검증 + `select_for_update`)
- [x] 진행률 계산 (`services/progress.py`)
- [x] 중복 제출 방지 (DB 제약 + 서비스 검증 + 409)

### Frontend

- [x] `MyAssignmentsView.vue` (요약 카드, 진행률 바, 상태 배지)
- [x] `EvaluationFormView.vue` (라디오 점수, 가중치 표시, 의견)
- [x] 자동 저장 (3초 디바운스) + 수동 저장
- [x] 이탈 방지 가드
- [x] 제출 확인 모달 + 미입력 항목 하이라이트
- [x] 제출 후 읽기 전용 전환
- [x] `ProgressBar.vue`, `StatusBadge.vue`

### 완료 조건

- [x] 임시 저장 후 재접속 시 입력이 복원된다
- [x] 제출 버튼 더블 클릭에도 평가지가 하나만 제출된다
- [x] 미입력 항목이 있으면 제출이 거부된다
- [x] 다른 사람의 평가지에 접근하면 403/404가 반환된다

---

## Phase 5 — 현황 모니터링

**목표:** 관리자가 응답 현황과 미응답자를 파악할 수 있다.

### Backend

- [x] `reports` 앱 생성
- [x] `status/summary/` (전체·차수별·유형별·부서별 집계)
- [x] `status/detail/` (필터·검색·페이지네이션)
- [x] `status/pending/` (평가자별 그룹핑)
- [x] 미시작(레코드 없음) 건을 분모에 포함하는 집계 로직
- [x] `POST /admin/responses/{id}/reopen/`
- [x] `assertNumQueries`로 N+1 방지 확인

### Frontend

- [x] `ResponseStatusView.vue` (요약/상세/미응답자 탭)
- [x] 진행률 시각화 (도넛/바)
- [x] 필터 조합 + 검색
- [x] 평가지 열람 모달 + 반려

### 완료 조건

- [x] 미시작 건이 미응답자 목록에 포함된다
- [x] 부서별 제출률이 정확하다
- [x] 반려한 평가지가 평가자 화면에서 다시 수정 가능해진다

---

## Phase 6 — 점수 산출

**목표:** 최종 점수가 산출되고 화면에서 확인된다.

### Backend

- [x] `services/scoring.py` — 평가지 환산, 개인 점수, 부서 점수, 가감, 최종
- [x] `Decimal` + `ROUND_HALF_UP` 반올림 유틸
- [x] `ScoreResult` 모델
- [x] `POST /admin/cycles/{id}/calculate/` (멱등, 단일 트랜잭션)
- [x] `GET /admin/cycles/{id}/scores/`
- [x] `GET /admin/cycles/{id}/department-scores/`
- [x] 회차 `CLOSED` 전이 시 자동 산출
- [x] **[06-scoring.md](06-scoring.md) §9의 12개 테스트 케이스 전부 통과**

### Frontend

- [x] `DepartmentScoreView.vue` (부서 점수 + 가감 파라미터 편집)
- [x] `ScoreResultView.vue` (재계산, 점수 테이블, 미산출 사유)
- [x] 산출 결과 요약 모달

### 완료 조건

- [x] 최종 점수가 항상 0~100 범위에 있다
- [x] 재계산을 반복해도 결과가 같고 레코드가 중복되지 않는다
- [x] 2차 평가자 미지정 시 1차 점수가 100% 반영된다
- [x] 부서 평가 미제출 시 가감이 0이다

---

## Phase 7 — CSV 내보내기 + 마무리

**목표:** 결과를 Excel로 내려받고 운영 준비를 마친다.

### Backend

- [x] `services/csv_export.py` (`StreamingHttpResponse`, UTF-8 BOM)
- [x] `export/scores.csv`, `export/responses.csv`, `export/pending.csv`
- [x] 한글 파일명 인코딩 (`filename*=UTF-8''`)
- [x] CSV 내보내기 요청 제한
- [x] 감사 로그
- [x] `GET /api/health/`

### Frontend

- [x] 각 화면에 CSV 다운로드 버튼
- [x] `DashboardView.vue` (회차 현황 요약 + 바로가기)
- [x] 403 / 404 화면
- [x] 기본 비밀번호 변경 안내 배너

### 마무리

- [x] `ruff`, `eslint` 통과
- [x] 테스트 커버리지 80% 이상, `scoring.py` 100%
- [x] `README.md` 실행 방법 검증 (빈 환경에서 처음부터 따라해 보기)
- [x] 운영 설정 점검 (`DEBUG=False`, HTTPS, CORS, `SECRET_KEY`)

### 완료 조건

- [x] Excel에서 CSV를 열었을 때 한글이 깨지지 않는다
- [x] 1000명 규모 데이터에서 CSV 다운로드가 5초 이내에 끝난다

---

## 진행 상황

| Phase | 상태 | 비고 |
|-------|------|------|
| 1. 기반 구축 | ✅ 완료 | 2026-09-16 |
| 2. 마스터 데이터 | ✅ 완료 | 2026-09-16 |
| 3. 평가 설정 | ✅ 완료 | 2026-09-16 |
| 4. 평가 응답 | ✅ 완료 | 2026-09-16 |
| 5. 현황 모니터링 | ✅ 완료 | 2026-09-16 |
| 6. 점수 산출 | ✅ 완료 | 2026-09-16 |
| 7. CSV + 마무리 | ✅ 완료 | 2026-09-16 |

> 각 Phase를 완료할 때 이 표와 [README.md](../README.md)의 진행 상황을 함께 갱신한다.
