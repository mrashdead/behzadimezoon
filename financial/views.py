from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

from reservations.models import Reservation


@method_decorator(login_required, name='dispatch')
class FinancialListView(TemplateView):
    template_name = 'financial/list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        totals = Reservation.objects.aggregate(
            total_reservations=Count('id'),
            total_revenue=Sum('final_price'),
            total_deposit=Sum('deposit_amount'),
            total_remaining=Sum('remaining_amount'),
        )
        context['page_title'] = 'مالی'
        context['totals'] = {
            'total_reservations': totals.get('total_reservations') or 0,
            'total_revenue': totals.get('total_revenue') or 0,
            'total_deposit': totals.get('total_deposit') or 0,
            'total_remaining': totals.get('total_remaining') or 0,
        }
        context['recent_reservations'] = (
            Reservation.objects.select_related('customer', 'dress', 'created_by')
            .order_by('-created_at')[:10]
        )
        return context
