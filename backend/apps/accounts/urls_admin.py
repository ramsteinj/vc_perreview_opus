from rest_framework.routers import DefaultRouter

from .views_admin import AdminUserViewSet, DepartmentViewSet, RoleChoicesView

app_name = 'accounts_admin'

router = DefaultRouter()
router.register('departments', DepartmentViewSet, basename='department')
router.register('users', AdminUserViewSet, basename='admin-user')
router.register('roles', RoleChoicesView, basename='role')

urlpatterns = router.urls
