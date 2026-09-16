from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimeStampedModel

from .managers import UserManager


class Role(models.TextChoices):
    EMPLOYEE = 'EMPLOYEE', '직원'
    ADMIN = 'ADMIN', '관리자'


class Department(TimeStampedModel):
    """부서. 자기참조 FK로 조직도 트리를 구성한다."""

    code = models.CharField('부서코드', max_length=20, unique=True)
    name = models.CharField('부서명', max_length=100)
    parent = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='children',
        verbose_name='상위부서',
    )
    is_active = models.BooleanField('활성여부', default=True)

    class Meta:
        verbose_name = '부서'
        verbose_name_plural = '부서'
        ordering = ['code']

    def __str__(self):
        return f'{self.name}({self.code})'

    def clean(self):
        """상위 부서 순환 참조를 금지한다."""
        if self.parent_id is None:
            return
        if self.pk and self.parent_id == self.pk:
            raise ValidationError({'parent': '자기 자신을 상위 부서로 지정할 수 없습니다.'})

        seen = {self.pk} if self.pk else set()
        node = self.parent
        while node is not None:
            if node.pk in seen:
                raise ValidationError({'parent': '상위 부서 관계가 순환합니다.'})
            seen.add(node.pk)
            node = node.parent


class User(AbstractUser):
    """직원·관리자를 함께 표현하는 사용자 모델.

    Django는 AUTH_USER_MODEL을 하나만 지원하므로 별도 테이블로 나누지 않고
    role 필드로 구분한다 (specs/02-data-model.md §3.2).
    로그인 식별자는 사번이며, 성명까지 함께 검증한다 (specs/03-auth.md §1).
    """

    # AbstractUser의 기본 식별/이름 필드는 사용하지 않는다
    username = None
    first_name = None
    last_name = None

    employee_no = models.CharField('사번', max_length=20, unique=True)
    name = models.CharField('성명', max_length=50)
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='members',
        verbose_name='소속부서',
    )
    position = models.CharField('직위', max_length=50, blank=True)
    role = models.CharField('권한', max_length=10, choices=Role.choices, default=Role.EMPLOYEE)
    hired_on = models.DateField('입사일', null=True, blank=True)

    USERNAME_FIELD = 'employee_no'
    REQUIRED_FIELDS = ['name']

    objects = UserManager()

    class Meta:
        verbose_name = '사용자'
        verbose_name_plural = '사용자'
        ordering = ['employee_no']
        indexes = [
            models.Index(fields=['role', 'is_active']),
            models.Index(fields=['department']),
        ]

    def __str__(self):
        return f'{self.name}({self.employee_no})'

    @property
    def is_admin(self):
        return self.role == Role.ADMIN

    def save(self, *args, **kwargs):
        # 관리자는 Django Admin에 접근할 수 있어야 한다
        if self.role == Role.ADMIN:
            self.is_staff = True
        super().save(*args, **kwargs)

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name
