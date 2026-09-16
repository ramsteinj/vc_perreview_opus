from rest_framework.routers import DefaultRouter

from .views import EvaluationCycleViewSet, EvaluationItemViewSet, EvaluatorAssignmentViewSet

app_name = 'evaluations_admin'

router = DefaultRouter()
router.register('cycles', EvaluationCycleViewSet, basename='cycle')
router.register('items', EvaluationItemViewSet, basename='item')
router.register('assignments', EvaluatorAssignmentViewSet, basename='assignment')

urlpatterns = router.urls
