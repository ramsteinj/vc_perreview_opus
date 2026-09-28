# 12. Render 배포 가이드 (무료 플랜)

[Render](https://render.com)에 **모든 리소스를 무료 플랜으로** 배포하는 절차다.
저장소 루트의 [`render.yaml`](../render.yaml)(Blueprint) 하나로 전체 구성을 만든다.

> 무료 플랜 조건은 2026-09-28에 Render 공식 문서로 확인했다. 조건은 바뀔 수 있으므로
> 배포 전에 [Free instances](https://render.com/docs/free) 문서를 한 번 더 확인한다.

## 1. 구성

```
브라우저 ──▶ vc-perreview        정적 사이트 (Vue SPA)      CDN, 잠들지 않음
         │
         └─▶ vc-perreview-api    웹 서비스 (Django + gunicorn)  15분 무활동 시 잠듦
                  │
                  └─▶ vc-perreview-db   Postgres 16            생성 30일 후 만료
```

| 리소스 | Render 유형 | 주소 (이름을 그대로 받았을 때) |
|--------|-------------|-------------------------------|
| `vc-perreview` | Static Site | `https://vc-perreview.onrender.com` |
| `vc-perreview-api` | Web Service (Python) | `https://vc-perreview-api.onrender.com` |
| `vc-perreview-db` | Postgres | 내부 연결만 사용 |

리전은 한국에서 가장 가까운 **싱가포르**다. API와 DB는 같은 리전이어야 내부 연결을 쓴다.

프론트엔드는 정적 사이트로 분리했다. 웹 서비스는 잠들지만 정적 사이트는 CDN에서 제공되어
항상 즉시 뜬다. 대신 프론트엔드가 다른 도메인의 API를 직접 호출하므로 CORS 설정이 필요하다 (§6).

## 2. 무료 플랜 제약 — 반드시 알아둘 것

| 제약 | 내용 | 이 앱에서의 영향 |
|------|------|------------------|
| **Postgres 30일 만료** | 생성 30일 후 만료, 14일 유예 후 삭제. 백업 없음 | **데이터가 사라진다.** 만료 전에 백업·재생성해야 한다 (§8) |
| Postgres 1개 | 워크스페이스당 무료 DB는 1개, 용량 1GB | 새 DB를 만들려면 기존 DB를 먼저 지워야 한다 |
| 웹 서비스 잠듦 | 15분간 요청이 없으면 잠들고, 깨는 데 약 1분 | 오래 쉬었다 들어오면 첫 요청이 1분가량 걸린다 (§7) |
| 인스턴스 시간 | 워크스페이스당 월 750시간 | API 1개를 한 달 내내 켜도 충분하다. 같은 워크스페이스의 다른 무료 서비스와 나눠 쓴다 |
| pre-deploy 명령 없음 | 유료 플랜 전용 | 마이그레이션을 시작 명령에서 실행한다 |
| Shell 접속 없음 | 유료 플랜 전용 | `manage.py` 명령을 서버에서 직접 실행할 수 없다 |
| 영구 디스크 없음 | 재배포·재시작 시 파일이 사라진다 | 이 앱은 업로드 파일을 저장하지 않으므로 영향 없음 |
| 빌드 시간 | 월 빌드 시간이 무료 한도에 포함 | push할 때마다 두 서비스가 모두 빌드된다 |

**30일 만료가 가장 중요하다.** 실제 평가 운영(회차 한 번에 몇 주)에 쓰려면 만료일 전에 반드시
백업해야 하고, 회차가 30일을 넘길 것 같으면 DB만이라도 유료 플랜을 고려한다.

## 3. 저장소에 추가·변경된 것

| 파일 | 내용 |
|------|------|
| `render.yaml` | Blueprint. DB 1 + 웹 서비스 1 + 정적 사이트 1 |
| `backend/config/settings/prod.py` | Render 호스트 자동 허용, 기본 관리자 비밀번호 필수화, WhiteNoise, DB 연결 재사용 |
| `backend/config/settings/base.py` | `CORS_EXPOSE_HEADERS = ['Content-Disposition']` |
| `backend/requirements.txt` | `whitenoise` 추가 (Django Admin 정적 파일) |
| `frontend/src/api/client.js` | API 주소·타임아웃을 빌드 시 환경 변수로 받음 |
| `frontend/src/api/system.js` | `wakeServer()` — 로그인 화면이 열리면 API를 미리 깨움 |
| `frontend/.env.example` | 프론트엔드 빌드 변수 설명 |

### 3.1 운영 설정의 주요 결정

| 항목 | 설정 | 이유 |
|------|------|------|
| `DEFAULT_ADMIN_PASSWORD` | 기본값 없음 (필수) | 공개 서버에 `admin1234!`가 그대로 쓰이는 것을 막는다 |
| `ALLOWED_HOSTS` | `RENDER_EXTERNAL_HOSTNAME` 자동 추가 | Render가 넣어주는 값. 헬스체크도 이 Host로 온다 |
| gunicorn | 워커 1개, 스레드 4개 | 로그인 시도 제한 카운터가 프로세스 메모리에 있어 워커가 여러 개면 제한이 느슨해진다. 무료 CPU는 0.1 |
| 마이그레이션 | 시작 명령에서 실행 | 무료 플랜에 pre-deploy 명령이 없다 |
| `PYTHON_VERSION` | `3.12.3` | Render 기본값(3.14)은 고정한 의존성과 맞지 않는다 |
| `CONN_HEALTH_CHECKS` | `True` | 무료 DB는 수시로 재시작될 수 있어 끊긴 연결을 재사용하지 않게 한다 |
| API 타임아웃 | 운영 90초 (개발 15초) | 잠든 API가 깨는 데 약 1분 걸린다 |

## 4. 사전 준비

1. **GitHub에 최신 코드를 push한다.** Render는 GitHub 저장소에서 빌드한다
2. [Render](https://dashboard.render.com)에 가입한다 (GitHub 계정으로 가입하면 연결이 쉽다)
3. **관리자 비밀번호를 정한다.** 배포할 때 한 번 입력한다. 10자 이상, 흔하지 않은 값

## 5. 배포 절차

### 5.1 Blueprint로 한 번에 만들기

1. Render 대시보드 → **New +** → **Blueprint**
2. GitHub 저장소 `vc_perreview_opus`를 연결하고 선택한다
   (처음이면 GitHub 권한 부여 화면이 나온다. 이 저장소만 허용해도 된다)
3. **Blueprint Name**을 입력한다 (예: `vc-perreview`). 브랜치는 `main`
4. Render가 `render.yaml`을 읽어 만들 리소스 3개를 보여준다. 모두 **Free**인지 확인한다
5. `DEFAULT_ADMIN_PASSWORD` 입력란에 4에서 정한 관리자 비밀번호를 넣는다
6. **Apply** (또는 **Deploy Blueprint**)

DB → API → 정적 사이트 순으로 만들어진다. 처음에는 5~10분 정도 걸린다.

### 5.2 진행 확인

대시보드에서 각 서비스를 눌러 **Events / Logs**를 본다.

**`vc-perreview-api` 로그에서 확인할 것:**

```
Applying accounts.0001_initial... OK
...
기본 관리자 계정을 생성했습니다 (사번: ADMIN).
Listening at: http://0.0.0.0:10000
```

상태가 **Live**가 되면 준비된 것이다.

**`vc-perreview` 빌드 로그 마지막:**

```
✓ built in ...
```

### 5.3 주소 확인 — 중요

각 서비스 상단에 실제 주소가 표시된다. **이름이 이미 다른 사람에게 쓰이고 있으면 Render가
주소 뒤에 임의 문자열을 붙인다** (예: `vc-perreview-api-x7k2.onrender.com`).

| 서비스 | 기대 주소 |
|--------|-----------|
| API | `https://vc-perreview-api.onrender.com` |
| 정적 사이트 | `https://vc-perreview.onrender.com` |

**둘 다 기대 주소와 같으면 §5.4로 넘어간다.** 하나라도 다르면 §6을 먼저 한다.

### 5.4 동작 확인

1. `https://vc-perreview-api.onrender.com/api/health/` →
   `{"status":"ok","db":"ok"}`
2. `https://vc-perreview.onrender.com` → 로그인 화면
3. 성명 `ADMIN` / 사번 `ADMIN` / 비밀번호: §5.1에서 입력한 값 → 대시보드
4. **즉시 비밀번호를 변경한다** (상단 사용자 메뉴 → 비밀번호 변경)
5. 부서·사용자를 등록하고 회차를 만들어 사용을 시작한다

> **Django Admin(`/admin/`)에는 로그인할 수 없다.** 로그인 백엔드가 성명까지 검증하는데
> Django Admin 로그인 폼은 성명을 보내지 않기 때문이다 (배포와 무관하게 개발 환경에서도 같다).
> 모든 관리 기능은 앱의 관리자 화면에서 쓸 수 있다.

## 6. 주소가 기대와 다를 때

프론트엔드와 API는 서로의 주소를 알아야 한다. Render가 붙인 주소로 두 값을 고친다.

**1) API 서비스 → Environment**

| 키 | 값 |
|----|----|
| `CORS_ALLOWED_ORIGINS` | 정적 사이트의 실제 주소 (예: `https://vc-perreview-ab12.onrender.com`) |

저장하면 API가 자동으로 재배포된다.

**2) 정적 사이트 → Environment**

| 키 | 값 |
|----|----|
| `VITE_API_BASE_URL` | API의 실제 주소 + `/api` (예: `https://vc-perreview-api-x7k2.onrender.com/api`) |

`VITE_*` 값은 **빌드할 때 번들에 들어간다.** 저장 후 **Manual Deploy → Clear build cache & deploy**로
다시 빌드해야 반영된다.

3) 다음 배포부터 같은 값이 유지되도록 `render.yaml`의 두 값도 실제 주소로 고쳐 push한다.
Blueprint는 저장소의 `render.yaml`을 기준으로 동기화하기 때문이다.

**증상으로 알아보기:** 로그인 버튼을 눌렀는데 아무 반응이 없고, 브라우저 개발자 도구 콘솔에
`CORS policy` 또는 `ERR_NAME_NOT_RESOLVED`가 보이면 이 절의 문제다.

## 7. 잠든 API 깨우기 (콜드 스타트)

무료 웹 서비스는 15분간 요청이 없으면 잠든다. 다음 요청이 오면 깨어나는 데 약 1분 걸린다.

이 앱이 대응하는 방식:

- 프론트엔드의 API 타임아웃을 **90초**로 늘렸다 (`VITE_API_TIMEOUT`). 1분 대기 중에 실패하지 않는다
- 로그인 화면이 열리면 즉시 `/api/health/`를 호출해 **사용자가 입력하는 동안 서버를 깨운다**
- 이미 로그인한 사용자가 새로고침하면 세션 복구 요청이 서버를 깨운다

그래도 오래 쉬었다 들어오면 첫 화면이나 로그인이 **30초~1분 정도 느릴 수 있다.** 정상이다.
평가 기간처럼 사용자가 몰리는 동안에는 요청이 이어져 잠들지 않는다.

항상 깨어 있게 하려면 외부 모니터링 서비스로 `/api/health/`를 14분마다 호출하는 방법이 있다.
다만 월 750시간 안에서 운영되는지 확인하고, Render 이용 약관을 따른다.

## 8. DB 30일 만료 대응 — 백업과 재생성

무료 Postgres는 **생성 30일 후 만료**되고 14일 유예 후 **삭제**된다. 백업 기능도 없다.
만료 전에 직접 백업해 새 DB로 옮겨야 한다. **만료일을 달력에 적어 둔다** (DB 페이지에 표시된다).

필요한 것: 로컬 PC의 `pg_dump`, `pg_restore` (PostgreSQL 16 이상 클라이언트)

### 8.1 백업

1. Render 대시보드 → `vc-perreview-db` → **Connect** → **External Database URL** 복사
2. 로컬에서:

```bash
export RENDER_DB_URL='postgresql://perreview:...@...singapore-postgres.render.com/perreview'
pg_dump --format=custom --no-owner --no-privileges "$RENDER_DB_URL" -f perreview-$(date +%Y%m%d).dump
```

`.dump` 파일이 생기면 백업이 끝난 것이다. **이 파일에는 개인정보와 평가 결과가 들어 있다.**
안전한 곳에 보관하고 저장소에 커밋하지 않는다.

### 8.2 새 DB로 옮기기

무료 DB는 워크스페이스당 1개라 **기존 DB를 먼저 지워야** 새로 만들 수 있다.
반드시 §8.1의 백업 파일을 확인한 뒤 진행한다.

1. `vc-perreview-db` → **Settings** → **Delete Database**
2. Blueprint 페이지 → **Manual Sync**
   `render.yaml`에 정의된 DB가 없으므로 같은 이름으로 새로 만들고, API의 `DATABASE_URL`도 새 DB로 연결한다
3. API가 재배포되며 빈 DB에 마이그레이션을 실행하고 관리자 계정을 새로 만든다.
   API가 **Live**가 된 뒤, 백업으로 새 DB를 덮어쓴다:

```bash
export NEW_DB_URL='(새 DB의 External Database URL)'
pg_restore --clean --if-exists --no-owner --no-privileges -d "$NEW_DB_URL" perreview-YYYYMMDD.dump
```

   `--clean`은 새 DB의 테이블을 지우고 백업의 구조와 데이터로 다시 만든다.
   Render의 DB 사용자는 superuser가 아니지만 테이블 소유자이므로 이 방식은 동작한다.
   (`--data-only --disable-triggers` 방식은 superuser 권한이 필요해 **실패한다**)

   로컬 클라이언트가 서버(16)보다 새 버전이면
   `unrecognized configuration parameter "transaction_timeout"` 오류가 한 줄 나온다.
   무시해도 되며 복원 결과에는 영향이 없다.

4. API 서비스 → **Manual Deploy → Restart service**
5. 기존 관리자 비밀번호로 로그인되고 이전 데이터가 보이는지 확인한다

Blueprint 동기화가 DB를 만들지 않으면, **New + → Postgres**로 같은 이름·리전(Singapore)·무료 플랜의
DB를 직접 만들고, API의 `DATABASE_URL`을 새 DB의 **Internal Database URL**로 바꾼다.

## 9. 일상 운영

| 작업 | 방법 |
|------|------|
| 코드 반영 | `main`에 push하면 두 서비스가 자동으로 다시 빌드·배포된다 |
| 로그 보기 | 서비스 → **Logs**. 감사 로그는 `[AUDIT]`로 검색한다 |
| 환경 변수 변경 | 서비스 → **Environment**. API는 저장 즉시 재배포, 정적 사이트는 다시 빌드해야 반영 |
| 재시작 | 서비스 → **Manual Deploy → Restart service** |
| 되돌리기 | 서비스 → **Events**에서 이전 배포의 **Rollback** |

`SECRET_KEY`를 바꾸면 발급된 모든 로그인 토큰이 무효가 되어 전원이 다시 로그인해야 한다.

## 10. 문제 해결

| 증상 | 원인 | 해결 |
|------|------|------|
| API 빌드 실패: `psycopg`·`Django` 설치 오류 | Python 버전 | `PYTHON_VERSION=3.12.3`이 설정되어 있는지 확인 |
| API 로그: `ImproperlyConfigured ... DEFAULT_ADMIN_PASSWORD` | 관리자 비밀번호 미입력 | API → Environment에 `DEFAULT_ADMIN_PASSWORD` 추가 |
| API 로그: `DisallowedHost` | 커스텀 도메인 등 다른 Host | Environment에 `ALLOWED_HOSTS=도메인` 추가 |
| 로그인 시 콘솔에 `CORS policy` | 정적 사이트 주소가 `CORS_ALLOWED_ORIGINS`와 다름 | §6 |
| 로그인 버튼이 1분 가까이 돈다 | API가 잠들어 있었음 | 정상 (§7). 두 번째부터는 빠르다 |
| 1분 넘게 기다린 뒤 "일시적인 오류" | 재배포 중이거나 월 750시간 소진 | API의 Events 확인 |
| 새로고침하면 404 | SPA 폴백 규칙 누락 | 정적 사이트 → Redirects/Rewrites에 `/*` → `/index.html` (Rewrite) |
| CSV 파일명이 `scores.csv` | `Content-Disposition` 노출 안 됨 | API가 최신 코드로 배포되었는지 확인 (`CORS_EXPOSE_HEADERS`) |
| Django Admin 화면이 스타일 없이 깨짐 | `collectstatic` 미실행 | API 빌드 명령에 `collectstatic`이 있는지 확인 |
| 데이터가 전부 사라짐 | DB 30일 만료로 삭제 | §8의 백업에서 복원. 백업이 없으면 복구할 수 없다 |

## 11. 유료 플랜으로 옮길 때

사용자가 늘거나 DB 만료가 부담되면 일부만 유료로 바꿀 수 있다. 우선순위:

1. **Postgres** — 만료·삭제가 없어지고 백업이 생긴다. 가장 효과가 크다
2. **웹 서비스** — 잠들지 않고, pre-deploy 명령을 쓸 수 있다.
   그때는 `startCommand`에서 `migrate`를 빼고 `preDeployCommand: python manage.py migrate --no-input`으로 옮긴다
   (배포 실패 시 이전 버전이 계속 서비스되어 더 안전하다)

정적 사이트는 유료로 바꿀 필요가 없다.

## 12. 로컬에서 운영 설정 점검하기

배포 전에 `render.yaml`의 명령을 로컬에서 그대로 돌려볼 수 있다. HTTP로 점검하므로 HTTPS 리다이렉트만 끈다.

```bash
docker compose up -d
docker compose exec -T db psql -U perreview -d postgres -c "CREATE DATABASE perreview_render;"

cd backend
export DJANGO_SETTINGS_MODULE=config.settings.prod
export SECRET_KEY=local-check-secret DEFAULT_ADMIN_PASSWORD='Local!Check2026'
export DATABASE_URL=postgres://perreview:perreview@localhost:5433/perreview_render
export RENDER_EXTERNAL_HOSTNAME=127.0.0.1 CORS_ALLOWED_ORIGINS=http://127.0.0.1:8200
export SECURE_SSL_REDIRECT=False PORT=8100

python manage.py collectstatic --no-input
python manage.py migrate --no-input && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 1 --threads 4

# 다른 터미널
cd frontend
VITE_API_BASE_URL=http://127.0.0.1:8100/api VITE_API_TIMEOUT=90000 npm run build
npx vite preview --host 127.0.0.1 --port 8200
```

`http://127.0.0.1:8200`에서 로그인·새로고침·CSV 다운로드가 되면 배포 구성도 동작한다.
점검이 끝나면 `backend/staticfiles/`와 `frontend/dist/`를 지운다 (둘 다 `.gitignore` 대상).
