#dashboard/urls.py
from django.urls import path
from .views import DashboardView, TempFormsView, TempUIView

app_name = 'dashboard'

urlpatterns = [
    path('', DashboardView.as_view(), name='index'),
    path('temp/', TempUIView.as_view(), name='temp-ui'),
    path('temp-forms/', TempFormsView.as_view(), name='temp-forms'),
]
