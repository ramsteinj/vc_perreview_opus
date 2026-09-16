"""로그인/인증 테스트 (specs/03-auth.md, FR-E-01)."""

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from apps.accounts.models import User

pytestmark = pytest.mark.django_db

LOGIN_URL = '/api/auth/login/'
ME_URL = '/api/auth/me/'
REFRESH_URL = '/api/auth/refresh/'
LOGOUT_URL = '/api/auth/logout/'
CHANGE_PASSWORD_URL = '/api/auth/change-password/'


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def admin_credentials():
    return {
        'name': settings.DEFAULT_ADMIN_NAME,
        'employee_no': settings.DEFAULT_ADMIN_EMPLOYEE_NO,
        'password': settings.DEFAULT_ADMIN_PASSWORD,
    }


# ── 로그인 성공 ──────────────────────────────────────────────


def test_기본_관리자_계정으로_로그인된다(client, admin_credentials):
    res = client.post(LOGIN_URL, admin_credentials, format='json')

    assert res.status_code == 200
    assert 'access' in res.data
    assert 'refresh' in res.data
    assert res.data['user']['employee_no'] == 'ADMIN'
    assert res.data['user']['role'] == 'ADMIN'


def test_기본_비밀번호를_쓰면_password_is_default가_참이다(client, admin_credentials):
    res = client.post(LOGIN_URL, admin_credentials, format='json')
    assert res.data['user']['password_is_default'] is True


def test_토큰에_커스텀_클레임이_담긴다(client, admin_credentials):
    from rest_framework_simplejwt.tokens import AccessToken

    res = client.post(LOGIN_URL, admin_credentials, format='json')
    token = AccessToken(res.data['access'])

    assert token['employee_no'] == 'ADMIN'
    assert token['name'] == 'ADMIN'
    assert token['role'] == 'ADMIN'


def test_성명_앞뒤_공백은_무시된다(client, admin_credentials):
    res = client.post(LOGIN_URL, {**admin_credentials, 'name': '  ADMIN  '}, format='json')
    assert res.status_code == 200


# ── 로그인 실패 ──────────────────────────────────────────────


def test_성명이_다르면_로그인에_실패한다(client, admin_credentials):
    """사번과 비밀번호가 맞아도 성명이 다르면 거부된다."""
    res = client.post(LOGIN_URL, {**admin_credentials, 'name': '홍길동'}, format='json')

    assert res.status_code == 401
    assert res.data['code'] == 'INVALID_CREDENTIALS'


def test_비밀번호가_틀리면_실패한다(client, admin_credentials):
    res = client.post(LOGIN_URL, {**admin_credentials, 'password': 'wrongpass'}, format='json')
    assert res.status_code == 401


def test_없는_사번이면_실패한다(client, admin_credentials):
    res = client.post(LOGIN_URL, {**admin_credentials, 'employee_no': 'NOPE'}, format='json')
    assert res.status_code == 401


def test_실패_응답은_사유를_구분하지_않는다(client, admin_credentials):
    """사용자 열거를 막기 위해 세 가지 실패가 같은 응답을 반환해야 한다."""
    wrong_name = client.post(LOGIN_URL, {**admin_credentials, 'name': '아무개'}, format='json')
    wrong_pw = client.post(
        LOGIN_URL, {**admin_credentials, 'password': 'nope123456'}, format='json'
    )
    no_user = client.post(LOGIN_URL, {**admin_credentials, 'employee_no': 'ZZZZ'}, format='json')

    assert wrong_name.data == wrong_pw.data == no_user.data


def test_비활성_계정은_로그인할_수_없다(client, employee):
    employee.is_active = False
    employee.save()

    res = client.post(
        LOGIN_URL,
        {'name': '홍길동', 'employee_no': '20230101', 'password': 'employeePass1!'},
        format='json',
    )
    assert res.status_code == 401


# ── 시도 제한 ────────────────────────────────────────────────


def test_반복_실패하면_차단된다(client, admin_credentials):
    bad = {**admin_credentials, 'password': 'wrongpass'}

    for _ in range(settings.LOGIN_ATTEMPT_LIMIT - 1):
        assert client.post(LOGIN_URL, bad, format='json').status_code == 401

    res = client.post(LOGIN_URL, bad, format='json')
    assert res.status_code == 429
    assert res.data['code'] == 'TOO_MANY_ATTEMPTS'


def test_차단된_뒤에는_올바른_비밀번호도_거부된다(client, admin_credentials):
    bad = {**admin_credentials, 'password': 'wrongpass'}
    for _ in range(settings.LOGIN_ATTEMPT_LIMIT):
        client.post(LOGIN_URL, bad, format='json')

    res = client.post(LOGIN_URL, admin_credentials, format='json')
    assert res.status_code == 429


def test_시도_제한은_사번_단위로_적용된다(client, admin_credentials, employee):
    bad = {'name': 'X', 'employee_no': 'OTHER', 'password': 'bad'}
    for _ in range(settings.LOGIN_ATTEMPT_LIMIT + 1):
        client.post(LOGIN_URL, bad, format='json')

    res = client.post(LOGIN_URL, admin_credentials, format='json')
    assert res.status_code == 200


def test_로그인_성공하면_카운터가_초기화된다(client, admin_credentials):
    bad = {**admin_credentials, 'password': 'wrongpass'}
    for _ in range(settings.LOGIN_ATTEMPT_LIMIT - 1):
        client.post(LOGIN_URL, bad, format='json')

    assert client.post(LOGIN_URL, admin_credentials, format='json').status_code == 200

    # 카운터가 초기화되었으므로 다시 한도만큼 실패할 수 있어야 한다
    for _ in range(settings.LOGIN_ATTEMPT_LIMIT - 1):
        assert client.post(LOGIN_URL, bad, format='json').status_code == 401


# ── /me/, refresh, logout ────────────────────────────────────


def test_me는_인증이_필요하다(client):
    assert client.get(ME_URL).status_code == 401


def test_me가_내_프로필을_반환한다(client, admin_credentials):
    login = client.post(LOGIN_URL, admin_credentials, format='json')
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {login.data["access"]}')

    res = client.get(ME_URL)

    assert res.status_code == 200
    assert res.data['employee_no'] == 'ADMIN'


def test_refresh로_새_access_토큰을_받는다(client, admin_credentials):
    login = client.post(LOGIN_URL, admin_credentials, format='json')

    res = client.post(REFRESH_URL, {'refresh': login.data['refresh']}, format='json')

    assert res.status_code == 200
    assert 'access' in res.data


def test_잘못된_refresh_토큰은_401이다(client):
    res = client.post(REFRESH_URL, {'refresh': 'garbage'}, format='json')
    assert res.status_code == 401
    assert res.data['code'] == 'TOKEN_INVALID'


def test_로그아웃하면_refresh_토큰이_무효화된다(client, admin_credentials):
    login = client.post(LOGIN_URL, admin_credentials, format='json')
    refresh = login.data['refresh']
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {login.data["access"]}')

    assert client.post(LOGOUT_URL, {'refresh': refresh}, format='json').status_code == 204
    assert client.post(REFRESH_URL, {'refresh': refresh}, format='json').status_code == 401


# ── 비밀번호 변경 ────────────────────────────────────────────


def test_비밀번호를_변경할_수_있다(client, admin_credentials):
    login = client.post(LOGIN_URL, admin_credentials, format='json')
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {login.data["access"]}')

    res = client.post(
        CHANGE_PASSWORD_URL,
        {'current_password': admin_credentials['password'], 'new_password': 'brandNewPass9!'},
        format='json',
    )

    assert res.status_code == 200
    admin = User.objects.get(employee_no='ADMIN')
    assert admin.check_password('brandNewPass9!')


def test_현재_비밀번호가_틀리면_변경되지_않는다(client, admin_credentials):
    login = client.post(LOGIN_URL, admin_credentials, format='json')
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {login.data["access"]}')

    res = client.post(
        CHANGE_PASSWORD_URL,
        {'current_password': 'nope123456', 'new_password': 'brandNewPass9!'},
        format='json',
    )
    assert res.status_code == 400


def test_짧은_비밀번호는_거부된다(client, admin_credentials):
    login = client.post(LOGIN_URL, admin_credentials, format='json')
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {login.data["access"]}')

    res = client.post(
        CHANGE_PASSWORD_URL,
        {'current_password': admin_credentials['password'], 'new_password': 'short1!'},
        format='json',
    )
    assert res.status_code == 400
