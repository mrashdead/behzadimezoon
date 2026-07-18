from django.urls import path
from .views import ReportsIndexView, export_reports_excel

app_name = 'reports'

urlpatterns = [
    path('', ReportsIndexView.as_view(), name='index'),
    path('export/excel/', export_reports_excel, name='export_excel'),
]
