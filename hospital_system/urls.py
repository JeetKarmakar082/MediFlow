from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.views import (
    login_view, logout_view, dashboard_view,
    patients_view, triage_view, queue_view,
    doctors_view, emergency_view, queue_display_view,
    assessments_view, schedules_view, records_view,
)

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Auth pages
    path('login/',  login_view,  name='login'),
    path('logout/', logout_view, name='logout'),

    # Frontend pages (all protected — redirect to login if not authenticated)
    path('',                          dashboard_view,     name='dashboard'),
    path('patients/',                 patients_view,      name='patients'),
    path('patients/register/',        patients_view,      name='patients-register'),
    path('triage/',                   triage_view,        name='triage'),
    path('triage/new/',               triage_view,        name='triage-new'),
    path('queue/',                    queue_view,         name='queue'),
    path('queue/new/',                queue_view,         name='queue-new'),
    path('doctors/',                  doctors_view,       name='doctors'),
    path('emergency/',                emergency_view,     name='emergency'),
    path('emergency/new/',            emergency_view,     name='emergency-new'),
    path('assessments/',              assessments_view,   name='assessments'),
    path('schedules/',                schedules_view,     name='schedules'),
    path('records/',                  records_view,       name='records'),
    path('display/<str:department>/', queue_display_view, name='queue-display'),

    # REST APIs
    path('api/', include('apps.urls')),

] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
