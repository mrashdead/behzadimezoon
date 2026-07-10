# financial/views_transactions.py

from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView

from financial.models import Transaction


@method_decorator(login_required, name='dispatch')
class TransactionListView(ListView):
    model = Transaction
    template_name = 'financial/transactions_list.html'
    context_object_name = 'transactions'
    paginate_by = 25

    def get_queryset(self):
        # Filter out voided transactions and select related for performance
        return (
            Transaction.objects.filter(
                is_voided=False,
                transaction_status=Transaction.TransactionStatus.POSTED,
            )
            .select_related('reservation', 'customer', 'account', 'category', 'created_by')
            .order_by('-transaction_date')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'لیست تراکنش‌ها'

        # Add filter form if implemented in views.py
        # context['filter_form'] = TransactionFilterForm(self.request.GET)

        # Add quick stats (calculated using TransactionService or DashboardService)
        try:
            from financial.services.transaction_service import TransactionService
            stats = {
                'total_inflow': TransactionService.get_total_inflow(),
                'total_outflow': TransactionService.get_total_outflow(),
                'total_net': TransactionService.get_total_net_financial(),
                'total_count': self.get_queryset().count(),
            }
            context['stats'] = stats
        except Exception:
            context['stats'] = {}

        return context


class TransactionDetailView(DetailView):
    model = Transaction
    template_name = 'financial/transaction_detail.html'
    context_object_name = 'transaction'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f'جزئیات تراکنش {self.object.transaction_number}'
        return context
