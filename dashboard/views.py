#dashboard/views.py
from django.views.generic import TemplateView
from django.db.models import Sum
from customers.models import Customer
from products.models import Dress
from reservations.constants import ReservationStatus
from reservations.utils import get_reservations_for_user
from reservations.models import Reservation
from financial.services import DashboardService


class DashboardView(TemplateView):
    template_name = 'dashboard/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get filtered reservations based on user role
        user_reservations = get_reservations_for_user(self.request.user)

        context['customers_count'] = Customer.objects.count()
        context['dresses_count'] = Dress.objects.count()
        context['active_reservations_count'] = user_reservations.filter(
            status__in=[
                ReservationStatus.DRAFT,
                ReservationStatus.CONFIRMED,
                ReservationStatus.DELIVERED,
            ]
        ).count()

        # Financial context (transaction-first where available)
        financial_ctx = DashboardService.get_financial_context()
        context['totals'] = financial_ctx.get('totals', {})
        context['recent_transactions'] = financial_ctx.get('recent_transactions', [])
        context['uses_transaction_ledger'] = financial_ctx.get('uses_transaction_ledger', False)
        context['open_reconciliation_issues'] = financial_ctx.get('open_reconciliation_issues', 0)
        # Backwards-compatible single value used in template
        context['total_income'] = context['totals'].get('total_cash_inflow', 0)

        # Defer newly added DB columns until migrations have been applied
        context['recent_reservations'] = user_reservations.select_related(
            'customer', 'dress'
        ).defer('discount_type', 'discount_value', 'discount_amount', 'refunded_amount').order_by('-created_at')[:3]

        context['active_reservations'] = user_reservations.select_related(
            'customer', 'dress'
        ).defer('discount_type', 'discount_value', 'discount_amount', 'refunded_amount').filter(
            status__in=[
                ReservationStatus.DRAFT,
                ReservationStatus.CONFIRMED,
                ReservationStatus.DELIVERED,
            ]
        ).order_by('-created_at')[:3]

        context['page_title'] = 'داشبورد'
        return context

class TempUIView(TemplateView):
    template_name = 'dashboard/temp-ui.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'صفحه آزمایشی'
        return context
class TempFormsView(TemplateView):
    template_name = 'dashboard/temp-forms.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'صفحه آزمایشی'
        return context
