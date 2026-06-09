from django.views.generic import ListView, DetailView, TemplateView
from .models import Reservation


class ReservationListView(ListView):
    model = Reservation
    template_name = 'reservations/list.html'
    context_object_name = 'reservations'
    paginate_by = 20
    ordering = ['-id']

    def get_queryset(self):
        queryset = super().get_queryset()
        status = self.request.GET.get('status')

        if status:
            queryset = queryset.filter(status=status)

        return queryset.select_related('customer', 'dress')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'رزروها'
        context['current_status'] = self.request.GET.get('status', '')
        return context


class ReservationDetailView(DetailView):
    model = Reservation
    template_name = 'reservations/detail.html'
    context_object_name = 'reservation'

    def get_queryset(self):
        return Reservation.objects.select_related('customer', 'dress')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'جزئیات رزرو'
        return context


class ReservationCreateView(TemplateView):
    template_name = 'reservations/form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'ثبت رزرو'
        context['form_mode'] = 'create'
        return context


class ReservationUpdateView(TemplateView):
    template_name = 'reservations/form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'ویرایش رزرو'
        context['form_mode'] = 'update'
        return context
