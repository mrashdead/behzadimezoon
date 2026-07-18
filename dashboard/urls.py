#dashboard/urls.py
from django.urls import path
from .views import (
    DashboardView,
    TempFormsView,
    TempUIView,
    backup_download_view,
    backup_list_view,
)

app_name = 'dashboard'

urlpatterns = [
    path('', DashboardView.as_view(), name='index'),
    path('temp/', TempUIView.as_view(), name='temp-ui'),
    path('temp-forms/', TempFormsView.as_view(), name='temp-forms'),
    path('backups/', backup_list_view, name='backup_list'),
    path('backups/download/<str:token>/', backup_download_view, name='backup_download'),
]
