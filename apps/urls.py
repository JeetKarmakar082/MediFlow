from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DashboardStatsView,
    DepartmentViewSet, DoctorViewSet, DoctorScheduleViewSet,
    PatientViewSet, MedicalRecordViewSet,
    TriageViewSet, TokenViewSet, EmergencyViewSet, NotificationViewSet,
)

router = DefaultRouter()
router.register(r'departments',   DepartmentViewSet,    basename='department')
router.register(r'doctors',       DoctorViewSet,        basename='doctor')
router.register(r'schedules',     DoctorScheduleViewSet,basename='schedule')
router.register(r'patients',      PatientViewSet,       basename='patient')
router.register(r'records',       MedicalRecordViewSet, basename='record')
router.register(r'triage',        TriageViewSet,        basename='triage')
router.register(r'queue',         TokenViewSet,         basename='token')
router.register(r'emergency',     EmergencyViewSet,     basename='emergency')
router.register(r'notifications', NotificationViewSet,  basename='notification')

urlpatterns = [
    path('dashboard/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),
    path('', include(router.urls)),
]
