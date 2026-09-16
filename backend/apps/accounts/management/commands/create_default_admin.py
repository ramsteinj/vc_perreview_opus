from django.conf import settings
from django.core.management.base import BaseCommand

from apps.accounts.bootstrap import create_default_admin
from apps.accounts.models import Role, User


class Command(BaseCommand):
    help = '기본 관리자 계정이 없으면 생성한다.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='관리자가 이미 있어도 기본 사번 계정을 생성하거나 비밀번호를 초기화한다.',
        )

    def handle(self, *args, **options):
        employee_no = settings.DEFAULT_ADMIN_EMPLOYEE_NO

        if options['force']:
            user, created = User.objects.get_or_create(
                employee_no=employee_no,
                defaults={
                    'name': settings.DEFAULT_ADMIN_NAME,
                    'role': Role.ADMIN,
                    'is_staff': True,
                    'is_superuser': True,
                },
            )
            user.role = Role.ADMIN
            user.is_active = True
            user.is_staff = True
            user.is_superuser = True
            user.set_password(settings.DEFAULT_ADMIN_PASSWORD)
            user.save()
            action = '생성' if created else '초기화'
            self.stdout.write(
                self.style.SUCCESS(f'기본 관리자 계정을 {action}했습니다: {employee_no}')
            )
            return

        admin = create_default_admin()
        if admin is None:
            self.stdout.write('관리자 계정이 이미 존재하여 아무것도 하지 않았습니다.')
        else:
            self.stdout.write(self.style.SUCCESS(f'기본 관리자 계정을 생성했습니다: {employee_no}'))
