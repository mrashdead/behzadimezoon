from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

from reservations.models import Reservation
from django.db.utils import ProgrammingError
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

        try:
            active_totals = active_reservations.aggregate(
                total_gross_rent=Sum('rent_price'),
                total_discounts=Sum('discount_amount'),
                total_revenue=Sum('final_price'),
                total_deposit=Sum('deposit_amount'),
                total_remaining=Sum('remaining_amount'),
                total_refunded=Sum('refunded_amount'),
                total_remaining_paid=Sum('remaining_payment_amount'),
            )
            active_totals['total_cash_inflow'] = (
                (active_totals.get('total_deposit') or 0)
                + (active_totals.get('total_remaining_paid') or 0)
                - (active_totals.get('total_refunded') or 0)
            )
        except ProgrammingError:
            # DB schema not migrated yet; provide safe defaults
            active_totals = {
                'total_gross_rent': 0,
                'total_discounts': 0,
                'total_revenue': 0,
                'total_deposit': 0,
                'total_remaining': 0,
                'total_refunded': 0,
                'total_remaining_paid': 0,
                'total_cash_inflow': 0,
            }

        total_reservations = all_reservations.aggregate(
            total_reservations=Count('id')
        )

        cancelled_reservations = Reservation.objects.filter(
            status=ReservationStatus.CANCELLED
        )

        try:
            cancelled_totals = cancelled_reservations.aggregate(
                total_cancelled_reservations=Count('id'),
                cancelled_received_amount=Sum('deposit_amount'),
                cancelled_refunded_amount=Sum('refunded_amount'),
            )
        except ProgrammingError:
            cancelled_totals = {
                'total_cancelled_reservations': 0,
                'cancelled_received_amount': 0,
                'cancelled_refunded_amount': 0,
            }

        context['page_title'] = 'مالی'
        context['totals'] = {
            'total_reservations': total_reservations.get('total_reservations') or 0,
            'total_revenue': active_totals.get('total_revenue') or 0,
            'total_gross_rent': active_totals.get('total_gross_rent') or 0,
            'total_discounts': active_totals.get('total_discounts') or 0,
            'total_deposit': active_totals.get('total_deposit') or 0,
            'total_remaining': active_totals.get('total_remaining') or 0,
            'total_cash_inflow': active_totals.get('total_cash_inflow') or 0,
            'total_refunded': active_totals.get('total_refunded') or 0,
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
