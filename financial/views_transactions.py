from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView

from financial.models import Transaction


@method_decorator(login_required, name='dispatch')
class TransactionListView(ListView):
    model = Transaction
    template_name = 'financial/transactions_list.html'
    context_object_name = 'transactions'
    paginate_by = 25

    def get_queryset(self):
        return Transaction.objects.select_related('reservation', 'created_by').order_by('-transaction_date')
