#dashboard/views.py
from django.views.generic import TemplateView
from django.db.models import Sum
from customers.models import Customer
from products.models import Dress
from reservations.constants import ReservationStatus
from reservations.utils import get_reservations_for_user
from reservations.models import Reservation


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

        # Only count income from delivered (completed) reservations, excluding cancelled
        total_income = user_reservations.filter(
            status=ReservationStatus.DELIVERED
        ).exclude(
            status=ReservationStatus.CANCELLED
        ).aggregate(total=Sum('final_price'))['total'] or 0
        context['total_income'] = total_income

        context['recent_reservations'] = user_reservations.select_related(
            'customer', 'dress'
        ).order_by('-created_at')[:3]

        context['active_reservations'] = user_reservations.select_related(
            'customer', 'dress'
        ).filter(
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
