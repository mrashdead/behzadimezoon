#products/urls.py
from django.urls import path
from .views import (
    DressCreateView,
    DressDeleteView,
    DressListView,
    DressUpdateView,
)

app_name = 'products'

urlpatterns = [
    path('', DressListView.as_view(), name='list'),
    path('add/', DressCreateView.as_view(), name='add'),
    path('<int:pk>/edit/', DressUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', DressDeleteView.as_view(), name='delete'),
]
