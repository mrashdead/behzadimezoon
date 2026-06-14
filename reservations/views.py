from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.http import JsonResponse
from .forms import ReservationForm
from django.views import View
from datetime import datetime, timedelta
from .models import Reservation
from .services.change_status import change_reservation_status
import jdatetime

class ReservationListView(LoginRequiredMixin, ListView):
    model = Reservation
    template_name = 'reservations/list.html'
    context_object_name = 'reservations'
    paginate_by = 10

    def get_queryset(self):
        qs = Reservation.objects.select_related('customer', 'dress', 'created_by').all()

        status_filter = self.request.GET.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        base_qs = Reservation.objects.all()

        context['current_status'] = self.request.GET.get('status', '')
        context['total_count'] = base_qs.count()
        context['draft_count'] = base_qs.filter(status=Reservation.Status.DRAFT).count()
        context['confirmed_count'] = base_qs.filter(status=Reservation.Status.CONFIRMED).count()
        context['delivered_count'] = base_qs.filter(status=Reservation.Status.DELIVERED).count()
        context['returned_count'] = base_qs.filter(status=Reservation.Status.RETURNED).count()
        context['laundry_count'] = base_qs.filter(status=Reservation.Status.LAUNDRY).count()
        context['canceled_count'] = base_qs.filter(status=Reservation.Status.CANCELED).count()

        context['create_form'] = ReservationForm()
        return context


class ReservationCreateView(CreateView):
    model = Reservation
    form_class = ReservationForm
    success_url = reverse_lazy('reservations:list')

    def get(self, request, *args, **kwargs):
        # دیگر صفحه form.html نداریم
        return redirect('reservations:list')

    def form_valid(self, form):
        reservation = form.save(commit=False)

        if reservation.dress:
            reservation.rent_price_snapshot = reservation.dress.daily_rent_price

        if reservation.rent_date and reservation.rent_days:
            reservation.return_date = reservation.rent_date + timedelta(days=reservation.rent_days)

        reservation.created_by = self.request.user
        reservation.save()

        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'رزرو با موفقیت ثبت شد.',
            })

        messages.success(self.request, 'رزرو با موفقیت ثبت شد.')
        return redirect(self.success_url)

    def form_invalid(self, form):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'errors': form.errors,
                'message': 'اطلاعات فرم نامعتبر است.',
            }, status=400)

        messages.error(self.request, 'اطلاعات فرم نامعتبر است.')
        return redirect(self.success_url)


class ReservationUpdateView(LoginRequiredMixin, UpdateView):
    model = Reservation
    form_class = ReservationForm
    template_name = 'reservations/form.html'
    success_url = reverse_lazy('reservations:list')

    def form_valid(self, form):
        instance = form.save(commit=False)

        if not instance.ceremony_date and instance.customer_id:
            customer_ceremony_date = getattr(instance.customer, 'ceremony_date', None)
            if customer_ceremony_date:
                instance.ceremony_date = customer_ceremony_date

        if not instance.rent_price_snapshot and instance.dress_id:
            dress_price = getattr(instance.dress, 'rent_price', None)
            if dress_price is not None:
                instance.rent_price_snapshot = dress_price

        instance.save()
        messages.success(self.request, 'رزرو با موفقیت ویرایش شد.')
        return redirect(self.success_url)


class ReservationDetailView(LoginRequiredMixin, DetailView):
    model = Reservation
    template_name = 'reservations/detail.html'
    context_object_name = 'reservation'


class ReservationDeleteView(LoginRequiredMixin, DeleteView):
    model = Reservation
    success_url = reverse_lazy('reservations:list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'رزرو با موفقیت حذف شد.')
        return super().delete(request, *args, **kwargs)


def change_reservation_status_view(request, pk, new_status):
    reservation = get_object_or_404(Reservation, pk=pk)

    try:
        change_reservation_status(reservation, new_status, user=request.user)
        messages.success(request, 'وضعیت رزرو با موفقیت تغییر کرد.')
    except Exception as e:
        messages.error(request, str(e))

    return redirect('reservations:list')

class CheckAvailabilityView(View):
    """
    بررسی موجود بودن لباس در بازه زمانی رزرو
    ورودی POST:
        - dress_id
        - rent_date
        - rent_days
        - reservation_id (اختیاری، برای edit)
        - only_calculate (اختیاری: اگر 1 باشد فقط return_date حساب می‌شود)
    خروجی:
        {
            "available": true/false,
            "message": "...",
            "return_date": "..."
        }
    """

    http_method_names = ['post']

    def post(self, request, *args, **kwargs):
        try:
            dress_id = (request.POST.get('dress_id') or '').strip()
            rent_date_raw = (request.POST.get('rent_date') or '').strip()
            rent_days_raw = (request.POST.get('rent_days') or '').strip()
            reservation_id = (request.POST.get('reservation_id') or '').strip()
            only_calculate = (request.POST.get('only_calculate') or '').strip()

            # دیباگ موقت، اگر خواستی بعداً حذفش کن
            print("DEBUG check_availability POST:", dict(request.POST))

            if not rent_date_raw:
                return JsonResponse({
                    'available': False,
                    'message': 'تاریخ شروع اجاره وارد نشده است.'
                }, status=400)

            rent_days = self._parse_positive_int(rent_days_raw)
            if not rent_days:
                return JsonResponse({
                    'available': False,
                    'message': 'تعداد روز اجاره نامعتبر است.'
                }, status=400)

            rent_date = self._parse_date(rent_date_raw)
            if not rent_date:
                return JsonResponse({
                    'available': False,
                    'message': 'فرمت تاریخ شروع اجاره نامعتبر است.'
                }, status=400)

            return_date = rent_date + timedelta(days=rent_days)

            # اگر فقط هدف محاسبه return_date باشد
            if only_calculate == '1':
                return JsonResponse({
                    'available': True,
                    'message': 'تاریخ تحویل محاسبه شد.',
                    'return_date': self._format_date(return_date, rent_date_raw),
                })

            if not dress_id:
                return JsonResponse({
                    'available': False,
                    'message': 'لباس انتخاب نشده است.'
                }, status=400)

            qs = Reservation.objects.filter(
                dress_id=dress_id,
                rent_date__lt=return_date,
                return_date__gt=rent_date,
            ).exclude(
                status__in=['canceled', 'cancelled']
            )

            if reservation_id:
                qs = qs.exclude(pk=reservation_id)

            conflict_exists = qs.exists()

            if conflict_exists:
                return JsonResponse({
                    'available': False,
                    'message': 'این لباس در بازه انتخابی قبلاً رزرو شده است.',
                    'return_date': self._format_date(return_date, rent_date_raw),
                })

            return JsonResponse({
                'available': True,
                'message': 'لباس در بازه انتخابی آزاد است.',
                'return_date': self._format_date(return_date, rent_date_raw),
            })

        except Exception as e:
            return JsonResponse({
                'available': False,
                'message': f'خطای سیستمی در بررسی موجودی: {str(e)}'
            }, status=500)

    def _parse_positive_int(self, value):
        value = self._to_english_digits(value)
        try:
            number = int(value)
            return number if number > 0 else None
        except (TypeError, ValueError):
            return None

    def _to_english_digits(self, value):
        if not value:
            return ''
        value = str(value)
        translation_table = str.maketrans(
            '۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩',
            '01234567890123456789'
        )
        return value.translate(translation_table).replace(',', '').strip()

    def _parse_date(self, value):
        """
        تلاش برای parse تاریخ:
        - yyyy-mm-dd
        - yyyy/mm/dd
        - تاریخ شمسی با کمک jdatetime
        """
        value = self._to_english_digits(value)

        for fmt in ('%Y-%m-%d', '%Y/%m/%d'):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                pass

        # تلاش برای parse جلالی
        for sep in ['-', '/']:
            try:
                parts = value.split(sep)
                if len(parts) == 3:
                    jy, jm, jd = map(int, parts)
                    return jdatetime.date(jy, jm, jd).togregorian()
            except Exception:
                pass

        return None

    def _format_date(self, date_obj, original_input=''):
        """
        اگر ورودی کاربر شمسی بوده، خروجی را هم شمسی بده.
        اگر میلادی بوده، خروجی را میلادی بده.
        """
        original_input = self._to_english_digits(original_input)

        if '/' in original_input or self._looks_like_jalali(original_input):
            try:
                j_date = jdatetime.date.fromgregorian(date=date_obj)
                return f"{j_date.year:04d}/{j_date.month:02d}/{j_date.day:02d}"
            except Exception:
                pass

        return date_obj.strftime('%Y-%m-%d')

    def _looks_like_jalali(self, value):
        """
        تشخیص تقریبی اینکه تاریخ احتمالاً جلالی است.
        مثال: 1405-03-24
        """
        try:
            year = int(value.split('-')[0])
            return 1300 <= year <= 1600
        except Exception:
            return False
