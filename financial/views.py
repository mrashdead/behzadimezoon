from django.contrib.auth.decorators import login_required
from django.db.utils import ProgrammingError
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.http import HttpResponse
import csv
from financial.services.reconciliation_service import ReconciliationService
from financial.services.transaction_service import TransactionService

from financial.services.dashboard_service import DashboardService
from reservations.models import Reservation
from accounts.models import User


@method_decorator(login_required, name='dispatch')
class FinancialListView(TemplateView):
    template_name = 'financial/list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # parse filters from query params
        params = {
            'date_from': self.request.GET.get('date_from'),
            'date_to': self.request.GET.get('date_to'),
            'seller_id': self.request.GET.get('seller'),
            'ledger_mode': self.request.GET.get('ledger', None),
        }

        reporting = {}
        try:
            financial_ctx = DashboardService.get_financial_context(filters=params)
            totals = financial_ctx.get('totals', {})
            cancelled_totals = financial_ctx.get('cancelled_totals', {})
            recent_reservations = financial_ctx.get('recent_reservations', [])
            uses_transaction_ledger = financial_ctx.get('uses_transaction_ledger', False)
            open_reconciliation_issues = financial_ctx.get('open_reconciliation_issues', 0)
            reporting = financial_ctx.get('reporting', {})
        except ProgrammingError:
            totals = {
                'total_reservations': 0,
                'total_revenue': 0,
                'total_gross_rent': 0,
                'total_discounts': 0,
                'total_deposit': 0,
                'total_remaining': 0,
                'total_damage_received': 0,
                'total_cash_inflow': 0,
                'total_refunded': 0,
            }
            cancelled_totals = {
                'total_cancelled_reservations': 0,
                'cancelled_received_amount': 0,
                'cancelled_damage_received': 0,
                'cancelled_refunded_amount': 0,
            }
            recent_reservations = Reservation.objects.none()
            uses_transaction_ledger = False
            open_reconciliation_issues = 0
            reporting = {}

        context['page_title'] = 'مالی'
        context['totals'] = totals
        context['cancelled_totals'] = cancelled_totals
        context['recent_reservations'] = recent_reservations
        context['uses_transaction_ledger'] = uses_transaction_ledger
        context['open_reconciliation_issues'] = open_reconciliation_issues
        context['reporting'] = reporting
        # sellers for filter dropdown
        context['sellers'] = User.objects.filter(role='SELLER')
        return context


@login_required
def export_financial_csv(request):
    params = {
        'date_from': request.GET.get('date_from'),
        'date_to': request.GET.get('date_to'),
        'seller_id': request.GET.get('seller'),
        'ledger_mode': request.GET.get('ledger', None),
    }
    ctx = DashboardService.get_financial_context(filters=params)
    reservations = ctx.get('recent_reservations', [])

    resp = HttpResponse(content_type='text/csv')
    resp['Content-Disposition'] = 'attachment; filename="financial_export.csv"'
    writer = csv.writer(resp)
    writer.writerow(['reservation_id', 'customer', 'dress', 'final_price', 'deposit', 'remaining', 'status', 'tx_total_deposit', 'tx_total_final_payment', 'tx_total_refund', 'reconcile_action'])
    for r in reservations:
        totals = TransactionService.aggregate_reservation_totals(r)
        recon = ReconciliationService.reservation_discrepancies(r)
        writer.writerow([
            r.pk,
            str(r.customer),
            str(r.dress),
            getattr(r, 'final_price', 0),
            getattr(r, 'deposit_amount', 0),
            getattr(r, 'remaining_amount', 0),
            r.status,
            totals.get('total_deposit') or 0,
            totals.get('total_final_payment') or 0,
            totals.get('total_refund') or 0,
            recon.get('action_label') if recon else '',
        ])
    return resp
