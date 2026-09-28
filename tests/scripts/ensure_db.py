"""E2E 전용 데이터베이스가 없으면 만든다.

backend/.venv의 파이썬으로 실행한다 (psycopg 사용).
DATABASE_URL이 가리키는 DB 이름으로, 같은 서버의 postgres DB에 접속해 생성한다.
"""

import os
import sys
from urllib.parse import urlparse

import psycopg
from psycopg import sql

url = urlparse(os.environ['DATABASE_URL'])
db_name = url.path.lstrip('/')

try:
    conn = psycopg.connect(
        host=url.hostname,
        port=url.port or 5432,
        user=url.username,
        password=url.password,
        dbname='postgres',
        autocommit=True,
        connect_timeout=5,
    )
except psycopg.OperationalError as exc:
    sys.exit(
        f'[e2e] PostgreSQL에 연결할 수 없습니다 ({url.hostname}:{url.port}).\n'
        f'      저장소 루트에서 `docker compose up -d`를 먼저 실행하세요.\n      원인: {exc}'
    )

with conn:
    exists = conn.execute('SELECT 1 FROM pg_database WHERE datname = %s', [db_name]).fetchone()
    if exists:
        print(f'[e2e] 데이터베이스 {db_name} 확인')
    else:
        conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(db_name)))
        print(f'[e2e] 데이터베이스 {db_name} 생성')
