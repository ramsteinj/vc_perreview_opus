from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AdminResponseViewSet,
    StatusDetailView,
    StatusPendingView,
    StatusSummaryView,
)

app_name = 'reports'

router = DefaultRouter()
router.register('responses', AdminResponseViewSet, basename='admin-response')

urlpatterns = [
    path('cycles/<int:pk>/status/summary/', StatusSummaryView.as_view(), name='status-summary'),
    path('cycles/<int:pk>/status/detail/', StatusDetailView.as_view(), name='status-detail'),
    path('cycles/<int:pk>/status/pending/', StatusPendingView.as_view(), name='status-pending'),
    *router.urls,
]
