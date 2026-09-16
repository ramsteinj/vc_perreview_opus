from django.urls import path
from rest_framework.routers import DefaultRouter

from .views_my import MyAssignmentsView, MyResponseViewSet

app_name = 'evaluations_my'

router = DefaultRouter()
router.register('responses', MyResponseViewSet, basename='my-response')

urlpatterns = [
    path('assignments/', MyAssignmentsView.as_view(), name='my-assignments'),
    *router.urls,
]
