from django.urls import path
from .views import (
    DressCreateView,
    DressDetailView,
    DressListView,
    DressUpdateView,
)

app_name = 'products'

urlpatterns = [
    path('', DressListView.as_view(), name='list'),
    path('create/', DressCreateView.as_view(), name='create'),
    path('<int:pk>/', DressDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', DressUpdateView.as_view(), name='edit'),
]
