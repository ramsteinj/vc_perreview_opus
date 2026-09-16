"""사용자 CSV 일괄 등록 테스트 (specs/05-admin-features.md FR-A-02)."""

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.accounts.models import Department, Role, User

pytestmark = pytest.mark.django_db

URL = '/api/admin/users/bulk-import/'
HEADER = 'employee_no,name,department_code,position,role,hired_on'


def login(client, name, employee_no, password):
    res = client.post(
        '/api/auth/login/',
        {'name': name, 'employee_no': employee_no, 'password': password},
        format='json',
    )
    if res.status_code == 200:
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {res.data["access"]}')
    return res


@pytest.fixture
def admin_client(db):
    client = APIClient()
    login(
        client,
        settings.DEFAULT_ADMIN_NAME,
        settings.DEFAULT_ADMIN_EMPLOYEE_NO,
        settings.DEFAULT_ADMIN_PASSWORD,
    )
    return client


@pytest.fixture
def departments(db):
    return {
        'DEV1': Department.objects.create(code='DEV1', name='개발1팀'),
        'HR': Department.objects.create(code='HR', name='인사팀'),
        'OLD': Department.objects.create(code='OLD', name='폐지팀', is_active=False),
    }


def upload(client, text, *, name='users.csv', encoding='utf-8-sig'):
    payload = text.encode(encoding) if isinstance(text, str) else text
    file = SimpleUploadedFile(name, payload, content_type='text/csv')
    return client.post(URL, {'file': file}, format='multipart')


def csv_text(*rows):
    return '\r\n'.join([HEADER, *rows]) + '\r\n'


# ── 권한 ─────────────────────────────────────────────────────


def test_직원은_일괄_등록할_수_없다(db, employee):
    client = APIClient()
    login(client, '홍길동', '20230101', 'employeePass1!')

    res = upload(client, csv_text('20260001,신입,,,,'))

    assert res.status_code == 403
    assert not User.objects.filter(employee_no='20260001').exists()


def test_비인증이면_401이다(db):
    assert upload(APIClient(), csv_text('20260001,신입,,,,')).status_code == 401


# ── 정상 등록 ────────────────────────────────────────────────


def test_여러_사용자를_한번에_등록한다(admin_client, departments):
    res = upload(
        admin_client,
        csv_text(
            '20260001,김철수,DEV1,선임,EMPLOYEE,2026-01-01',
            '20260002,이영희,HR,책임,EMPLOYEE,2026-02-01',
            '20260003,박관리,DEV1,팀장,ADMIN,2020-03-01',
        ),
    )

    assert res.status_code == 201
    assert res.data['created_count'] == 3
    assert res.data['total_rows'] == 3

    user = User.objects.get(employee_no='20260001')
    assert user.name == '김철수'
    assert user.department == departments['DEV1']
    assert user.position == '선임'
    assert user.role == Role.EMPLOYEE
    assert str(user.hired_on) == '2026-01-01'


def test_ADMIN_역할은_is_staff가_켜진다(admin_client, departments):
    upload(admin_client, csv_text('20260003,박관리,DEV1,팀장,ADMIN,2020-03-01'))

    admin = User.objects.get(employee_no='20260003')
    assert admin.role == Role.ADMIN
    assert admin.is_staff is True


def test_임시_비밀번호가_1회_반환된다(admin_client, departments):
    res = upload(admin_client, csv_text('20260001,김철수,DEV1,,,'))

    row = res.data['created'][0]
    assert row['generated_password']
    assert User.objects.get(employee_no='20260001').check_password(row['generated_password'])


def test_발급된_비밀번호로_로그인된다(admin_client, departments):
    res = upload(admin_client, csv_text('20260001,김철수,DEV1,,,'))
    password = res.data['created'][0]['generated_password']

    assert login(APIClient(), '김철수', '20260001', password).status_code == 200


def test_선택_컬럼은_비워도_된다(admin_client):
    res = upload(admin_client, csv_text('20260001,김철수,,,,'))

    assert res.status_code == 201
    user = User.objects.get(employee_no='20260001')
    assert user.department is None
    assert user.position == ''
    assert user.role == Role.EMPLOYEE
    assert user.hired_on is None


def test_필수_컬럼만_있는_헤더도_허용된다(admin_client):
    res = upload(admin_client, 'employee_no,name\r\n20260001,김철수\r\n')

    assert res.status_code == 201
    assert User.objects.filter(employee_no='20260001').exists()


def test_빈_줄은_건너뛴다(admin_client):
    res = upload(
        admin_client,
        f'{HEADER}\r\n20260001,김철수,,,,\r\n,,,,,\r\n20260002,이영희,,,,\r\n',
    )

    assert res.data['created_count'] == 2


# ── 인코딩 ───────────────────────────────────────────────────


@pytest.mark.parametrize('encoding', ['utf-8-sig', 'utf-8', 'cp949'])
def test_여러_인코딩을_받아들인다(admin_client, encoding):
    """한국어 Excel은 CP949로 저장하는 경우가 흔하다."""
    res = upload(admin_client, csv_text('20260001,김철수,,,,'), encoding=encoding)

    assert res.status_code == 201
    assert User.objects.get(employee_no='20260001').name == '김철수'


def test_인식할_수_없는_인코딩은_400이다(admin_client):
    res = upload(admin_client, b'\xff\xfe\x00\x01\x02\x03')

    assert res.status_code == 400
    assert res.data['code'] == 'IMPORT_ENCODING_ERROR'


# ── 검증 실패와 롤백 ─────────────────────────────────────────


def test_한_행이라도_오류면_전체를_롤백한다(admin_client, departments):
    """스펙: 검증 실패 행은 사유와 함께 리포트하고, 전체를 롤백한다."""
    res = upload(
        admin_client,
        csv_text(
            '20260001,김철수,DEV1,,,',
            '20260002,,HR,,,',  # 성명 누락
            '20260003,박영수,DEV1,,,',
        ),
    )

    assert res.status_code == 400
    assert res.data['code'] == 'IMPORT_VALIDATION_FAILED'
    assert res.data['error_count'] == 1
    assert res.data['total_rows'] == 3

    # 정상이던 행도 저장되지 않아야 한다
    assert not User.objects.filter(employee_no__startswith='202600').exists()


def test_오류에_행번호와_사유가_담긴다(admin_client):
    res = upload(admin_client, csv_text('20260001,김철수,,,,', ',이영희,,,,'))

    error = res.data['errors'][0]
    assert error['line'] == 3  # 헤더 1행 + 데이터 2번째
    assert error['field'] == 'employee_no'
    assert '필수' in error['message']


def test_기존_사번과_중복되면_거부된다(admin_client, employee):
    res = upload(admin_client, csv_text('20230101,다른사람,,,,'))

    assert res.status_code == 400
    assert res.data['errors'][0]['field'] == 'employee_no'
    assert '이미 사용 중' in res.data['errors'][0]['message']


def test_파일_안에서_사번이_중복되면_거부된다(admin_client):
    res = upload(admin_client, csv_text('20260001,김철수,,,,', '20260001,이영희,,,,'))

    assert res.status_code == 400
    messages = [e['message'] for e in res.data['errors']]
    assert any('파일 안에서 중복' in m for m in messages)


def test_없는_부서코드는_거부된다(admin_client, departments):
    res = upload(admin_client, csv_text('20260001,김철수,NOPE,,,'))

    assert res.status_code == 400
    assert res.data['errors'][0]['field'] == 'department_code'
    assert 'NOPE' in res.data['errors'][0]['message']


def test_비활성_부서는_거부된다(admin_client, departments):
    res = upload(admin_client, csv_text('20260001,김철수,OLD,,,'))

    assert res.status_code == 400
    assert '비활성 부서' in res.data['errors'][0]['message']


def test_잘못된_권한값은_거부된다(admin_client):
    res = upload(admin_client, csv_text('20260001,김철수,,,SUPERUSER,'))

    assert res.status_code == 400
    assert res.data['errors'][0]['field'] == 'role'


def test_잘못된_날짜_형식은_거부된다(admin_client):
    res = upload(admin_client, csv_text('20260001,김철수,,,,2026/01/01'))

    assert res.status_code == 400
    assert res.data['errors'][0]['field'] == 'hired_on'
    assert 'YYYY-MM-DD' in res.data['errors'][0]['message']


def test_여러_오류가_모두_리포트된다(admin_client):
    res = upload(
        admin_client,
        csv_text(
            ',이름없음사번없음,,,,',
            '20260002,,,,,',
            '20260003,박영수,NOPE,,BAD_ROLE,2026-13-01',
        ),
    )

    assert res.data['error_count'] >= 5
    lines = {e['line'] for e in res.data['errors']}
    assert lines == {2, 3, 4}


# ── 파일 형식 ────────────────────────────────────────────────


def test_필수_컬럼이_없으면_400이다(admin_client):
    res = upload(admin_client, 'name,position\r\n김철수,선임\r\n')

    assert res.status_code == 400
    assert res.data['code'] == 'IMPORT_MISSING_COLUMNS'
    assert 'employee_no' in res.data['required_columns']


def test_데이터_행이_없으면_400이다(admin_client):
    res = upload(admin_client, f'{HEADER}\r\n')

    assert res.status_code == 400
    assert res.data['code'] == 'IMPORT_NO_ROWS'


def test_빈_파일은_400이다(admin_client):
    file = SimpleUploadedFile('users.csv', b'', content_type='text/csv')
    res = admin_client.post(URL, {'file': file}, format='multipart')

    assert res.status_code == 400


def test_CSV가_아닌_확장자는_400이다(admin_client):
    file = SimpleUploadedFile('users.xlsx', b'binary', content_type='application/vnd.ms-excel')
    res = admin_client.post(URL, {'file': file}, format='multipart')

    assert res.status_code == 400


def test_파일_없이_요청하면_400이다(admin_client):
    res = admin_client.post(URL, {}, format='multipart')
    assert res.status_code == 400


def test_쉼표가_포함된_값도_따옴표로_처리된다(admin_client, departments):
    res = upload(
        admin_client,
        f'{HEADER}\r\n20260001,"김,철수",DEV1,"선임, 파트리드",EMPLOYEE,2026-01-01\r\n',
    )

    assert res.status_code == 201
    user = User.objects.get(employee_no='20260001')
    assert user.name == '김,철수'
    assert user.position == '선임, 파트리드'


def test_최대_건수를_초과하면_400이다(admin_client):
    from apps.accounts.csv_import import MAX_ROWS

    rows = [f'2026{i:05d},직원{i},,,,' for i in range(MAX_ROWS + 5)]
    res = upload(admin_client, csv_text(*rows))

    assert res.status_code == 400
    assert res.data['code'] == 'IMPORT_TOO_MANY_ROWS'


def test_대량_등록도_동작한다(admin_client):
    rows = [f'2026{i:05d},직원{i},,,,' for i in range(300)]

    res = upload(admin_client, csv_text(*rows))

    assert res.status_code == 201
    assert res.data['created_count'] == 300
    assert User.objects.filter(employee_no__startswith='2026').count() == 300


def test_등록_후_목록_API에_나타난다(admin_client, departments):
    upload(admin_client, csv_text('20260001,김철수,DEV1,선임,EMPLOYEE,2026-01-01'))

    res = admin_client.get('/api/admin/users/', {'search': '김철수'})

    assert res.data['count'] == 1
    assert res.data['results'][0]['department_name'] == '개발1팀'
