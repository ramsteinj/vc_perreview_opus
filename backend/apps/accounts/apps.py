from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    verbose_name = '사용자'

    def ready(self):
        from django.db.models.signals import post_migrate

        from .bootstrap import create_default_admin

        post_migrate.connect(create_default_admin, sender=self)
