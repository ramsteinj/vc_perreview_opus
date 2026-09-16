from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AdminResponseViewSet,
    CsvExportView,
    DepartmentScoreView,
    ScoreCalculateView,
    ScoreListView,
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
    path('cycles/<int:pk>/calculate/', ScoreCalculateView.as_view(), name='score-calculate'),
    path('cycles/<int:pk>/scores/', ScoreListView.as_view(), name='score-list'),
    path(
        'cycles/<int:pk>/department-scores/',
        DepartmentScoreView.as_view(),
        name='department-score-list',
    ),
    path(
        'cycles/<int:pk>/export/<str:kind>.csv',
        CsvExportView.as_view(),
        name='csv-export',
    ),
    *router.urls,
]
