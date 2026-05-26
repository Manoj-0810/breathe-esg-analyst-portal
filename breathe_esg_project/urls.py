"""
URL configuration for breathe_esg_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from breathe_esg.views import (
    IngestView,
    IngestionJobListView,
    IngestionJobRowsView,
    ApproveRowView,
    FlagRowView,
    DashboardView,
    AuditLogListView
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/ingest/<str:source_type>/', IngestView.as_view(), name='api-ingest'),
    path('api/runs/', IngestionJobListView.as_view(), name='api-runs-list'),
    path('api/runs/<uuid:pk>/rows/', IngestionJobRowsView.as_view(), name='api-runs-rows'),
    path('api/rows/<uuid:pk>/approve/', ApproveRowView.as_view(), name='api-rows-approve'),
    path('api/rows/<uuid:pk>/flag/', FlagRowView.as_view(), name='api-rows-flag'),
    path('api/dashboard/', DashboardView.as_view(), name='api-dashboard'),
    path('api/audit-logs/', AuditLogListView.as_view(), name='api-audit-logs'),
]

