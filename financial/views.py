from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, Q
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

from reservations.models import Reservation
from reservations.constants import ReservationStatus


@method_decorator(login_required, name='dispatch')
class FinancialListView(TemplateView):
    template_name = 'financial/list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        all_reservations = Reservation.objects.all()
        active_reservations = all_reservations.exclude(
            status=ReservationStatus.CANCELLED
        )

        active_totals = active_reservations.aggregate(
            total_revenue=Sum('final_price'),
            total_deposit=Sum('deposit_amount'),
            total_remaining=Sum('remaining_amount'),
        )

        total_reservations = all_reservations.aggregate(
            total_reservations=Count('id')
        )

        # Cancelled reservations - only count received amounts (deposits)
        cancelled_reservations = Reservation.objects.filter(
            status=ReservationStatus.CANCELLED
        )

        cancelled_totals = cancelled_reservations.aggregate(
            total_cancelled_reservations=Count('id'),
            cancelled_received_amount=Sum('deposit_amount'),  # Only received amount counts
        )

        context['page_title'] = 'مالی'
        context['totals'] = {
            'total_reservations': total_reservations.get('total_reservations') or 0,
            'total_revenue': active_totals.get('total_revenue') or 0,
            'total_deposit': active_totals.get('total_deposit') or 0,
            'total_remaining': active_totals.get('total_remaining') or 0,
        }

        # Add cancelled reservation info
        context['cancelled_totals'] = {
            'total_cancelled_reservations': cancelled_totals.get('total_cancelled_reservations') or 0,
            'cancelled_received_amount': cancelled_totals.get('cancelled_received_amount') or 0,
        }

        context['recent_reservations'] = (
            Reservation.objects.select_related('customer', 'dress', 'created_by')
            .order_by('-created_at')[:10]
        )
        return context
