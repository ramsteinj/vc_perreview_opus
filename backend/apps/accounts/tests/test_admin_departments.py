"""부서 관리 API 테스트 (specs/05-admin-features.md FR-A-03)."""

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from apps.accounts.models import Department, Role, User

pytestmark = pytest.mark.django_db

URL = '/api/admin/departments/'


@pytest.fixture
def admin_client():
    client = APIClient()
    res = client.post(
        '/api/auth/login/',
        {
            'name': settings.DEFAULT_ADMIN_NAME,
            'employee_no': settings.DEFAULT_ADMIN_EMPLOYEE_NO,
            'password': settings.DEFAULT_ADMIN_PASSWORD,
        },
        format='json',
    )
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {res.data["access"]}')
    return client


@pytest.fixture
def employee_client(employee):
    client = APIClient()
    res = client.post(
        '/api/auth/login/',
        {'name': '홍길동', 'employee_no': '20230101', 'password': 'employeePass1!'},
        format='json',
    )
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {res.data["access"]}')
    return client


# ── 권한 ─────────────────────────────────────────────────────


def test_직원은_부서_API에_접근할_수_없다(employee_client):
    assert employee_client.get(URL).status_code == 403


def test_비인증_요청은_401이다():
    assert APIClient().get(URL).status_code == 401


# ── 생성 / 조회 ──────────────────────────────────────────────


def test_부서를_생성한다(admin_client):
    res = admin_client.post(URL, {'code': 'DEV1', 'name': '개발1팀'}, format='json')

    assert res.status_code == 201
    assert res.data['code'] == 'DEV1'
    assert Department.objects.filter(code='DEV1').exists()


def test_부서코드가_중복되면_400이다(admin_client):
    Department.objects.create(code='DEV1', name='개발1팀')

    res = admin_client.post(URL, {'code': 'DEV1', 'name': '개발2팀'}, format='json')

    assert res.status_code == 400


def test_소속_인원수가_함께_반환된다(admin_client):
    dept = Department.objects.create(code='DEV1', name='개발1팀')
    User.objects.create_user(
        employee_no='20230301', name='김개발', password='pass123456!', department=dept
    )

    res = admin_client.get(URL)

    row = next(r for r in res.data['results'] if r['code'] == 'DEV1')
    assert row['member_count'] == 1


def test_트리_조회는_계층_구조를_반환한다(admin_client):
    hq = Department.objects.create(code='HQ', name='본사')
    div = Department.objects.create(code='DIV', name='개발본부', parent=hq)
    Department.objects.create(code='DEV1', name='개발1팀', parent=div)
    Department.objects.create(code='HR', name='인사팀', parent=hq)

    res = admin_client.get(URL, {'tree': 'true'})

    assert res.status_code == 200
    roots = res.data['results']
    assert len(roots) == 1
    assert roots[0]['code'] == 'HQ'

    codes = {c['code'] for c in roots[0]['children']}
    assert codes == {'DIV', 'HR'}

    dev_div = next(c for c in roots[0]['children'] if c['code'] == 'DIV')
    assert dev_div['children'][0]['code'] == 'DEV1'


# ── 순환 참조 ────────────────────────────────────────────────


def test_자기_자신을_상위부서로_지정하면_400이다(admin_client):
    dept = Department.objects.create(code='DEV1', name='개발1팀')

    res = admin_client.patch(f'{URL}{dept.id}/', {'parent': dept.id}, format='json')

    assert res.status_code == 400


def test_직계_자손을_상위부서로_지정하면_400이다(admin_client):
    parent = Department.objects.create(code='HQ', name='본사')
    child = Department.objects.create(code='DEV1', name='개발1팀', parent=parent)

    res = admin_client.patch(f'{URL}{parent.id}/', {'parent': child.id}, format='json')

    assert res.status_code == 400


def test_먼_자손을_상위부서로_지정하면_400이다(admin_client):
    a = Department.objects.create(code='A', name='A본부')
    b = Department.objects.create(code='B', name='B실', parent=a)
    c = Department.objects.create(code='C', name='C팀', parent=b)

    res = admin_client.patch(f'{URL}{a.id}/', {'parent': c.id}, format='json')

    assert res.status_code == 400


def test_정상적인_상위부서_변경은_허용된다(admin_client):
    a = Department.objects.create(code='A', name='A본부')
    b = Department.objects.create(code='B', name='B팀')

    res = admin_client.patch(f'{URL}{b.id}/', {'parent': a.id}, format='json')

    assert res.status_code == 200
    b.refresh_from_db()
    assert b.parent == a


# ── 삭제 ─────────────────────────────────────────────────────


def test_삭제는_기본적으로_비활성화다(admin_client):
    dept = Department.objects.create(code='DEV1', name='개발1팀')

    res = admin_client.delete(f'{URL}{dept.id}/')

    assert res.status_code == 200
    dept.refresh_from_db()
    assert dept.is_active is False


def test_소속_직원이_있으면_물리삭제가_거부된다(admin_client):
    dept = Department.objects.create(code='DEV1', name='개발1팀')
    User.objects.create_user(
        employee_no='20230301', name='김개발', password='pass123456!', department=dept
    )

    res = admin_client.delete(f'{URL}{dept.id}/?hard=true')

    assert res.status_code == 409
    assert res.data['code'] == 'DEPARTMENT_IN_USE'
    assert Department.objects.filter(pk=dept.pk).exists()


def test_하위_부서가_있으면_물리삭제가_거부된다(admin_client):
    parent = Department.objects.create(code='HQ', name='본사')
    Department.objects.create(code='DEV1', name='개발1팀', parent=parent)

    res = admin_client.delete(f'{URL}{parent.id}/?hard=true')

    assert res.status_code == 409


def test_비어있는_부서는_물리삭제된다(admin_client):
    dept = Department.objects.create(code='TEMP', name='임시부서')

    res = admin_client.delete(f'{URL}{dept.id}/?hard=true')

    assert res.status_code == 204
    assert not Department.objects.filter(pk=dept.pk).exists()


# ── 검색 / 필터 ──────────────────────────────────────────────


def test_부서명으로_검색된다(admin_client):
    Department.objects.create(code='DEV1', name='개발1팀')
    Department.objects.create(code='HR', name='인사팀')

    res = admin_client.get(URL, {'search': '개발'})

    assert res.data['count'] == 1
    assert res.data['results'][0]['code'] == 'DEV1'


def test_활성여부로_필터된다(admin_client):
    Department.objects.create(code='DEV1', name='개발1팀')
    Department.objects.create(code='OLD', name='폐지팀', is_active=False)

    res = admin_client.get(URL, {'is_active': 'true'})

    assert res.data['count'] == 1
    assert res.data['results'][0]['code'] == 'DEV1'


def test_관리자가_아닌_사용자는_생성할_수_없다(employee_client):
    res = employee_client.post(URL, {'code': 'X', 'name': 'X팀'}, format='json')
    assert res.status_code == 403
    assert not Department.objects.filter(code='X').exists()


def test_생성한_부서에_직원을_소속시킬_수_있다(admin_client):
    """완료 조건: 부서 트리를 만들고 직원을 소속시킬 수 있다."""
    created = admin_client.post(URL, {'code': 'DEV1', 'name': '개발1팀'}, format='json')
    dept_id = created.data['id']

    res = admin_client.post(
        '/api/admin/users/',
        {
            'employee_no': '20260501',
            'name': '신입사원',
            'department': dept_id,
            'role': Role.EMPLOYEE,
        },
        format='json',
    )

    assert res.status_code == 201
    assert res.data['department'] == dept_id
    assert User.objects.get(employee_no='20260501').department_id == dept_id
