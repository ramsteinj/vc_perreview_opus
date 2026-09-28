# 11. E2E 테스트 가이드 (Playwright + Chrome)

브라우저에서 실제 사용자 흐름을 끝까지 검증하는 E2E 테스트의 구성·실행·작성 규칙이다.
테스트 코드는 저장소 루트의 [`tests/`](../tests/)에 있다.

## 1. 역할 분담

E2E는 백엔드 테스트(pytest)를 대체하지 않는다. 같은 것을 두 번 검증하지 않도록 나눈다.

| 계층 | 도구 | 검증 대상 |
|------|------|-----------|
| 백엔드 단위·API | pytest (`backend/apps/*/tests/`) | 점수 계산식, DB 제약, 권한, 동시성, 경계값, 오류 코드 |
| **E2E** | **Playwright** (`tests/e2e/`) | 화면에서 사용자가 겪는 흐름, 화면과 API의 연결, 브라우저 동작 |

E2E에 넣는 것:

- 로그인 → 이동 → 입력 → 저장 → 새로고침 후 복원처럼 **여러 화면을 가로지르는 흐름**
- 진행률 즉시 갱신, 자동 저장, 이탈 방지 확인창처럼 **브라우저에서만 드러나는 동작**
- 파일 다운로드·업로드, 한글 파일명, CSV BOM처럼 **브라우저와 서버가 맞물리는 지점**
- 스펙의 대표 예시값이 화면까지 올바르게 전달되는지 (예: 최종 점수 88.40)

E2E에 넣지 않는 것:

- 계산식의 모든 경계값 — `test_scoring.py`의 12개 필수 케이스가 담당한다
- 오류 코드 조합 전수 검사 — API 테스트가 담당한다
- 동시 제출의 DB 직렬화 — `test_concurrency.py`가 실제 스레드로 검증한다

## 2. 구성

### 2.1 디렉터리

```
tests/
├── package.json              # @playwright/test, 실행 스크립트
├── playwright.config.js      # 프로젝트(chromium/chrome), webServer, 리포터
├── scripts/
│   ├── start-backend.sh      # E2E DB 준비 + 백엔드 기동 (webServer가 호출)
│   └── ensure_db.py          # perreview_e2e DB가 없으면 생성
└── e2e/
    ├── support/
    │   ├── env.js            # 포트·URL
    │   ├── data.js           # 고유 ID, 날짜, 비밀번호, ADMIN 계정
    │   ├── api.js            # 테스트 데이터 준비용 API 클라이언트
    │   └── fixtures.js       # test.extend: api, loginAs / 헬퍼: toast, dialog
    ├── auth.spec.js          # 로그인 · 세션 · 권한
    ├── admin-master.spec.js  # 부서 · 사용자 · CSV 일괄 등록
    ├── cycle-setup.spec.js   # 회차 · 항목 · 가중치 · 평가자 배정
    ├── evaluation.spec.js    # 직원 평가 응답
    ├── monitoring.spec.js    # 응답 현황 · 반려
    └── scoring-export.spec.js# 점수 산출 · CSV 내보내기
```

### 2.2 개발 환경과의 격리

E2E는 **개발 DB와 개발 서버를 건드리지 않는다.** 개발 서버를 띄워 둔 채로 E2E를 돌려도 된다.

| 항목 | 개발 | E2E |
|------|------|-----|
| DB | `perreview` | `perreview_e2e` (같은 PostgreSQL 컨테이너) |
| 백엔드 | `localhost:8000`, `config.settings.dev` | `127.0.0.1:8001`, `config.settings.e2e` |
| 프론트엔드 | `localhost:5173` | `127.0.0.1:5174` (프록시 → 8001) |

`config.settings.e2e`는 dev 설정을 상속하고 **요청 제한만 완화**한다.
E2E는 한 IP에서 수십 번 로그인·다운로드하므로 운영용 제한(login 30/hour, export 10/hour)을
그대로 두면 테스트가 막힌다. 사번 단위 로그인 잠금은 그대로 둔다.

Vite 프록시 대상은 `VITE_API_PROXY_TARGET` 환경 변수로 바꾼다 (`frontend/vite.config.js`).

### 2.3 실행 흐름

```
npx playwright test
   │
   ├─ webServer[0]  scripts/start-backend.sh
   │     ├─ ensure_db.py      perreview_e2e 없으면 생성
   │     ├─ migrate
   │     ├─ flush             데이터 전체 삭제 → post_migrate로 기본 ADMIN 재생성
   │     └─ runserver 127.0.0.1:8001
   │
   ├─ webServer[1]  vite dev --port 5174   (VITE_API_PROXY_TARGET=http://127.0.0.1:8001)
   │
   └─ 테스트 병렬 실행 → 종료 시 두 서버 정리
```

매 실행마다 DB가 비워진 상태에서 시작한다. 실행 사이에 상태가 새지 않는다.

## 3. 준비

### 3.1 사전 조건

README의 개발 환경 구성을 먼저 마친다.

```bash
docker compose up -d                 # PostgreSQL (호스트 5433)
cd backend && uv venv .venv && uv pip install -r requirements.txt   # 또는 python -m venv
cd frontend && npm install
```

### 3.2 Playwright 설치

```bash
cd tests
npm install
npm run install:browsers             # = npx playwright install chromium
```

### 3.3 브라우저 선택: Chromium과 Google Chrome

두 프로젝트가 정의되어 있다.

| 프로젝트 | 브라우저 | 설치 | 용도 |
|----------|----------|------|------|
| `chromium` (기본) | Playwright 번들 Chromium | `npx playwright install chromium` (sudo 불필요) | 로컬 개발, CI |
| `chrome` | 실제 Google Chrome (`channel: 'chrome'`) | `sudo npx playwright install chrome` | 배포 전 실브라우저 확인 |

Chromium은 Chrome과 같은 렌더링 엔진(Blink)과 JS 엔진(V8)을 쓴다. 일상적인 검증은
`chromium`으로 충분하고, 배포 전에 실제 사용자 환경과 같은 `chrome`으로 한 번 더 돌린다.

`npm test`는 **`chromium` 프로젝트만** 돌린다. Google Chrome이 설치되지 않은 환경에서
실패하지 않게 하기 위함이다.

## 4. 실행

`tests/` 디렉터리에서 실행한다.

| 명령 | 설명 |
|------|------|
| `npm test` | 전체 실행 (Chromium, 헤드리스, 병렬) |
| `npm run test:chrome` | Google Chrome으로 전체 실행 |
| `npm run test:headed` | 브라우저 창을 띄워 실행 |
| `npm run test:ui` | Playwright UI 모드 (시간 여행 디버깅) |
| `npm run test:debug` | Playwright Inspector로 한 단계씩 실행 |
| `npm run report` | 마지막 HTML 리포트 열기 |

자주 쓰는 옵션:

```bash
npx playwright test e2e/evaluation.spec.js              # 파일 하나
npx playwright test -g "임시 저장"                       # 제목으로 거르기
npx playwright test --project=chromium --repeat-each=5  # flaky 여부 확인
E2E_VERBOSE=1 npx playwright test                       # 서버 로그 보기
```

실패하면 `test-results/<테스트명>/`에 스크린샷·영상·trace가 남는다.

```bash
npx playwright show-trace test-results/<테스트명>/trace.zip
```

### 4.1 환경 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `E2E_BACKEND_PORT` | `8001` | E2E 백엔드 포트 |
| `E2E_FRONTEND_PORT` | `5174` | E2E 프론트엔드 포트 |
| `E2E_DATABASE_URL` | `postgres://perreview:perreview@localhost:5433/perreview_e2e` | E2E DB |
| `E2E_VERBOSE` | (없음) | 설정하면 서버 로그를 출력 |
| `CI` | (없음) | 설정하면 재시도 2회, 워커 2개, `test.only` 금지, 서버 재사용 안 함 |

## 5. 작성 규칙

### 5.1 준비는 API로, 검증은 UI로

검증 대상이 아닌 준비 단계는 `api` fixture로 빠르게 만든다. UI는 테스트가 실제로 확인하려는
흐름에만 쓴다.

```js
test('임시 저장 후 새로고침하면 입력이 복원된다', async ({ page, api, loginAs }) => {
  const { evaluator } = await api.seedOpenEvaluation()   // 준비: API
  await loginAs(evaluator, '/my/evaluations')             // 준비: 토큰 주입

  await page.getByRole('button', { name: '평가하기' }).click()   // 검증: UI
  ...
})
```

`Api`의 주요 메서드:

| 메서드 | 내용 |
|--------|------|
| `createDepartment()` / `createUser()` | 부서·사용자 생성. `createUser`는 로그인 정보(`employeeNo`, `password`)를 함께 돌려준다 |
| `createCycle()` / `createStandardItems(cycleId, type)` | 회차, 가중치 50/30/20 항목 3개 |
| `assign(cycleId, {...})` / `openCycle(cycleId)` | 평가자 배정, 회차 열기(confirm 포함) |
| `submitSheet(user, assignmentId, scores)` | 해당 평가자로 평가지 작성·제출 |
| `calculate(cycleId)` | 점수 산출 |
| `seedOpenEvaluation({ secondary })` | 평가 1건이 진행 가능한 최소 구성 한 번에 |

### 5.2 테스트는 서로 독립이어야 한다

테스트는 **병렬로** 돈다 (`fullyParallel: true`). 한 테스트가 다른 테스트의 데이터에 기대면 안 된다.

- 사번·부서코드·회차명은 `uid()`로 고유하게 만든다. 고정값을 쓰지 않는다
- **목록에서 방금 만든 항목을 위치로 찾지 않는다.** 목록은 페이지로 나뉘고 데이터가 누적될 수 있다.
  검색창으로 좁힌 뒤 찾는다 (예: 회차명 검색, 사번 검색)
- **전역 개수를 단언하지 않는다.** "사용자가 3명이다"는 다른 테스트가 만든 사용자 때문에 깨진다.
  자기가 만든 데이터로 범위를 좁혀서(검색, 회차 ID) 단언한다
- 회차를 열 때 다른 테스트의 사용자가 항상 미배정 상태로 존재한다. `openCycle`은 `confirm=true`를 쓰고,
  UI로 열 때는 "미배정 대상이 있습니다" 확인창을 거친다

### 5.3 로그인: `loginAs`와 UI 로그인

| 상황 | 방법 |
|------|------|
| 로그인 흐름 자체를 검증 (`auth.spec.js`) | 로그인 폼을 직접 채운다 |
| 그 밖의 모든 테스트 | `loginAs(user, path)` |

`loginAs`는 API로 로그인해 refresh 토큰을 받아 **앱이 부팅되기 전에** localStorage에 심는다
(`page.addInitScript`). 두 가지를 주의해서 만들었다.

1. `page.evaluate`로 이미 열린 페이지에 심으면 안 된다. 그 페이지의 앱이 부팅 중 refresh를 회전시키며
   새 토큰을 늦게 써서 방금 심은 토큰을 덮어쓴다. 같은 테스트에서 사용자를 바꿀 때 병렬 부하에서만
   드러나는 경쟁 조건이었다
2. init script는 매 탐색마다 실행되므로 그대로 두면 새로고침할 때 이미 회전·폐기된 옛 토큰으로 되돌린다.
   sessionStorage 플래그로 1회만 심는다

같은 이유로 `storageState`로 로그인 상태를 저장해 재사용하지 않는다. refresh 토큰 회전
(`ROTATE_REFRESH_TOKENS` + `BLACKLIST_AFTER_ROTATION`) 때문에 저장된 토큰은 한 번 쓰면 무효가 된다.

### 5.4 선택자

우선순위: `getByRole` > `getByLabel` > `getByText` > CSS 선택자.
사용자에게 보이는 것(역할·레이블·문구)으로 찾아야 마크업이 바뀌어도 테스트가 유지된다.

| 대상 | 방법 |
|------|------|
| 모달 | `dialog(page, '모달 제목')` — 제목(heading)으로 특정한 `role=dialog` |
| 토스트 | `toast(page, '문구')` |
| 모달 안 입력 | `dialog(...).getByLabel('사번')` — 페이지 필터의 "검색 (사번 · 성명)"과 겹치지 않게 모달로 좁힌다 |
| 이름이 겹치는 레이블 | `getByLabel('비밀번호', { exact: true })` — "비밀번호 표시" 버튼과 구분 |
| 점수 버튼 | `getByRole('group', { name: '업무 성과 점수' })` 안의 `label`을 클릭, `input[type=radio]`로 선택 확인 |

**표의 행은 첫 번째 칸으로 찾는다.** 배정 화면처럼 행마다 사용자 `<select>`가 있으면 모든 행의
텍스트에 모든 사용자 이름이 `<option>`으로 들어간다. `tr.filter({ hasText })`는 모든 행에 걸린다.

```js
function rowByFirstCell(page, text) {
  return page.locator('tbody tr').filter({ has: page.locator('td:first-child', { hasText: text }) })
}
```

같은 문구가 두 곳에 있으면(예: "잠정 결과"가 제목 배지와 경고문에) strict 모드 위반이 난다.
둘 중 무엇을 확인하려는지 범위를 좁혀서 명시한다.

### 5.5 기다리기

- `page.waitForTimeout()`을 쓰지 않는다. `expect(...)`는 조건이 맞을 때까지 자동으로 재시도한다
- 자동 저장처럼 시간이 걸리는 동작은 결과(예: "마지막 저장:" 문구)를 기다리고 타임아웃만 늘린다

```js
await expect(page.getByText(/마지막 저장: /)).toBeVisible({ timeout: 8_000 })
```

### 5.6 브라우저 이벤트

```js
// window.confirm (이탈 방지)
page.once('dialog', (message) => message.dismiss())

// 파일 다운로드
const [download] = await Promise.all([
  page.waitForEvent('download'),
  page.getByRole('button', { name: 'CSV 다운로드' }).click(),
])
// download.path()는 원격 브라우저에 연결해 실행하면 쓸 수 없다. saveAs()를 쓴다
const saved = testInfo.outputPath(download.suggestedFilename())
await download.saveAs(saved)
const bytes = await readFile(saved)

// 파일 업로드 (디스크에 파일을 만들지 않는다)
await input.setInputFiles({ name: 'users.csv', mimeType: 'text/csv', buffer: Buffer.from(text) })

// 네트워크 관찰 (중복 제출 확인)
page.on('response', (res) => { if (res.url().includes('/submit/')) statuses.push(res.status()) })
```

### 5.7 새 테스트를 추가할 때

1. 검증하려는 스펙 항목(FR 번호)을 정한다. 파일 첫 줄 주석에 스펙 위치를 적는다
2. 백엔드 테스트로 충분한 것이면 E2E에 넣지 않는다 (§1)
3. 준비는 `api`로, 검증 흐름만 UI로 쓴다
4. 새로 추가한 테스트는 `--repeat-each=5`로 돌려 flaky가 아닌지 확인한다

## 6. 현재 시나리오

53개 테스트, 6개 파일.

### `auth.spec.js` — 로그인 · 세션 · 권한 (03-auth.md, FR-E-01)

| 테스트 | 스펙 |
|--------|------|
| 기본 관리자로 로그인하면 대시보드로 이동 | FR-A-01 |
| 기본 비밀번호 사용 시 변경 안내 배너 | 03-auth §5 |
| 직원은 내 평가 화면으로 이동 | FR-E-01 |
| 성명이 다르면 로그인 실패 | FR-E-01 수용 기준 |
| 실패 사유를 구분하지 않음 (사용자 열거 방지) | 03-auth §1 |
| 빈 칸 제출 시 필드별 안내 / 비밀번호 표시 토글 | 08-frontend §4.1 |
| 새로고침해도 세션 유지 | FR-E-01 수용 기준 |
| 미로그인 시 로그인 화면 → 로그인 후 원래 경로로 복귀 | 08-frontend §1 |
| 로그아웃 후 새로고침해도 복구되지 않음 | 03-auth §2 |
| 직원이 관리자 화면 접근 시 403 / 관리자 메뉴 없음 | 03-auth §4 |
| 비밀번호 변경 후 새 비밀번호로만 로그인 | 03-auth §3 |

### `admin-master.spec.js` — 부서 · 사용자 (FR-A-02, FR-A-03)

| 테스트 | 스펙 |
|--------|------|
| 부서 생성 → 하위 부서 추가 → 트리 표시 | FR-A-03 수용 기준 |
| 상위 부서 선택지에서 자신과 자손 제외 (순환 방지) | FR-A-03 수용 기준 |
| 소속 직원이 있는 부서는 비활성화만 가능 | FR-A-03 수용 기준 |
| 임시 비밀번호 발급 → 그 비밀번호로 로그인 | FR-A-02 |
| 중복 사번 오류 / 사번 검색 | FR-A-02 수용 기준 |
| 비활성화한 사용자는 로그인 불가 | FR-A-02 수용 기준 |
| 관리자 본인 행의 비활성화 버튼 비활성 | 08-frontend |
| CSV 일괄 등록 성공 (쉼표 포함 성명) | FR-A-02 일괄 등록 |
| CSV 오류 1행이라도 있으면 전체 미등록 + 행별 사유 | FR-A-02 수용 기준 |

### `cycle-setup.spec.js` — 회차 · 항목 · 배정 (FR-A-04, FR-A-05, FR-A-10)

| 테스트 | 스펙 |
|--------|------|
| 회차 생성 | FR-A-10 |
| 가중치 합계 ≠ 100이면 경고 배지 + OPEN 거부 | FR-A-04 수용 기준 |
| 가중치 100이면 합계 배지 정상 | FR-A-04 |
| 2차 평가자 없이 배정 저장 | FR-A-05 수용 기준 |
| 평가자 선택지에 피평가자 본인 없음 | FR-A-05 수용 기준 |
| 미배정 대상이 있으면 확인 후 OPEN | FR-A-10 |

### `evaluation.spec.js` — 직원 평가 응답 (FR-E-02 ~ FR-E-06)

| 테스트 | 스펙 |
|--------|------|
| 배정 대상이 미시작으로 표시 / 배정 없으면 안내 | FR-E-02 |
| 문항별 가중치 표시 | FR-E-03 |
| 점수 선택 시 진행률 즉시 갱신 | FR-E-05 |
| 임시 저장 → 새로고침 → 점수·의견·종합의견 복원 | FR-E-04 수용 기준 |
| 3초 디바운스 자동 저장 | FR-E-04 |
| 같은 점수 재클릭 시 선택 해제 | 08-frontend §4.3 |
| 저장 안 된 변경이 있으면 이탈 확인창 | FR-E-04 |
| 미입력 항목이 있으면 제출 차단 + 문항 표시 | FR-E-06 수용 기준 |
| 제출 → 제출완료 → 읽기 전용 | FR-E-06 수용 기준 |
| 제출 확인 더블 클릭에도 제출 요청 1회 | FR-E-06 수용 기준 |
| 타인의 평가지 주소 접근 차단 | FR-E-02 수용 기준 |

### `monitoring.spec.js` — 응답 현황 · 반려 (FR-A-06)

| 테스트 | 스펙 |
|--------|------|
| 미시작 건을 분모에 포함한 제출률 (50%) | FR-A-06 수용 기준 |
| 부서별 제출률 (평가자 소속 부서 기준) | FR-A-06 수용 기준 |
| 미응답자 탭에 미시작 평가자 표시 | FR-A-06 수용 기준 |
| 상세 탭 상태 필터 | FR-A-06 수용 기준 |
| 제출된 평가지 열람 | FR-A-06 6-4 |
| 반려 → 평가자 화면에서 다시 수정 가능 | FR-A-06 수용 기준 |
| 응답상세 CSV 다운로드 | FR-A-07 |

### `scoring-export.spec.js` — 점수 산출 · CSV (06-scoring.md, FR-A-07 ~ FR-A-09)

| 테스트 | 스펙 |
|--------|------|
| **스펙 §6 예시 재현: 1차 82.00 / 2차 90.00 / 개인 84.40 / 가감 +4.00 / 최종 88.40** | 06-scoring §6 |
| 마감 전에는 잠정 결과 표시 | FR-A-09 |
| 부서 성과 점수 90.00, 가감 +4.00 | FR-A-08 |
| 1차 미제출 대상은 사유와 함께 미산출 보고 | 06-scoring §8 |
| 점수 CSV: BOM(EF BB BF), 한글 파일명, 최종 점수 포함 | FR-A-07 수용 기준 |

## 7. 문제 해결

| 증상 | 원인 | 해결 |
|------|------|------|
| `PostgreSQL에 연결할 수 없습니다` | DB 컨테이너가 꺼져 있음 | 저장소 루트에서 `docker compose up -d` |
| `backend/.venv가 없습니다` | 백엔드 설치 전 | README의 백엔드 설치 절차 |
| `Timed out waiting ... from config.webServer` | 서버가 뜨지 못함 | `E2E_VERBOSE=1`로 다시 실행해 서버 로그 확인 |
| `port 5174 is already in use` | 이전 실행의 서버가 남음 | 해당 프로세스 종료, 또는 `E2E_FRONTEND_PORT` 변경 |
| `Chromium distribution 'chrome' is not found` | Google Chrome 미설치 | `sudo npx playwright install chrome`, 또는 `npm test`(Chromium) 사용 |
| `strict mode violation ... resolved to 2 elements` | 같은 문구가 여러 곳에 있음 | 범위를 좁힌다 (§5.4) |
| 같은 문구의 토스트가 2개라 strict mode 위반 | 같은 동작을 연달아 해서 앞 토스트(3초)가 남아 있음 | `toast(...).last()` |
| `Path is not available when connecting remotely` | 원격 브라우저 연결에서 `download.path()` 사용 | `download.saveAs()` (§5.6) |
| 새로 만든 항목이 목록에서 안 보여 시간 초과 | 목록이 페이지로 나뉘어 있음 | 위치에 기대지 말고 검색으로 좁힌다 (§5.2) |
| 단독으로는 통과, 전체 실행에서만 실패 | 테스트 간 데이터 의존 또는 경쟁 조건 | §5.2 확인, `--repeat-each`로 재현 |
| 사용자를 바꿨는데 이전 사용자로 로그인되어 있음 | 이미 열린 페이지에 토큰을 심음 | `loginAs`를 쓴다 (§5.3) |

### 7.1 서버 재사용과 데이터 누적

로컬에서는 이미 떠 있는 서버를 재사용한다 (`reuseExistingServer`). VS Code 확장이나 UI 모드처럼
**서버를 띄워 둔 채 여러 번 실행하면 DB 초기화(flush)가 일어나지 않아 데이터가 계속 쌓인다.**
실행할 때마다 부서·사용자·회차가 수십 개씩 늘어난다.

테스트는 고유 데이터를 쓰므로 누적되어도 통과해야 한다. 실제로 누적 데이터(부서 365, 사용자 915,
회차 348)에서 **목록이 200건·100건에서 잘리는 앱 버그**가 드러났다 (2026-09-28 수정).
누적 상태는 규모가 큰 조직을 흉내 내는 셈이라 오히려 유용하다.

처음부터 깨끗하게 돌리려면 8001/5174의 서버를 끄고 다시 실행한다. 다음 실행이 서버를 새로 띄우며
DB를 비운다.

```bash
kill $(ss -lntp | grep -E ':(8001|5174) ' | grep -oE 'pid=[0-9]+' | cut -d= -f2)
```

**백엔드 코드를 바꿨다면 반드시 서버를 재시작한다.** 백엔드는 `--noreload`로 뜨므로 재사용된 서버는
옛 코드로 돈다 (프론트엔드는 Vite가 즉시 반영한다). 새 엔드포인트가 404를 내면 이 경우다.

## 8. CI 예시

GitHub Actions 예시다. 저장소에 워크플로는 아직 없다.

```yaml
jobs:
  e2e:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env: { POSTGRES_DB: perreview, POSTGRES_USER: perreview, POSTGRES_PASSWORD: perreview }
        ports: ['5433:5432']
        options: --health-cmd "pg_isready -U perreview" --health-interval 5s --health-retries 10
    env:
      CI: 'true'
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt
      - run: cd frontend && npm ci
      - run: cd tests && npm ci && npx playwright install --with-deps chromium
      - run: cd tests && npm test
      - uses: actions/upload-artifact@v4
        if: failure()
        with: { name: playwright-report, path: tests/playwright-report }
```

## 9. 한계

- 검증 엔진은 Chromium 계열(Chrome, Edge)뿐이다. [09-non-functional.md](09-non-functional.md) §8은
  **Safari도 지원 대상**으로 정하고 있으나 E2E에는 아직 포함하지 않았다. 필요하면
  `playwright.config.js`에 `{ name: 'webkit', use: devices['Desktop Safari'] }` 프로젝트를 추가한다
  (WebKit은 Safari와 엔진은 같지만 실제 Safari와 완전히 동일하지는 않다)
- 화면 레이아웃·색상의 시각적 회귀는 검증하지 않는다
- Excel로 CSV를 여는 동작 자체는 자동화하지 않는다. BOM 바이트와 UTF-8 디코딩으로 대신 확인한다
