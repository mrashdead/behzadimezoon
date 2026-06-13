from django.urls import path
from . import views

app_name = 'reservations'

urlpatterns = [
    # لیست رزروها
    path('', views.ReservationListView.as_view(), name='list'),

    # ایجاد رزرو جدید
    path('create/', views.ReservationCreateView.as_view(), name='create'),

    # جزئیات یک رزرو خاص
    path('<int:pk>/', views.ReservationDetailView.as_view(), name='detail'),

    # ویرایش رزرو
    path('<int:pk>/edit/', views.ReservationUpdateView.as_view(), name='edit'),

    # پیشنهاد: اگر بعدا خواستی دکمه لغو یا تغییر وضعیت سریع اضافه کنی، اینجا جایش است:
    # path('<int:pk>/cancel/', views.ReservationCancelView.as_view(), name='cancel'),
]
