#dashboard/views.py
from django.views.generic import TemplateView
from django.db.models import Sum
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

        total_income = Reservation.objects.filter(
            status='DELIVERED'
        ).aggregate(total=Sum('final_price'))['total'] or 0
        context['total_income'] = total_income

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
