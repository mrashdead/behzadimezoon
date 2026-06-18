from django.urls import path
from . import views

app_name = 'leaves'

urlpatterns = [
    path('submit/', views.leave_create, name='leave-create'),
    path('my/', views.seller_leaves, name='seller-leaves'),
    path('management/', views.management_list, name='management-list'),
    path('management/<int:pk>/approve/', views.approve_leave, name='approve-leave'),
    path('management/<int:pk>/reject/', views.reject_leave, name='reject-leave'),
]
