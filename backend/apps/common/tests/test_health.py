"""공통 엔드포인트 테스트."""

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_헬스체크는_인증_없이_접근된다():
    res = APIClient().get('/api/health/')

    assert res.status_code == 200
    assert res.data['status'] == 'ok'
    assert res.data['db'] == 'ok'
