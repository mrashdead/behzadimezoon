from django.urls import path
from .views import FinancialListView

app_name = 'financial'

urlpatterns = [
    path('', FinancialListView.as_view(), name='list'),
]
