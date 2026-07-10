from datetime import date, datetime, timedelta
from urllib.parse import urlencode
import jdatetime

from django.contrib.auth.decorators import login_required
from django.db.models import Case, Count, IntegerField, Q, Sum, When
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView

from accounts.models import User
from customers.models import Customer
from financial.models import CancellationRecord, DamageRecord, Transaction
from financial.services.dashboard_service import DashboardService
from products.models import Dress
from reservations.constants import PaymentMethod, ReservationStatus
from reservations.models import AdditionalFee, Reservation
from reservations.utils import parse_reservation_date


@method_decorator(login_required, name='dispatch')
class ReportsIndexView(TemplateView):
    template_name = 'reports/index.html'

    def _parse_date(self, value):
        if not value:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        parsed = parse_reservation_date(value)
        if parsed:
            return parsed
        try:
            return date.fromisoformat(str(value))
        except ValueError:
            return None

    def _gregorian_to_jalali(self, gregorian_date):
        """Convert Gregorian date to Jalali date string (YYYY/MM/DD format)"""
        if not gregorian_date:
            return ''
        try:
            j_date = jdatetime.date.fromgregorian(date=gregorian_date)
            return j_date.strftime('%Y/%m/%d')
        except Exception:
            return ''

    def _build_filter_url(self, override_params=None):
        params = {key: value for key, value in self.request.GET.items() if value}
        if override_params:
            params.update({key: value for key, value in override_params.items() if value not in (None, '')})
        if not params:
            return self.request.path
        return f"{self.request.path}?{urlencode(params)}"

    def _apply_filters(self, queryset, filters, *, date_field='start_date', field_overrides=None):
        if not queryset:
            return queryset
        field_overrides = field_overrides or {}
        if filters.get('seller_id'):
            seller_field = field_overrides.get('seller_id', 'created_by_id')
            queryset = queryset.filter(**{seller_field: filters['seller_id']})
        if filters.get('customer_id'):
            customer_field = field_overrides.get('customer_id', 'customer_id')
            queryset = queryset.filter(**{customer_field: filters['customer_id']})
        if filters.get('dress_id'):
            dress_field = field_overrides.get('dress_id', 'dress_id')
            queryset = queryset.filter(**{dress_field: filters['dress_id']})
        if filters.get('status'):
            status_field = field_overrides.get('status', 'status')
            queryset = queryset.filter(**{status_field: filters['status']})
        if filters.get('payment_method'):
            payment_field = field_overrides.get('payment_method', 'payment_method')
            queryset = queryset.filter(**{payment_field: filters['payment_method']})
        date_from = filters.get('date_from')
        date_to = filters.get('date_to')
        if date_from:
            queryset = queryset.filter(**{f'{date_field}__gte': date_from})
        if date_to:
            queryset = queryset.filter(**{f'{date_field}__lte': date_to})
        return queryset

    def _active_filter_labels(self, filters, selected_seller, selected_customer, selected_dress):
        labels = []
        if filters.get('date_from'):
            labels.append(f"از {filters['date_from'].strftime('%Y/%m/%d')}")
        if filters.get('date_to'):
            labels.append(f"تا {filters['date_to'].strftime('%Y/%m/%d')}")
        if selected_seller:
            labels.append(f"فروشنده: {selected_seller}")
        if selected_customer:
            labels.append(f"مشتری: {selected_customer}")
        if selected_dress:
            labels.append(f"لباس: {selected_dress}")
        if filters.get('status'):
            labels.append(f"وضعیت: {dict(ReservationStatus.CHOICES).get(filters['status'], filters['status'])}")
        if filters.get('payment_method'):
            labels.append(f"پرداخت: {dict(PaymentMethod.CHOICES).get(filters['payment_method'], filters['payment_method'])}")
        return labels

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request
        today = timezone.localdate()

        date_from = self._parse_date(request.GET.get('date_from'))
        date_to = self._parse_date(request.GET.get('date_to'))
        if not date_from:
            date_from = today - timedelta(days=7)
        if not date_to:
            date_to = today

        filters = {
            'date_from': date_from,
            'date_to': date_to,
            'seller_id': request.GET.get('seller_id') or '',
            'customer_id': request.GET.get('customer_id') or '',
            'dress_id': request.GET.get('dress_id') or '',
            'status': request.GET.get('status') or '',
            'payment_method': request.GET.get('payment_method') or '',
        }

        reservation_qs = self._apply_filters(Reservation.objects.filter(is_deleted=False), filters)
        transaction_qs = self._apply_filters(
            Transaction.objects.filter(transaction_status=Transaction.TransactionStatus.POSTED, is_voided=False),
            filters,
            date_field='transaction_date',
            field_overrides={
                'seller_id': 'reservation__created_by_id',
                'customer_id': 'reservation__customer_id',
                'dress_id': 'reservation__dress_id',
                'status': 'reservation__status',
                'payment_method': 'reservation__payment_method',
            },
        )

        active_statuses = [
            ReservationStatus.CONFIRMED,
            ReservationStatus.DELIVERED,
            ReservationStatus.RETURNED,
            ReservationStatus.LAUNDRY,
            ReservationStatus.READY,
        ]

        month_revenue = reservation_qs.aggregate(total=Sum('final_price'))['total'] or 0
        active_reservations = reservation_qs.filter(status__in=active_statuses).count()
        cancelled_reservations = reservation_qs.filter(status=ReservationStatus.CANCELLED).count()
        refund_cases = transaction_qs.filter(transaction_type=Transaction.TransactionType.REFUND).count()
        refund_amount = transaction_qs.filter(transaction_type=Transaction.TransactionType.REFUND).aggregate(total=Sum('amount'))['total'] or 0
        damage_penalty_total = (
            reservation_qs.aggregate(total_damage=Sum('damage_amount'))['total_damage'] or 0
        ) + (
            reservation_qs.aggregate(total_penalty=Sum('cancellation_fee'))['total_penalty'] or 0
        )

        top_dress = reservation_qs.values('dress__code').annotate(
            total_revenue=Sum('final_price'),
            reservation_count=Count('id'),
        ).order_by('-total_revenue').first()
        top_customer = reservation_qs.values(
            'customer__pk', 'customer__bride_first_name', 'customer__bride_last_name'
        ).annotate(
            total_revenue=Sum('final_price'),
            reservation_count=Count('id'),
        ).order_by('-total_revenue').first()

        cash_inflow = transaction_qs.filter(
            transaction_type__in=[
                Transaction.TransactionType.DEPOSIT,
                Transaction.TransactionType.FINAL_PAYMENT,
                Transaction.TransactionType.PARTIAL_PAYMENT,
                Transaction.TransactionType.DAMAGE_PAYMENT,
                Transaction.TransactionType.PENALTY_INCOME,
                Transaction.TransactionType.TRANSFER_IN,
                Transaction.TransactionType.ADJUSTMENT_IN,
            ]
        ).aggregate(total=Sum('amount'))['total'] or 0
        cancellation_fee_income = transaction_qs.filter(transaction_type=Transaction.TransactionType.CANCELLATION_FEE).aggregate(total=Sum('amount'))['total'] or 0
        damage_income = transaction_qs.filter(transaction_type=Transaction.TransactionType.DAMAGE_PAYMENT).aggregate(total=Sum('amount'))['total'] or 0
        refund_total = transaction_qs.filter(transaction_type=Transaction.TransactionType.REFUND).aggregate(total=Sum('amount'))['total'] or 0
        outstanding_total = reservation_qs.aggregate(total=Sum('remaining_amount'))['total'] or 0
        additional_fee_total = AdditionalFee.objects.filter(is_deleted=False, reservation__in=reservation_qs).aggregate(total=Sum('amount'))['total'] or 0
        adjustment_total = transaction_qs.filter(
            transaction_type__in=[Transaction.TransactionType.DISCOUNT, Transaction.TransactionType.ADJUSTMENT_IN, Transaction.TransactionType.ADJUSTMENT_OUT]
        ).aggregate(total=Sum('amount'))['total'] or 0

        repeat_customers = reservation_qs.values(
            'customer__pk', 'customer__bride_first_name', 'customer__bride_last_name'
        ).annotate(
            reservation_count=Count('id'),
            total_revenue=Sum('final_price'),
        ).order_by('-reservation_count', '-total_revenue')[:8]

        top_dresses = reservation_qs.values('dress__pk', 'dress__code').annotate(
            reservation_count=Count('id'),
            total_revenue=Sum('final_price'),
        ).order_by('-total_revenue')[:8]

        seller_rows = reservation_qs.values('created_by__id', 'created_by__username').annotate(
            reservation_count=Count('id'),
            total_revenue=Sum('final_price'),
            cancelled_count=Sum(Case(When(status=ReservationStatus.CANCELLED, then=1), default=0, output_field=IntegerField())),
            damage_total=Sum('damage_amount'),
        ).order_by('-total_revenue', '-reservation_count')[:8]

        damage_records = DamageRecord.objects.filter(reservation__in=reservation_qs).select_related('customer', 'dress').order_by('-amount')[:6]
        cancellation_records = CancellationRecord.objects.filter(reservation__in=reservation_qs).select_related('reservation').order_by('-penalty_amount')[:6]
        cancellation_total = cancellation_records.count()
        damage_total_amount = damage_records.aggregate(total=Sum('amount'))['total'] or 0

        trend_days = 14
        if date_from and date_to:
            span = (date_to - date_from).days + 1
            trend_days = max(7, min(30, span))

        labels = []
        revenue_series = []
        reservation_series = []
        current_day = date_to
        for offset in range(trend_days):
            day = current_day - timedelta(days=trend_days - 1 - offset)
            labels.append(day.strftime('%Y/%m/%d'))
            day_reservations = reservation_qs.filter(start_date=day)
            revenue_series.append(day_reservations.aggregate(total=Sum('final_price'))['total'] or 0)
            reservation_series.append(day_reservations.count())

        previous_start = date_from - timedelta(days=max(1, trend_days))
        previous_end = date_from - timedelta(days=1)
        previous_reservations = Reservation.objects.filter(
            is_deleted=False,
            start_date__gte=previous_start,
            start_date__lte=previous_end,
        )
        if filters.get('seller_id'):
            previous_reservations = previous_reservations.filter(created_by_id=filters['seller_id'])
        if filters.get('customer_id'):
            previous_reservations = previous_reservations.filter(customer_id=filters['customer_id'])
        if filters.get('dress_id'):
            previous_reservations = previous_reservations.filter(dress_id=filters['dress_id'])
        if filters.get('status'):
            previous_reservations = previous_reservations.filter(status=filters['status'])
        if filters.get('payment_method'):
            previous_reservations = previous_reservations.filter(payment_method=filters['payment_method'])
        previous_cancelled = previous_reservations.filter(status=ReservationStatus.CANCELLED).count()
        current_cancelled = cancelled_reservations
        if current_cancelled > previous_cancelled:
            cancellation_trend = 'در حال افزایش است'
        else:
            cancellation_trend = 'پایدار یا کاهشی'

        previous_damage = previous_reservations.aggregate(total=Sum('damage_amount'))['total'] or 0
        current_damage = damage_penalty_total
        if current_damage > previous_damage:
            damage_trend = 'در حال افزایش است'
        else:
            damage_trend = 'پایدار یا کاهشی'

        selected_seller = User.objects.filter(pk=filters['seller_id']).first() if filters.get('seller_id') else None
        selected_customer = Customer.objects.filter(pk=filters['customer_id']).first() if filters.get('customer_id') else None
        selected_dress = Dress.objects.filter(pk=filters['dress_id']).first() if filters.get('dress_id') else None

        context['page_title'] = 'گزارش‌های عملیاتی'
        context['filters'] = filters
        context['date_from_value'] = request.GET.get('date_from') or self._gregorian_to_jalali(date_from)
        context['date_to_value'] = request.GET.get('date_to') or self._gregorian_to_jalali(date_to)
        context['active_filter_labels'] = self._active_filter_labels(filters, selected_seller, selected_customer, selected_dress)
        context['date_presets'] = [
            {'label': 'امروز', 'url': self._build_filter_url({'date_from': today.strftime('%Y-%m-%d'), 'date_to': today.strftime('%Y-%m-%d')})},
            {'label': 'این هفته', 'url': self._build_filter_url({'date_from': (today - timedelta(days=6)).strftime('%Y-%m-%d'), 'date_to': today.strftime('%Y-%m-%d')})},
            {'label': 'این ماه', 'url': self._build_filter_url({'date_from': today.replace(day=1).strftime('%Y-%m-%d'), 'date_to': today.strftime('%Y-%m-%d')})},
            {'label': '۳ ماه اخیر', 'url': self._build_filter_url({'date_from': (today.replace(year=today.year if today.month > 3 else today.year - 1, month=today.month - 3 if today.month > 3 else today.month + 9)).strftime('%Y-%m-%d'), 'date_to': today.strftime('%Y-%m-%d')})},
            {'label': 'سال جاری', 'url': self._build_filter_url({'date_from': date(today.year, 1, 1).strftime('%Y-%m-%d'), 'date_to': today.strftime('%Y-%m-%d')})},
        ]
        context['reset_url'] = self.request.path
        context['sellers'] = User.objects.filter(is_active=True).order_by('username')
        context['customers'] = Customer.objects.order_by('bride_last_name', 'bride_first_name')[:200]
        context['dresses'] = Dress.objects.order_by('code')[:200]
        context['statuses'] = ReservationStatus.CHOICES
        context['payment_methods'] = PaymentMethod.CHOICES
        top_customer_label = '—'
        if top_customer:
            top_customer_label = f"{top_customer.get('customer__bride_first_name', '')} {top_customer.get('customer__bride_last_name', '')}".strip() or '—'

        context['summary'] = {
            'month_revenue': month_revenue,
            'active_reservations': active_reservations,
            'cancelled_reservations': cancelled_reservations,
            'refund_cases': refund_cases,
            'refund_amount': refund_amount,
            'damage_penalty_total': damage_penalty_total,
            'top_dress_label': f"{top_dress['dress__code']}" if top_dress else '—',
            'top_customer_label': top_customer_label,
            'period_label': f"{date_from.strftime('%Y/%m/%d')} تا {date_to.strftime('%Y/%m/%d')}",
        }
        context['financial_rows'] = [
            {'label': 'درآمد خالص از رزروها', 'value': month_revenue, 'hint': 'جمع مبلغ نهایی رزروها'},
            {'label': 'درآمد جریمه لغو', 'value': cancellation_fee_income, 'hint': 'تراکنش‌های ثبت‌شده جریمه لغو'},
            {'label': 'درآمد خسارت', 'value': damage_income, 'hint': 'دریافت خسارت از رزروها'},
            {'label': 'مجموع دریافتی‌ها', 'value': cash_inflow, 'hint': 'بیعانه + پرداخت‌های تکمیلی'},
            {'label': 'بازپرداخت‌ها', 'value': refund_total, 'hint': 'مبلغ بازپرداخت ثبت‌شده'},
            {'label': 'مانده پرداخت‌ها', 'value': outstanding_total, 'hint': 'باقی‌مانده رزروهای فعال'},
            {'label': 'هزینه‌های جانبی', 'value': additional_fee_total, 'hint': 'جمع هزینه‌های جانبی رزروها'},
            {'label': 'تخفیف و تعدیل', 'value': adjustment_total, 'hint': 'تخفیف/تعدیل ثبت‌شده'},
        ]
        context['repeat_customers'] = repeat_customers
        context['top_dresses'] = top_dresses
        context['employee_rows'] = seller_rows
        context['damage_records'] = damage_records
        context['cancellation_records'] = cancellation_records
        context['trend_labels'] = labels
        context['trend_revenue'] = revenue_series
        context['trend_reservations'] = reservation_series
        context['analysis'] = {
            'cancellation_rate': round((cancelled_reservations / reservation_qs.count() * 100) if reservation_qs.count() else 0, 1),
            'cancellation_total': cancellation_total,
            'damage_total_amount': damage_total_amount,
            'cancellation_trend': cancellation_trend,
            'damage_trend': damage_trend,
            'avg_refund': round((refund_amount / refund_cases) if refund_cases else 0, 0),
            'avg_penalty': round((sum(record.penalty_amount or 0 for record in cancellation_records) / cancellation_total) if cancellation_total else 0, 0),
        }
        return context
