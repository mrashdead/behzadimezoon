from django.urls import path
from .views import (
    ReservationCreateView,
    ReservationDetailView,
    ReservationListView,
    ReservationUpdateView,
)

app_name = 'reservations'

urlpatterns = [
    path('', ReservationListView.as_view(), name='list'),
    path('create/', ReservationCreateView.as_view(), name='create'),
    path('<int:pk>/', ReservationDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', ReservationUpdateView.as_view(), name='edit'),
]
