#customers/urls.py
from django.urls import path
from .views import (
    CustomerCreateView,
    CustomerListView,
    CustomerUpdateView,
    CustomerDeleteView,
)

app_name = 'customers'

urlpatterns = [
    path('', CustomerListView.as_view(), name='list'),
    path('create/', CustomerCreateView.as_view(), name='create'),
    path('edit/<int:pk>/', CustomerUpdateView.as_view(), name='update'),
    path('<int:pk>/delete/', CustomerDeleteView.as_view(), name='delete'),
]
