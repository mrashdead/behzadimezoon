# reservations/urls.py

from django.urls import path
from . import views

app_name = 'reservations'

urlpatterns = [
    path('', views.ReservationListView.as_view(), name='list'),
    path('create/', views.ReservationCreateView.as_view(), name='create'),
    path('<int:pk>/', views.ReservationDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.ReservationUpdateView.as_view(), name='edit'),

    # اضافه کردن مسیر تغییر وضعیت (برای دکمه‌های داخل لیست یا جزئیات)
   path('check-availability/', views.CheckAvailabilityView.as_view(), name='check_availability'),

]
