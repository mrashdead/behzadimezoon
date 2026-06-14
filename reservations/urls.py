# reservations/urls.py

from django.urls import path
from .views import (
    ReservationListView,
    ReservationCreateView,
    ReservationUpdateView,
    ReservationDetailView,
    ReservationDeleteView,
    change_reservation_status_view,
    CheckAvailabilityView
)

app_name = 'reservations'

urlpatterns = [
    path('', ReservationListView.as_view(), name='list'),
    path('create/', ReservationCreateView.as_view(), name='create'),
    path('<int:pk>/edit/', ReservationUpdateView.as_view(), name='edit'),
    path('<int:pk>/detail/', ReservationDetailView.as_view(), name='detail'),
    path('<int:pk>/delete/', ReservationDeleteView.as_view(), name='delete'),
    path('<int:pk>/status/<str:new_status>/', change_reservation_status_view, name='change_status'),
    path('check-availability/',CheckAvailabilityView.as_view(),name='check_availability'),
]
