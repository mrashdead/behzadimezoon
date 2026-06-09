from django.urls import path
from .views import ReportsIndexView

app_name = 'reports'

urlpatterns = [
    path('', ReportsIndexView.as_view(), name='index'),
]
