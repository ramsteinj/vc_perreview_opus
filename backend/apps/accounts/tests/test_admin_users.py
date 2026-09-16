"""사용자 관리 API 테스트 (specs/05-admin-features.md FR-A-02)."""

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from apps.accounts.models import Department, Role, User

pytestmark = pytest.mark.django_db

URL = '/api/admin/users/'
LOGIN_URL = '/api/auth/login/'


def login(client, name, employee_no, password):
    res = client.post(
        LOGIN_URL, {'name': name, 'employee_no': employee_no, 'password': password}, format='json'
    )
    if res.status_code == 200:
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {res.data["access"]}')
    return res


@pytest.fixture
def admin_client():
    client = APIClient()
    login(
        client,
        settings.DEFAULT_ADMIN_NAME,
        settings.DEFAULT_ADMIN_EMPLOYEE_NO,
        settings.DEFAULT_ADMIN_PASSWORD,
    )
    return client


@pytest.fixture
def employee_client(employee):
    client = APIClient()
    login(client, '홍길동', '20230101', 'employeePass1!')
    return client


@pytest.fixture
def department(db):
    return Department.objects.create(code='DEV1', name='개발1팀')


# ── 권한 ─────────────────────────────────────────────────────


def test_직원은_사용자_API에_접근할_수_없다(employee_client):
    assert employee_client.get(URL).status_code == 403


def test_직원은_사용자를_생성할_수_없다(employee_client):
    res = employee_client.post(URL, {'employee_no': '20260001', 'name': '무단생성'}, format='json')
    assert res.status_code == 403
    assert not User.objects.filter(employee_no='20260001').exists()


# ── 생성 ─────────────────────────────────────────────────────


def test_사용자를_생성한다(admin_client, department):
    res = admin_client.post(
        URL,
        {
            'employee_no': '20260101',
            'name': '홍길동',
            'department': department.id,
            'position': '선임',
            'role': Role.EMPLOYEE,
            'hired_on': '2026-01-01',
            'password': 'initialPass1!',
        },
        format='json',
    )

    assert res.status_code == 201
    user = User.objects.get(employee_no='20260101')
    assert user.name == '홍길동'
    assert user.department == department
    assert user.check_password('initialPass1!')


def test_중복_사번으로_생성하면_400이다(admin_client, employee):
    res = admin_client.post(URL, {'employee_no': '20230101', 'name': '다른사람'}, format='json')

    assert res.status_code == 400
    assert 'employee_no' in res.data.get('fields', {})


def test_비밀번호를_생략하면_임시_비밀번호가_발급된다(admin_client):
    res = admin_client.post(URL, {'employee_no': '20260102', 'name': '임시비번'}, format='json')

    assert res.status_code == 201
    generated = res.data['generated_password']
    assert generated

    user = User.objects.get(employee_no='20260102')
    assert user.check_password(generated)


def test_발급된_임시_비밀번호로_로그인된다(admin_client):
    """완료 조건: 생성한 직원 계정으로 로그인된다."""
    res = admin_client.post(URL, {'employee_no': '20260103', 'name': '신입'}, format='json')
    password = res.data['generated_password']

    login_res = login(APIClient(), '신입', '20260103', password)

    assert login_res.status_code == 200
    assert login_res.data['user']['employee_no'] == '20260103'


def test_지정한_비밀번호로_로그인된다(admin_client):
    admin_client.post(
        URL,
        {'employee_no': '20260104', 'name': '지정비번', 'password': 'chosenPass12!'},
        format='json',
    )

    res = login(APIClient(), '지정비번', '20260104', 'chosenPass12!')

    assert res.status_code == 200


def test_약한_비밀번호는_거부된다(admin_client):
    res = admin_client.post(
        URL, {'employee_no': '20260105', 'name': '약한비번', 'password': '1234'}, format='json'
    )

    assert res.status_code == 400
    assert not User.objects.filter(employee_no='20260105').exists()


def test_목록_응답에는_비밀번호가_포함되지_않는다(admin_client):
    admin_client.post(URL, {'employee_no': '20260106', 'name': '아무개'}, format='json')

    res = admin_client.get(URL)

    for row in res.data['results']:
        assert 'password' not in row
        assert 'generated_password' not in row


# ── 수정 ─────────────────────────────────────────────────────


def test_사용자_정보를_수정한다(admin_client, employee, department):
    res = admin_client.patch(
        f'{URL}{employee.id}/',
        {'position': '책임', 'department': department.id},
        format='json',
    )

    assert res.status_code == 200
    employee.refresh_from_db()
    assert employee.position == '책임'
    assert employee.department == department


def test_본인의_관리자_권한은_스스로_낮출_수_없다(admin_client):
    admin = User.objects.get(employee_no='ADMIN')

    res = admin_client.patch(f'{URL}{admin.id}/', {'role': Role.EMPLOYEE}, format='json')

    assert res.status_code == 409
    assert res.data['code'] == 'SELF_ROLE_DOWNGRADE'
    admin.refresh_from_db()
    assert admin.role == Role.ADMIN


def test_다른_관리자가_있으면_권한_강등이_가능하다(admin_client):
    other = User.objects.create_user(
        employee_no='90000001', name='다른관리자', password='otherAdmin1!', role=Role.ADMIN
    )

    res = admin_client.patch(f'{URL}{other.id}/', {'role': Role.EMPLOYEE}, format='json')

    assert res.status_code == 200
    other.refresh_from_db()
    assert other.role == Role.EMPLOYEE


def test_마지막_관리자는_비활성화할_수_없다(admin_client):
    admin = User.objects.get(employee_no='ADMIN')

    res = admin_client.patch(f'{URL}{admin.id}/', {'is_active': False}, format='json')

    assert res.status_code == 409
    assert res.data['code'] == 'LAST_ADMIN'
    admin.refresh_from_db()
    assert admin.is_active is True


def test_수정_시_중복_사번은_거부된다(admin_client, employee):
    res = admin_client.patch(f'{URL}{employee.id}/', {'employee_no': 'ADMIN'}, format='json')

    assert res.status_code == 400


def test_자기_사번_유지는_허용된다(admin_client, employee):
    res = admin_client.patch(
        f'{URL}{employee.id}/', {'employee_no': '20230101', 'position': '선임'}, format='json'
    )

    assert res.status_code == 200


# ── 삭제 / 비활성화 ──────────────────────────────────────────


def test_삭제는_기본적으로_비활성화다(admin_client, employee):
    res = admin_client.delete(f'{URL}{employee.id}/')

    assert res.status_code == 200
    employee.refresh_from_db()
    assert employee.is_active is False
    assert User.objects.filter(pk=employee.pk).exists()


def test_비활성화된_사용자는_로그인할_수_없다(admin_client, employee):
    """수용 기준: 비활성 사용자는 로그인할 수 없다."""
    admin_client.delete(f'{URL}{employee.id}/')

    res = login(APIClient(), '홍길동', '20230101', 'employeePass1!')

    assert res.status_code == 401


def test_마지막_관리자는_삭제할_수_없다(admin_client):
    admin = User.objects.get(employee_no='ADMIN')

    res = admin_client.delete(f'{URL}{admin.id}/')

    assert res.status_code == 409
    assert res.data['code'] == 'LAST_ADMIN'
    admin.refresh_from_db()
    assert admin.is_active is True


def test_이력이_없으면_물리삭제된다(admin_client, employee):
    pk = employee.pk

    res = admin_client.delete(f'{URL}{pk}/?hard=true')

    assert res.status_code == 204
    assert not User.objects.filter(pk=pk).exists()


def test_비활성화된_사용자를_다시_활성화한다(admin_client, employee):
    admin_client.delete(f'{URL}{employee.id}/')

    res = admin_client.post(f'{URL}{employee.id}/activate/')

    assert res.status_code == 200
    employee.refresh_from_db()
    assert employee.is_active is True


# ── 비밀번호 초기화 ──────────────────────────────────────────


def test_비밀번호를_초기화하면_임시_비밀번호가_발급된다(admin_client, employee):
    res = admin_client.post(f'{URL}{employee.id}/reset-password/')

    assert res.status_code == 200
    password = res.data['generated_password']

    employee.refresh_from_db()
    assert employee.check_password(password)
    assert not employee.check_password('employeePass1!')


def test_초기화_비밀번호를_직접_지정할_수_있다(admin_client, employee):
    res = admin_client.post(
        f'{URL}{employee.id}/reset-password/', {'password': 'resetPass123!'}, format='json'
    )

    assert res.status_code == 200
    assert 'generated_password' not in res.data
    employee.refresh_from_db()
    assert employee.check_password('resetPass123!')


def test_초기화_비밀번호도_검증을_통과해야_한다(admin_client, employee):
    res = admin_client.post(
        f'{URL}{employee.id}/reset-password/', {'password': 'abc'}, format='json'
    )

    assert res.status_code == 400
    employee.refresh_from_db()
    assert employee.check_password('employeePass1!')


def test_초기화된_비밀번호로_로그인된다(admin_client, employee):
    res = admin_client.post(f'{URL}{employee.id}/reset-password/')
    password = res.data['generated_password']

    assert login(APIClient(), '홍길동', '20230101', password).status_code == 200


# ── 검색 / 필터 / 정렬 ───────────────────────────────────────


def test_성명으로_검색된다(admin_client, employee):
    res = admin_client.get(URL, {'search': '홍길'})

    assert res.data['count'] == 1
    assert res.data['results'][0]['employee_no'] == '20230101'


def test_사번으로_검색된다(admin_client, employee):
    res = admin_client.get(URL, {'search': '20230'})

    assert res.data['count'] == 1


def test_부서로_필터된다(admin_client, department):
    User.objects.create_user(
        employee_no='20230401', name='소속있음', password='pass123456!', department=department
    )
    User.objects.create_user(employee_no='20230402', name='소속없음', password='pass123456!')

    res = admin_client.get(URL, {'department': department.id})

    assert res.data['count'] == 1
    assert res.data['results'][0]['employee_no'] == '20230401'


def test_권한으로_필터된다(admin_client, employee):
    res = admin_client.get(URL, {'role': Role.ADMIN})

    assert res.data['count'] == 1
    assert res.data['results'][0]['employee_no'] == 'ADMIN'


def test_재직_상태로_필터된다(admin_client, employee):
    employee.is_active = False
    employee.save()

    res = admin_client.get(URL, {'is_active': 'false'})

    assert res.data['count'] == 1
    assert res.data['results'][0]['employee_no'] == '20230101'


def test_사번으로_정렬된다(admin_client):
    User.objects.create_user(employee_no='20230999', name='나중', password='pass123456!')
    User.objects.create_user(employee_no='20230001', name='먼저', password='pass123456!')

    res = admin_client.get(URL, {'ordering': 'employee_no'})

    numbers = [r['employee_no'] for r in res.data['results']]
    assert numbers == sorted(numbers)


def test_목록에_부서명이_포함된다(admin_client, department):
    User.objects.create_user(
        employee_no='20230501', name='소속자', password='pass123456!', department=department
    )

    res = admin_client.get(URL, {'search': '소속자'})

    assert res.data['results'][0]['department_name'] == '개발1팀'


def test_options는_활성_사용자만_반환한다(admin_client, employee):
    inactive = User.objects.create_user(
        employee_no='20230601', name='퇴사자', password='pass123456!'
    )
    inactive.is_active = False
    inactive.save()

    res = admin_client.get(f'{URL}options/')

    numbers = [u['employee_no'] for u in res.data]
    assert '20230101' in numbers
    assert '20230601' not in numbers


def test_역할_선택지를_조회한다(admin_client):
    res = admin_client.get('/api/admin/roles/')

    values = {r['value'] for r in res.data}
    assert values == {'EMPLOYEE', 'ADMIN'}


def test_다른_관리자가_마지막_관리자를_강등해도_차단된다(admin_client):
    """관리자 A가 B를 강등해 관리자가 0명이 되는 경로도 막아야 한다."""
    other = User.objects.create_user(
        employee_no='90000002', name='임시관리자', password='tempAdmin12!', role=Role.ADMIN
    )
    # ADMIN 계정을 강등해 other만 남긴다
    admin = User.objects.get(employee_no='ADMIN')

    other_client = APIClient()
    login(other_client, '임시관리자', '90000002', 'tempAdmin12!')
    assert (
        other_client.patch(f'{URL}{admin.id}/', {'role': Role.EMPLOYEE}, format='json').status_code
        == 200
    )

    # 이제 other가 마지막 관리자 -> 스스로도, 남도 강등할 수 없다
    res = other_client.patch(f'{URL}{other.id}/', {'role': Role.EMPLOYEE}, format='json')
    assert res.status_code == 409


# ── 진행 중 회차 평가자 배정 경고 (FR-A-02) ────────────────────


def test_진행중_회차_평가자를_비활성화하면_경고한다(admin_client, department):
    from apps.evaluations.models import (
        EvaluationCycle,
        EvaluationItem,
        EvaluatorAssignment,
        TargetType,
    )

    evaluator = User.objects.create_user(
        employee_no='20180001', name='박팀장', password='managerPass1!', department=department
    )
    target = User.objects.create_user(
        employee_no='20230001', name='김철수', password='memberPass1!', department=department
    )
    cycle = EvaluationCycle.objects.create(
        name='2026 상반기', year=2026, starts_on='2026-09-01', ends_on='2026-09-30'
    )
    EvaluationItem.objects.create(
        cycle=cycle, target_type=TargetType.EMPLOYEE, code='A', title='A', weight=100
    )
    EvaluatorAssignment.objects.create(
        cycle=cycle,
        target_type=TargetType.EMPLOYEE,
        target_user=target,
        primary_evaluator=evaluator,
    )
    admin_client.post(f'/api/admin/cycles/{cycle.id}/open/?confirm=true')

    res = admin_client.delete(f'{URL}{evaluator.id}/')

    assert res.status_code == 409
    assert res.data['code'] == 'EVALUATOR_IN_OPEN_CYCLE'
    assert len(res.data['assignments']) == 1
    assert res.data['assignments'][0]['round'] == 'PRIMARY'

    evaluator.refresh_from_db()
    assert evaluator.is_active is True


def test_force면_경고를_무시하고_비활성화한다(admin_client, department):
    from apps.evaluations.models import (
        EvaluationCycle,
        EvaluationItem,
        EvaluatorAssignment,
        TargetType,
    )

    evaluator = User.objects.create_user(
        employee_no='20180002', name='이팀장', password='managerPass1!', department=department
    )
    target = User.objects.create_user(
        employee_no='20230002', name='박영희', password='memberPass1!', department=department
    )
    cycle = EvaluationCycle.objects.create(
        name='2026 상반기', year=2026, starts_on='2026-09-01', ends_on='2026-09-30'
    )
    EvaluationItem.objects.create(
        cycle=cycle, target_type=TargetType.EMPLOYEE, code='A', title='A', weight=100
    )
    EvaluatorAssignment.objects.create(
        cycle=cycle,
        target_type=TargetType.EMPLOYEE,
        target_user=target,
        primary_evaluator=evaluator,
    )
    admin_client.post(f'/api/admin/cycles/{cycle.id}/open/?confirm=true')

    res = admin_client.delete(f'{URL}{evaluator.id}/?force=true')

    assert res.status_code == 200
    evaluator.refresh_from_db()
    assert evaluator.is_active is False


def test_DRAFT_회차_배정은_경고하지_않는다(admin_client, department):
    from apps.evaluations.models import EvaluationCycle, EvaluatorAssignment, TargetType

    evaluator = User.objects.create_user(
        employee_no='20180003', name='정팀장', password='managerPass1!', department=department
    )
    target = User.objects.create_user(
        employee_no='20230003', name='최민수', password='memberPass1!', department=department
    )
    cycle = EvaluationCycle.objects.create(
        name='준비중 회차', year=2026, starts_on='2026-09-01', ends_on='2026-09-30'
    )
    EvaluatorAssignment.objects.create(
        cycle=cycle,
        target_type=TargetType.EMPLOYEE,
        target_user=target,
        primary_evaluator=evaluator,
    )

    res = admin_client.delete(f'{URL}{evaluator.id}/')

    assert res.status_code == 200
