from django.urls import path
from . import views
from . import views_operations
from . import views_reconcile
from . import views_transactions

app_name = 'financial'

urlpatterns = [
    # داشبورد مالی اصلی
    path('', views.FinancialDashboardView.as_view(), name='list'),
    path('dashboard/', views.FinancialDashboardView.as_view(), name='dashboard'),
    path('export/excel/', views.export_financial_excel, name='export_excel'),
    path('export/reports/', views.export_financial_excel, name='export_reports'),

    # API Endpoints
    path('api/reservation-search/', views.api_reservation_search, name='api_reservation_search'),
    path('api/reservation-info/', views.api_reservation_info, name='api_reservation_info'),

    # عملیات پرداخت سریع از داشبورد
    path('record-payment/', views.record_payment_view, name='record_payment'),
    path('record-expense/', views.record_expense_view, name='record_expense'),

    # مدیریت تراکنش‌ها
    path('transactions/', views_transactions.TransactionListView.as_view(), name='transactions'),
    path('transactions/<int:pk>/detail/', views_transactions.TransactionDetailView.as_view(), name='transaction_detail'),
    # path('transactions/new/', views_transactions.create_transaction_view, name='create_transaction'), # Handled via quick action modals or reservation financial view
    # path('transactions/<int:pk>/edit/', views_transactions.edit_transaction_view, name='edit_transaction'), # Implement if direct transaction editing needed
    # path('transactions/<int:pk>/void/', views_transactions.void_transaction_view, name='void_transaction'), # Implement if direct voiding needed

    # مدیریت پرداخت‌ها
    path('payments/entry/', views.PaymentEntryView.as_view(), name='payment_entry'),
    # path('payments/pending/', views.pending_payments_view, name='pending_payments'), # Placeholder
    # path('payments/history/', views.payment_history_view, name='payment_history'), # Placeholder

    # حساب‌ها و مطالبات (placeholder views for now)
    # path('accounts/', views.accounts_list_view, name='accounts'),
    # path('accounts/new/', views.create_account_view, name='create_account'),
    # path('receivables/', views.receivables_view, name='receivables'),

    # گزارشات مالی
    path('reports/', views.ReportsView.as_view(), name='reports'),
    # path('reports/daily/', views.daily_report_view, name='daily_report'),
    # path('reports/monthly/', views.monthly_report_view, name='monthly_report'),

    # هماهنگی و اصلاح
    path('reconciliation/', views_reconcile.ReconciliationAdminPageView.as_view(), name='reconcile_admin'),
    path('reconciliation/ui/', views_reconcile.ReconciliationAdminPageView.as_view(), name='reconcile_admin_ui'),
    path('reconciliation/resolve/', views_reconcile.reconciliation_resolve_view, name='reconcile_resolve'),
    path('reconciliation/manual-reconcile/', views_reconcile.reconcile_transactions_manual_view, name='manual_reconcile'),

    # تنظیمات مالی (placeholder view)
    # path('settings/', views.financial_settings_view, name='settings'),

    # عملیات مالی مرتبط با رزرو (از views_operations)
    path('reservation/<int:pk>/financial/', views_operations.reservation_financial_view, name='reservation_financial'),
    path('reservation/<int:pk>/guarantee/add/', views_operations.add_guarantee_view, name='add_guarantee'),
    path('guarantee/<int:pk>/return/', views_operations.return_guarantee_view, name='return_guarantee'),
    path('reservation/<int:pk>/damage/add/', views_operations.add_damage_view, name='add_damage'),
    path('reservation/<int:pk>/transaction/create/', views_operations.create_transaction_view, name='create_transaction'),
    path('reservation/<int:pk>/cancel-flow/', views_operations.cancel_reservation_flow, name='cancel_reservation_flow'),
    path('reservation/<int:pk>/cancel-flow/', views_operations.cancel_reservation_flow, name='cancel_reservation'),
]
