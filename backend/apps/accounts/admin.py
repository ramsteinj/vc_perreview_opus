from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Department, User


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'parent', 'is_active']
    list_filter = ['is_active']
    search_fields = ['code', 'name']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ['employee_no']
    list_display = ['employee_no', 'name', 'department', 'position', 'role', 'is_active']
    list_filter = ['role', 'is_active', 'department']
    search_fields = ['employee_no', 'name']

    fieldsets = (
        (None, {'fields': ('employee_no', 'password')}),
        ('개인정보', {'fields': ('name', 'department', 'position', 'hired_on', 'email')}),
        (
            '권한',
            {
                'fields': (
                    'role',
                    'is_active',
                    'is_staff',
                    'is_superuser',
                    'groups',
                    'user_permissions',
                )
            },
        ),
        ('기록', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': ('employee_no', 'name', 'password1', 'password2', 'role'),
            },
        ),
    )
