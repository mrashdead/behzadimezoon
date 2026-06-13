# reservations/views.py

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView

from .forms import ReservationForm
from .models import Reservation
from reservations.services.change_status import change_reservation_status
from reservations.services.status_machine import get_allowed_next_statuses


# ---------------------------------------------------------
#   Reservation List
# ---------------------------------------------------------
class ReservationListView(LoginRequiredMixin, ListView):
    model = Reservation
    template_name = 'reservations/list.html'
    context_object_name = 'reservations'
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            Reservation.objects
            .select_related('customer', 'dress', 'created_by')
            .order_by('-id')
        )

        status = self.request.GET.get('status')
        valid_statuses = [choice[0] for choice in Reservation.Status.choices]

        if status in valid_statuses:
            queryset = queryset.filter(status=status)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        all_reservations = Reservation.objects.all()

        context.update({
            'page_title': 'رزروها',
            'current_status': self.request.GET.get('status', ''),
            'status_choices': Reservation.Status.choices,

            'total_count': all_reservations.count(),
            'draft_count': all_reservations.filter(status=Reservation.Status.DRAFT).count(),
            'confirmed_count': all_reservations.filter(status=Reservation.Status.CONFIRMED).count(),
            'delivered_count': all_reservations.filter(status=Reservation.Status.DELIVERED).count(),
            'returned_count': all_reservations.filter(status=Reservation.Status.RETURNED).count(),
            'laundry_count': all_reservations.filter(status=Reservation.Status.LAUNDRY).count(),
            'canceled_count': all_reservations.filter(status=Reservation.Status.CANCELED).count(),
        })
        return context



# ---------------------------------------------------------
#   Reservation Detail
# ---------------------------------------------------------
class ReservationDetailView(LoginRequiredMixin, DetailView):
    model = Reservation
    template_name = 'reservations/detail.html'
    context_object_name = 'reservation'

    def get_queryset(self):
        # Load related foreign keys for faster DB access
        return Reservation.objects.select_related(
            'customer',
            'dress',
            'created_by'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reservation = self.object

        context.update({
            'page_title': 'جزئیات رزرو',
            'status_choices': Reservation.Status.choices,
            'allowed_next_statuses': get_allowed_next_statuses(
                self.request.user,
                reservation
            ),
        })
        return context


# ---------------------------------------------------------
#   Create Reservation
# ---------------------------------------------------------
class ReservationCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Reservation
    form_class = ReservationForm
    template_name = 'reservations/form.html'
    success_url = reverse_lazy('reservations:list')
    success_message = "رزرو جدید با موفقیت ثبت شد."

    def form_valid(self, form):
        # Set creator of this reservation
        form.instance.created_by = self.request.user

        # Snapshot rent price on create
        if not form.instance.rent_price_snapshot:
            form.instance.rent_price_snapshot = form.instance.dress.rent_price

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'ثبت رزرو',
            'form_mode': 'create',
        })
        return context


# ---------------------------------------------------------
#   Update Reservation
# ---------------------------------------------------------
class ReservationUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Reservation
    form_class = ReservationForm
    template_name = 'reservations/form.html'
    success_url = reverse_lazy('reservations:list')
    success_message = "اطلاعات رزرو با موفقیت ویرایش شد."

    def get_queryset(self):
        return Reservation.objects.select_related('customer', 'dress')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'ویرایش رزرو',
            'form_mode': 'update',
        })
        return context


# ---------------------------------------------------------
#   Change Reservation Status
# ---------------------------------------------------------
class ReservationChangeStatusView(LoginRequiredMixin, View):

    def post(self, request, pk):
        reservation = get_object_or_404(Reservation, pk=pk)
        new_status = request.POST.get('status')

        valid_statuses = [choice[0] for choice in Reservation.Status.choices]

        if new_status not in valid_statuses:
            messages.error(request, 'وضعیت انتخاب‌شده معتبر نیست.')
            return redirect('reservations:detail', pk=reservation.pk)

        try:
            change_reservation_status(
                user=request.user,
                reservation=reservation,
                new_status=new_status,
            )
            messages.success(request, 'وضعیت رزرو با موفقیت تغییر کرد.')

        except ValidationError as exc:
            messages.error(request, exc.messages[0] if exc.messages else "درخواست نامعتبر است.")

        except PermissionDenied:
            messages.error(request, 'شما اجازه تغییر وضعیت این رزرو را ندارید.')

        except Exception:
            messages.error(request, 'خطای غیرمنتظره‌ای رخ داد.')

        return redirect('reservations:detail', pk=reservation.pk)
