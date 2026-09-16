import django_filters as filters

from .models import Department, User


class UserFilter(filters.FilterSet):
    department = filters.ModelChoiceFilter(queryset=Department.objects.all())
    role = filters.CharFilter(field_name='role', lookup_expr='iexact')
    is_active = filters.BooleanFilter()

    class Meta:
        model = User
        fields = ['department', 'role', 'is_active']


class DepartmentFilter(filters.FilterSet):
    parent = filters.ModelChoiceFilter(queryset=Department.objects.all())
    is_active = filters.BooleanFilter()

    class Meta:
        model = Department
        fields = ['parent', 'is_active']
