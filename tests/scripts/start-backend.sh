#!/usr/bin/env bash
# E2E용 백엔드를 띄운다 (Playwright webServer가 호출한다).
#
# 1. 전용 DB(perreview_e2e)가 없으면 만든다
# 2. 마이그레이션 후 모든 데이터를 비운다 (flush)
#    flush는 post_migrate를 다시 발생시키므로 기본 ADMIN 계정이 재생성된다
# 3. 127.0.0.1:8001에서 runserver를 띄운다
#
# 개발 DB(perreview)와 개발 서버(8000)는 건드리지 않는다.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT/backend"

export DJANGO_SETTINGS_MODULE=config.settings.e2e
export DATABASE_URL="${E2E_DATABASE_URL:-postgres://perreview:perreview@localhost:5433/perreview_e2e}"
PORT="${E2E_BACKEND_PORT:-8001}"
PYTHON="$ROOT/backend/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "[e2e] backend/.venv가 없습니다. README의 백엔드 설치 절차를 먼저 진행하세요." >&2
  exit 1
fi

"$PYTHON" "$ROOT/tests/scripts/ensure_db.py"
"$PYTHON" manage.py migrate --no-input -v 0
"$PYTHON" manage.py flush --no-input -v 0
echo "[e2e] 데이터 초기화 완료 (기본 관리자 재생성)"

exec "$PYTHON" manage.py runserver "127.0.0.1:${PORT}" --noreload
