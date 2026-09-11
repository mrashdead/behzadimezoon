#products/urls.py
from django.urls import path
from .views import (
    DressBulkDeleteView,
    DressCreateView,
    DressDeleteView,
    DressListView,
    DressUpdateView,
    export_products_excel,
)

app_name = 'products'

urlpatterns = [
    path('', DressListView.as_view(), name='list'),
    path('export/excel/', export_products_excel, name='export_excel'),
    path('add/', DressCreateView.as_view(), name='add'),
    path('<int:pk>/edit/', DressUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', DressDeleteView.as_view(), name='delete'),
    path('delete-selected/', DressBulkDeleteView.as_view(), name='delete_selected'),
]
