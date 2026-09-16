from django.contrib.auth.models import BaseUserManager


class UserManager(BaseUserManager):
    """사번(employee_no)을 식별자로 사용하는 사용자 매니저."""

    use_in_migrations = True

    def create_user(self, employee_no, name, password=None, **extra_fields):
        if not employee_no:
            raise ValueError('사번은 필수입니다.')
        if not name:
            raise ValueError('성명은 필수입니다.')

        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)

        user = self.model(employee_no=employee_no, name=name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, employee_no, name, password=None, **extra_fields):
        from .models import Role

        extra_fields.setdefault('role', Role.ADMIN)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('superuser는 is_staff=True여야 합니다.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('superuser는 is_superuser=True여야 합니다.')

        return self.create_user(employee_no, name, password, **extra_fields)
