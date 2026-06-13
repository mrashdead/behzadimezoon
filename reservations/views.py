# reservations/views.py

from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView
from products.models import Dress


from .forms import ReservationForm
from .models import Reservation
from .services.change_status import change_reservation_status
from .services.status_machine import get_allowed_next_statuses


def get_status_choices():
    return Reservation._meta.get_field('status').choices


def get_status_values():
    return [choice[0] for choice in get_status_choices()]


class ReservationListView(LoginRequiredMixin, ListView):
    model = Reservation
    template_name = 'reservations/list.html'
    context_object_name = 'reservations'
    paginate_by = 20

    def get_queryset(self):
        queryset = Reservation.objects.select_related('customer', 'dress').all()
        status = self.request.GET.get('status')

        if status in get_status_values():
            queryset = queryset.filter(status=status)

        return queryset.order_by('-id')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_reservations = Reservation.objects.all()

        context.update({
            'page_title': 'رزروها',
            'form': ReservationForm(),
            'current_status': self.request.GET.get('status', ''),
            'status_choices': get_status_choices(),
            'total_count': all_reservations.count(),
            'pending_count': all_reservations.filter(status='pending').count(),
            'reserved_count': all_reservations.filter(status='reserved').count(),
            'delivered_count': all_reservations.filter(status='delivered').count(),
            'returned_count': all_reservations.filter(status='returned').count(),
            'cancelled_count': all_reservations.filter(status='cancelled').count(),
        })
        return context


class ReservationDetailView(LoginRequiredMixin, DetailView):
    model = Reservation
    template_name = 'reservations/detail.html'
    context_object_name = 'reservation'

    def get_queryset(self):
        return Reservation.objects.select_related('customer', 'dress')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reservation = self.object

        context.update({
            'page_title': 'جزئیات رزرو',
            'status_choices': get_status_choices(),
            'allowed_next_statuses': get_allowed_next_statuses(
                self.request.user,
                reservation
            ),
        })
        return context

class ReservationCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView):
    model = Reservation
    form_class = ReservationForm
    template_name = 'reservations/form.html'
    success_url = reverse_lazy('reservations:list')
    success_message = 'رزرو جدید با موفقیت ثبت شد.'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'ثبت رزرو',
            'form_mode': 'create',
        })
        return context

    def form_valid(self, form):
        dress = form.cleaned_data.get('dress')

        if dress and not form.instance.rent_price_snapshot:
            form.instance.rent_price_snapshot = dress.daily_rent_price

        return super().form_valid(form)

class ReservationUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = Reservation
    form_class = ReservationForm
    template_name = 'reservations/form.html'
    success_url = reverse_lazy('reservations:list')
    success_message = 'اطلاعات رزرو با موفقیت ویرایش شد.'

    def get_queryset(self):
        return Reservation.objects.select_related('customer', 'dress')

    def form_valid(self, form):
        dress = form.cleaned_data.get('dress')

        if dress and not form.instance.rent_price_snapshot:
            form.instance.rent_price_snapshot = dress.daily_rent_price

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'page_title': 'ویرایش رزرو',
            'form_mode': 'update',
        })
        return context


class ReservationChangeStatusView(LoginRequiredMixin, View):
    def post(self, request, pk):
        reservation = get_object_or_404(Reservation, pk=pk)
        new_status = request.POST.get('status')

        if new_status not in get_status_values():
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
            messages.error(
                request,
                exc.messages[0] if getattr(exc, 'messages', None) else 'درخواست نامعتبر است.'
            )
        except PermissionDenied:
            messages.error(request, 'شما اجازه تغییر وضعیت این رزرو را ندارید.')
        except Exception:
            messages.error(request, 'خطای غیرمنتظره‌ای رخ داد.')

        return redirect('reservations:detail', pk=reservation.pk)


class CheckAvailabilityView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        dress_id = request.POST.get('dress') or request.POST.get('dress_id')
        rent_date = request.POST.get('rent_date')
        rent_days = request.POST.get('rent_days')
        reservation_id = request.POST.get('reservation_id')

        print('POST DATA =', dict(request.POST))
        print('dress_id =', dress_id)
        print('rent_date =', rent_date)
        print('rent_days =', rent_days)
        print('reservation_id =', reservation_id)

        if not dress_id or not rent_date or not rent_days:
            return JsonResponse({
                'available': False,
                'message': 'اطلاعات ناقص است.',
                'debug': {
                    'dress_id': dress_id,
                    'rent_date': rent_date,
                    'rent_days': rent_days,
                    'reservation_id': reservation_id,
                    'raw_post': dict(request.POST),
                }
            }, status=400)

        try:
            rent_days = int(rent_days)
            start_date = datetime.strptime(rent_date, '%Y-%m-%d').date()
            return_date = start_date + timedelta(days=rent_days)
        except (ValueError, TypeError):
            return JsonResponse({
                'available': False,
                'message': 'فرمت تاریخ یا تعداد روز نامعتبر است.',
                'debug': {
                    'rent_date': rent_date,
                    'rent_days': rent_days,
                    'raw_post': dict(request.POST),
                }
            }, status=400)

        qs = Reservation.objects.filter(
            dress_id=dress_id,
            rent_date__lt=return_date,
            return_date__gt=start_date
        ).exclude(status='cancelled')

        if reservation_id:
            qs = qs.exclude(pk=reservation_id)

        is_reserved = qs.exists()

        return JsonResponse({
            'available': not is_reserved,
            'return_date': return_date.strftime('%Y-%m-%d'),
            'message': 'لباس آزاد است.' if not is_reserved else 'لباس در این بازه رزرو شده است.'
        })
