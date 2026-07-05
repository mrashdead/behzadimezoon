from django.urls import path
from .views import FinancialListView
from .views_transactions import TransactionListView
from .views_reconcile import (
    reconciliation_admin_view,
    reconciliation_resolve_view,
    ReconciliationAdminPageView,
)
from .views_operations import (
    reservation_financial_view,
    add_guarantee_view,
    return_guarantee_view,
    add_damage_view,
    create_transaction_view,
    cancel_reservation_flow,
)
from .views import FinancialListView, export_financial_csv

app_name = 'financial'

urlpatterns = [
    path('', FinancialListView.as_view(), name='list'),
    path('export/csv/', export_financial_csv, name='export_csv'),
    path('transactions/', TransactionListView.as_view(), name='transactions'),
    path('reconcile-admin/', reconciliation_admin_view, name='reconcile_admin'),
    path('reconcile-admin/ui/', ReconciliationAdminPageView.as_view(), name='reconcile_admin_ui'),
    path('reconcile-admin/resolve/', reconciliation_resolve_view, name='reconcile_resolve'),
    # Staff financial operations per-reservation
    path('reservation/<int:pk>/financial/', reservation_financial_view, name='reservation_financial'),
    path('reservation/<int:pk>/guarantee/add/', add_guarantee_view, name='add_guarantee'),
    path('guarantee/<int:pk>/return/', return_guarantee_view, name='return_guarantee'),
    path('reservation/<int:pk>/damage/add/', add_damage_view, name='add_damage'),
    path('reservation/<int:pk>/transaction/create/', create_transaction_view, name='create_transaction'),
    path('reservation/<int:pk>/cancel/', cancel_reservation_flow, name='cancel_reservation'),
]
