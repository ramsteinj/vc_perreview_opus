# 08. 프론트엔드 명세

## 1. 라우팅

```
/login                              LoginView            공개

# 직원
/my/evaluations                     MyAssignmentsView    인증
/my/evaluations/:responseId         EvaluationFormView   인증 (본인 평가지만)

# 관리자
/admin                              AdminLayout          ADMIN
  /admin/dashboard                  DashboardView
  /admin/users                      UserListView
  /admin/departments                DepartmentListView
  /admin/cycles                     CycleListView
  /admin/cycles/:id/items           ItemEditorView
  /admin/cycles/:id/assignments     AssignmentEditorView
  /admin/cycles/:id/status          ResponseStatusView
  /admin/cycles/:id/department-scores DepartmentScoreView
  /admin/cycles/:id/scores          ScoreResultView

/403                                ForbiddenView
/:pathMatch(.*)*                    NotFoundView
```

### 내비게이션 가드

```js
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.public) return true
  if (!auth.isAuthenticated) return { name: 'login', query: { next: to.fullPath } }
  if (to.meta.role === 'ADMIN' && auth.user.role !== 'ADMIN') return { name: 'forbidden' }
  return true
})
```

## 2. 상태 관리 (Pinia)

### `stores/auth.js`

| State | 설명 |
|-------|------|
| `accessToken` | 메모리에만 보관 |
| `user` | `{ id, employee_no, name, role, department }` |

| Action | 설명 |
|--------|------|
| `login({ name, employee_no, password })` | 로그인 |
| `logout()` | 토큰 폐기 + 스토어 초기화 |
| `refresh()` | access 토큰 갱신 |
| `restore()` | 앱 부팅 시 `localStorage`의 refresh로 세션 복구 |

`refresh` 토큰만 `localStorage`에 저장한다. 앱 부팅 시 `restore()`를 호출해
세션을 복구하고, 완료 전에는 라우팅을 보류한다.

### `stores/evaluation.js`

| State | 설명 |
|-------|------|
| `currentResponse` | 작성 중인 평가지 |
| `dirty` | 저장되지 않은 변경 여부 |
| `lastSavedAt` | 마지막 저장 시각 |
| `saving` | 저장 진행 중 플래그 |

| Getter | 설명 |
|--------|------|
| `progress` | 낙관적 진행률 계산 |

## 3. Axios 클라이언트

```js
// api/client.js
const client = axios.create({ baseURL: '/api', timeout: 15000 })

client.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.accessToken) config.headers.Authorization = `Bearer ${auth.accessToken}`
  return config
})

// 401 → refresh 1회 재시도. 동시 다발 401은 하나의 refresh Promise로 합류시킨다
client.interceptors.response.use(null, async (error) => { /* ... */ })
```

**규칙**

- 컴포넌트에서 `axios`를 직접 호출하지 않는다. 항상 `api/*.js` 모듈을 거친다
- 401 재시도는 **요청당 1회**로 제한한다. 실패하면 로그아웃 후 로그인 화면으로 이동
- `refresh` 요청 자체가 401이면 재시도하지 않는다 (무한 루프 방지)

## 4. 화면별 요구사항

### 4.1 LoginView

- 성명 / 사번 / 비밀번호 3개 필드
- 제출 중 버튼 비활성화 + 스피너
- 실패 메시지는 폼 상단 `alert-danger`에 통합 표시
- 성공 시 `role`에 따라 분기 (직원 → `/my/evaluations`, 관리자 → `/admin/dashboard`)
- `next` 쿼리가 있으면 해당 경로로 복귀

### 4.2 MyAssignmentsView

- 상단 요약 카드: 전체 / 제출완료 / 임시저장 / 미시작
- 목록 테이블: 대상, 유형, 차수, 진행률 바, 상태 배지, 액션
- 마감일 D-day 표시. 3일 이내면 강조
- 미시작 행의 [평가하기]는 `POST /my/responses/` 후 폼으로 이동

### 4.3 EvaluationFormView

**핵심 화면.** 상세 레이아웃은 [04-employee-features.md](04-employee-features.md) FR-E-03 참조.

| 요구 | 구현 |
|------|------|
| 진행률 | 상단 sticky 프로그레스 바, 입력 시 즉시 갱신 |
| 자동 저장 | 변경 후 3초 디바운스 |
| 수동 저장 | [임시 저장] 버튼 |
| 이탈 방지 | `onBeforeRouteLeave` + `beforeunload`에서 `dirty` 확인 |
| 제출 | 확인 모달 → `POST .../submit/` |
| 미입력 항목 | 제출 실패 시 첫 미입력 항목으로 스크롤 + 붉은 테두리 |
| 읽기 전용 | `editable === false`면 모든 입력 `disabled` |

점수 입력은 Bootstrap의 `btn-group` + `btn-check` 라디오로 구현한다
(터치 대상이 충분히 크고 키보드 접근성이 확보된다).

### 4.4 ItemEditorView

- `개인 항목` / `부서 항목` 탭
- 인라인 편집 테이블 (코드, 제목, 설명, 가중치, 척도, 활성)
- **가중치 합계 실시간 표시.** 100이면 초록, 아니면 경고
- 드래그로 순서 변경 → `POST /admin/items/reorder/`
- 사용 중인 항목(`in_use: true`)은 가중치·척도 입력이 잠긴다

### 4.5 AssignmentEditorView

- 대상 행마다 1차/2차 평가자 선택 (검색 가능한 셀렉트)
- 미배정 대상 상단 요약 + 필터
- 부서 단위 일괄 배정 모달
- 저장은 변경된 행만 전송

### 4.6 ResponseStatusView

- 탭: `요약` / `상세` / `미응답자`
- 요약: 전체 제출률 도넛, 차수별·부서별 진행률 바
- 상세: 필터(부서/상태/차수/유형) + 검색 + 페이지네이션 테이블
- 미응답자: 평가자별 그룹, 미응답 건수 내림차순
- 각 탭에 CSV 다운로드 버튼

### 4.7 ScoreResultView

- [재계산] 버튼 → 산출 결과 요약 모달 (산출/미산출 건수, 미산출 사유)
- 점수 테이블: 1차 / 2차 / 개인 / 부서가감 / 최종
- 미산출자 행은 흐리게 표시하고 사유 툴팁
- [CSV 다운로드]

## 5. Bootstrap 5 사용 규칙

- **npm으로 설치한다.** CDN을 사용하지 않는다

```js
// main.js
import 'bootstrap/dist/css/bootstrap.min.css'
import 'bootstrap/dist/js/bootstrap.bundle.min.js'
import './assets/main.scss'
```

- 커스터마이즈는 SCSS 변수 오버라이드로 한다. 인라인 스타일을 쓰지 않는다

```scss
// assets/main.scss
$primary: #0d6efd;
$font-family-sans-serif: 'Pretendard', system-ui, sans-serif;
@import 'bootstrap/scss/bootstrap';
```

- 모달/토스트는 Bootstrap JS API를 직접 호출하기보다 Vue 상태로 제어하는
  얇은 래퍼 컴포넌트(`BaseModal.vue`, `ToastHost.vue`)를 만들어 쓴다

### 공용 컴포넌트

| 컴포넌트 | 용도 |
|----------|------|
| `BaseModal.vue` | 확인/입력 모달 |
| `ToastHost.vue` | 전역 토스트 (저장 완료, 오류) |
| `ProgressBar.vue` | 진행률 표시 |
| `StatusBadge.vue` | 상태 배지 (미시작/임시저장/제출완료) |
| `DataTable.vue` | 정렬·페이지네이션 테이블 |
| `UserSelect.vue` | 검색 가능한 사용자 선택 |
| `ConfirmLeave.vue` | 이탈 방지 훅 |

## 6. UX 규칙

| 상황 | 처리 |
|------|------|
| 로딩 | 스켈레톤 또는 스피너. 레이아웃 점프 방지 |
| 빈 목록 | 안내 문구 + 다음 행동 버튼 |
| 저장 성공 | 토스트 (3초 자동 사라짐) |
| 저장 실패 | 토스트(오류) + 재시도 버튼. 입력값은 보존 |
| 파괴적 동작 | 확인 모달 (삭제, 제출, 회차 마감, 반려) |
| 권한 없음 | `/403` 이동 |
| 네트워크 오류 | "일시적인 오류입니다. 다시 시도해 주세요." |

## 7. 접근성 / 반응형

- 모든 입력에 `<label>` 연결
- 점수 라디오 그룹에 `aria-label`로 항목명 제공
- 키보드만으로 평가지 작성·제출이 가능해야 한다
- 색상만으로 상태를 구분하지 않는다 (배지에 텍스트 병기)
- 데스크톱 우선. 태블릿(768px)까지 테이블이 가로 스크롤로 동작하면 충분하다
