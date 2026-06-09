#dashboard/views.py
from django.views.generic import TemplateView
from customers.models import Customer
from products.models import Dress
from reservations.models import Reservation


class DashboardView(TemplateView):
    template_name = 'dashboard/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['customers_count'] = Customer.objects.count()
        context['dresses_count'] = Dress.objects.count()
        context['active_reservations_count'] = Reservation.objects.filter(
            status__in=['DRAFT', 'CONFIRMED', 'DELIVERED']
        ).count()

        context['page_title'] = 'داشبورد'
        return context
