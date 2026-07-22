# financial/services/dashboard_service.py

from django.db.models import Count, Q, Sum, Case, When, Value, BigIntegerField, F
from django.utils import timezone
import datetime


def _coerce_date_filter(value):
    if not value:
        return None
    if isinstance(value, datetime.datetime):
        if timezone.is_aware(value):
            return value
        return timezone.make_aware(value, timezone.get_current_timezone())
    if isinstance(value, datetime.date):
        naive_dt = datetime.datetime.combine(value, datetime.time.min)
        return timezone.make_aware(naive_dt, timezone.get_current_timezone())
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        parsed = parse_reservation_date(value)
        if parsed:
            naive_dt = datetime.datetime.combine(parsed, datetime.time.min)
            return timezone.make_aware(naive_dt, timezone.get_current_timezone())
    return None


def _coerce_date_range(filters):
    if not filters:
        return None, None
    date_from = _coerce_date_filter(filters.get('date_from'))
    date_to = _coerce_date_filter(filters.get('date_to'))
    if date_from and date_to and date_from > date_to:
        date_from, date_to = date_to, date_from
    return date_from, date_to

from financial.models import Transaction, DamageRecord, Guarantee, CancellationRecord, FinancialAccount, TransactionCategory
from reservations.constants import ReservationStatus
from reservations.models import AdditionalFee, Reservation
from reservations.utils import parse_reservation_date

class DashboardService:
    ACTIVE_STATUSES = [
        ReservationStatus.DRAFT,
        ReservationStatus.CONFIRMED,
        ReservationStatus.DELIVERED,
        ReservationStatus.RETURNED,
        ReservationStatus.LAUNDRY,
        ReservationStatus.READY,
    ]

    @staticmethod
    def _parse_filter_date(value):
        if not value:
            return None
        if isinstance(value, datetime.datetime):
            if timezone.is_aware(value):
                return value.date()
            return timezone.make_aware(value, timezone.get_current_timezone()).date()
        if isinstance(value, datetime.date):
            return value
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            try:
                return parse_reservation_date(value)
            except Exception:
                try:
                    return datetime.date.fromisoformat(value)
                except Exception:
                    return None
        return None

    @staticmethod
    def _apply_seller_filter(queryset, seller_id):
        if not seller_id:
            return queryset
        try:
            seller_id = int(seller_id)
        except (TypeError, ValueError):
            return queryset
        return queryset.filter(created_by_id=seller_id)

    @staticmethod
    def _apply_reservation_filters(queryset, filters):
        if not filters:
            return queryset

        queryset = DashboardService._apply_seller_filter(queryset, filters.get('seller_id'))

        date_from = DashboardService._parse_filter_date(filters.get('date_from'))
        date_to = DashboardService._parse_filter_date(filters.get('date_to'))
        if date_from:
            queryset = queryset.filter(start_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(start_date__lte=date_to)

        return queryset

    @staticmethod
    def _apply_related_transaction_filters(queryset, filters):
        if not filters:
            return queryset

        queryset = DashboardService._apply_seller_filter(queryset, filters.get('seller_id'))

        date_from, date_to = _coerce_date_range(filters)
        if date_from:
            queryset = queryset.filter(transaction_date__gte=date_from)
        if date_to:
            end_of_day = date_to + datetime.timedelta(days=1)
            queryset = queryset.filter(transaction_date__lt=end_of_day)

        return queryset

    @staticmethod
    def _income_transaction_types():
        return [
            Transaction.TransactionType.DEPOSIT,
            Transaction.TransactionType.FINAL_PAYMENT,
            Transaction.TransactionType.PARTIAL_PAYMENT,
            Transaction.TransactionType.PAYMENT,
            Transaction.TransactionType.DAMAGE_PAYMENT,
            Transaction.TransactionType.PENALTY_INCOME,
            Transaction.TransactionType.TRANSFER_IN,
            Transaction.TransactionType.ADJUSTMENT_IN,
        ]

    @staticmethod
    def _expense_transaction_types():
        return [
            Transaction.TransactionType.LAUNDRY_EXPENSE,
            Transaction.TransactionType.REPAIR_EXPENSE,
            Transaction.TransactionType.SUPPLY_EXPENSE,
            Transaction.TransactionType.UTILITY_EXPENSE,
            Transaction.TransactionType.STAFF_SALARY,
            Transaction.TransactionType.RENT_EXPENSE,
            Transaction.TransactionType.MARKETING_EXPENSE,
            Transaction.TransactionType.TRANSFER_OUT,
            Transaction.TransactionType.ADJUSTMENT_OUT,
        ]

    @staticmethod
    def _get_transaction_totals_by_reservation(filters=None):
        filters = filters or {}
        qs = Transaction.objects.filter(
            reservation__status__in=DashboardService.ACTIVE_STATUSES,
            reservation__is_deleted=False,
            reservation__isnull=False,
            transaction_status=Transaction.TransactionStatus.POSTED, # Only posted transactions
            is_voided=False
        )
        seller_id = filters.get('seller_id')
        if seller_id:
            qs = qs.filter(reservation__created_by_id=seller_id)

        transaction_rows = (
            qs.values('reservation')
            .annotate(
                total_deposit=Sum(Case(When(transaction_type=Transaction.TransactionType.DEPOSIT, then='amount'), default=Value(0), output_field=BigIntegerField())),
                total_final_payment=Sum(Case(When(transaction_type=Transaction.TransactionType.FINAL_PAYMENT, then='amount'), default=Value(0), output_field=BigIntegerField())),
                total_partial_payment=Sum(Case(When(transaction_type=Transaction.TransactionType.PARTIAL_PAYMENT, then='amount'), default=Value(0), output_field=BigIntegerField())),
                total_damage_payment=Sum(Case(When(transaction_type=Transaction.TransactionType.DAMAGE_PAYMENT, then='amount'), default=Value(0), output_field=BigIntegerField())),
                total_refund=Sum(Case(When(transaction_type=Transaction.TransactionType.REFUND, then='amount'), default=Value(0), output_field=BigIntegerField())),
                total_discount=Sum(Case(When(transaction_type=Transaction.TransactionType.DISCOUNT, then='amount'), default=Value(0), output_field=BigIntegerField())),
                total_damage_charge=Sum(Case(When(transaction_type=Transaction.TransactionType.DAMAGE_CHARGE, then='amount'), default=Value(0), output_field=BigIntegerField())),
                total_cancellation_fee=Sum(Case(When(transaction_type=Transaction.TransactionType.CANCELLATION_FEE, then='amount'), default=Value(0), output_field=BigIntegerField())),
                total_adjustment_in=Sum(Case(When(transaction_type=Transaction.TransactionType.ADJUSTMENT_IN, then='amount'), default=Value(0), output_field=BigIntegerField())),
                total_adjustment_out=Sum(Case(When(transaction_type=Transaction.TransactionType.ADJUSTMENT_OUT, then='amount'), default=Value(0), output_field=BigIntegerField())),
                total_payment=Sum(Case(When(transaction_type=Transaction.TransactionType.PAYMENT, then='amount'), default=Value(0), output_field=BigIntegerField())), # Legacy PAYMENT type
            )
        )
        return {row['reservation']: row for row in transaction_rows}

    @staticmethod
    def _prefer_transaction_value(transaction_value, reservation_value):
        if transaction_value is not None:
            return transaction_value
        return reservation_value or 0

    @staticmethod
    def _build_damage_breakdown(filters=None):
        damage_qs = DashboardService._apply_related_transaction_filters(DamageRecord.objects.all(), filters or {})
        damage_rows = (
            damage_qs
            .values(
                'customer__pk',
                'customer__bride_first_name',
                'customer__bride_last_name',
                'dress__pk',
                'dress__code',
            )
            .annotate(
                total_damage=Sum('amount'),
                record_count=Count('id'),
            )
            .order_by('-total_damage')[:10]
        )

        return [
            {
                'customer_name': f"{row.get('customer__bride_first_name') or ''} {row.get('customer__bride_last_name') or ''}".strip() or '-',
                'product_code': row.get('dress__code') or '-',
                'total_damage': row.get('total_damage') or 0,
                'record_count': row.get('record_count') or 0,
            }
            for row in damage_rows
        ]

    @staticmethod
    def _build_guarantee_summary(filters=None):
        guarantee_qs = DashboardService._apply_related_transaction_filters(Guarantee.objects.all(), filters or {})
        guarantee_totals = guarantee_qs.aggregate(
            total_guarantees=Count('id'),
            active_guarantees=Count('id', filter=Q(status=Guarantee.RECEIVED)),
            returned_guarantees=Count('id', filter=Q(status=Guarantee.RETURNED)),
            forfeited_guarantees=Count('id', filter=Q(status=Guarantee.FORFEITED)),
            total_estimated_value=Sum('estimated_value'),
        )
        guarantee_preview = guarantee_qs.select_related('reservation', 'customer', 'dress').order_by('-received_at')[:8]

        return {
            'summary': {
                'total_guarantees': guarantee_totals.get('total_guarantees') or 0,
                'active_guarantees': guarantee_totals.get('active_guarantees') or 0,
                'returned_guarantees': guarantee_totals.get('returned_guarantees') or 0,
                'forfeited_guarantees': guarantee_totals.get('forfeited_guarantees') or 0,
                'estimated_value': guarantee_totals.get('total_estimated_value') or 0,
            },
            'preview': guarantee_preview,
        }

    @staticmethod
    def _build_cancellation_report(filters=None):
        cancellation_qs = DashboardService._apply_related_transaction_filters(CancellationRecord.objects.all(), filters or {})
        totals = cancellation_qs.aggregate(
            total_cancellations=Count('id'),
            total_deposit_at_cancel=Sum('deposit_at_cancel'),
            total_refund_amount=Sum('refund_amount'),
            total_penalty_amount=Sum('penalty_amount'),
        )
        return {
            'total_cancellations': totals.get('total_cancellations') or 0,
            'total_deposit_at_cancel': totals.get('total_deposit_at_cancel') or 0,
            'total_refund_amount': totals.get('total_refund_amount') or 0,
            'total_penalty_amount': totals.get('total_penalty_amount') or 0,
        }

    @staticmethod
    def _build_damage_report(filters=None, transaction_totals=None):
        damage_qs = DashboardService._apply_related_transaction_filters(DamageRecord.objects.all(), filters or {})
        damage_totals = damage_qs.aggregate(
            total_damage_amount=Sum('amount'),
            total_damage_collected=Sum(Case(When(collected=True, then='amount'), default=Value(0), output_field=BigIntegerField())),
            total_damage_outstanding=Sum(Case(When(collected=False, then='amount'), default=Value(0), output_field=BigIntegerField())),
        )

        # Prefer transaction-based totals for financial accuracy if available
        if transaction_totals is not None:
            damage_charge = transaction_totals.get('total_damage_charge') or 0
            damage_payment = transaction_totals.get('total_damage_payment') or 0
        else:
            damage_charge = damage_totals.get('total_damage_amount') or 0
            damage_payment = damage_totals.get('total_damage_collected') or 0

        return {
            'total_damage_charge': damage_charge,
            'total_damage_paid': damage_payment,
            'total_damage_outstanding': damage_totals.get('total_damage_outstanding') or 0,
            'breakdown': DashboardService._build_damage_breakdown(filters),
        }

    @staticmethod
    def get_financial_context(filters=None):
        filters = filters or {}

        # This will be based on the FinancialAccount balances if possible
        cash_account = FinancialAccount.objects.filter(account_type=FinancialAccount.AccountType.CASH).first()
        total_cash_balance = cash_account.balance if cash_account else 0

        # Overall revenue and expenses from all posted transactions
        all_posted_transactions = DashboardService._apply_related_transaction_filters(
            Transaction.objects.filter(
                transaction_status=Transaction.TransactionStatus.POSTED,
                is_voided=False
            ),
            filters,
        )

        total_revenue = all_posted_transactions.filter(
            transaction_type__in=DashboardService._income_transaction_types()
        ).aggregate(total=Sum('amount'))['total'] or 0

        total_expenses = all_posted_transactions.filter(
            transaction_type__in=DashboardService._expense_transaction_types()
        ).aggregate(total=Sum('amount'))['total'] or 0

        net_profit = total_revenue - total_expenses

        today = timezone.localdate()
        start_of_today = timezone.make_aware(datetime.datetime(today.year, today.month, today.day))
        end_of_today = start_of_today + datetime.timedelta(days=1)

        today_income_transactions = all_posted_transactions.filter(
            transaction_date__gte=start_of_today,
            transaction_date__lt=end_of_today,
            transaction_type__in=DashboardService._income_transaction_types(),
        )
        today_income = today_income_transactions.aggregate(total=Sum('amount'))['total'] or 0


        reservation_qs = DashboardService._apply_reservation_filters(Reservation.objects.filter(is_deleted=False), filters)

        # Payment Status Breakdown
        total_reservations = reservation_qs.count()
        paid_reservations = reservation_qs.filter(payment_status=Reservation.PAYMENT_PAID).count()
        partial_reservations = reservation_qs.filter(payment_status=Reservation.PAYMENT_PARTIAL).count()
        unpaid_reservations = reservation_qs.filter(payment_status=Reservation.PAYMENT_UNPAID).count()

        payment_stats = {
            'paid': paid_reservations,
            'partial': partial_reservations,
            'unpaid': unpaid_reservations,
            'total': total_reservations,
        }

        # Recent transactions
        recent_transactions = all_posted_transactions.select_related('reservation', 'customer').order_by('-transaction_date')[:10]

        # Upcoming payments (reservations with remaining amount)
        upcoming_payments = reservation_qs.filter(
            Q(payment_status=Reservation.PAYMENT_PARTIAL) | Q(payment_status=Reservation.PAYMENT_UNPAID)
        ).annotate(
            # Recalculate remaining amount for display consistency
            amount_remaining=F('final_price') - (F('deposit_amount') + F('remaining_payment_amount') - F('refunded_amount'))
        ).filter(amount_remaining__gt=0).select_related('customer', 'dress').order_by('start_date')[:5]


        # Placeholder for revenue trend data for chart
        # This would typically be generated by grouping transactions by date over a period
        chart_labels = []
        revenue_data = []
        expense_data = []

        # Example for last 30 days
        for i in range(30):
            date = today - datetime.timedelta(days=29 - i)
            start_d = timezone.make_aware(datetime.datetime(date.year, date.month, date.day))
            end_d = start_d + datetime.timedelta(days=1)

            daily_income = all_posted_transactions.filter(
                transaction_date__gte=start_d,
                transaction_date__lt=end_d,
                transaction_type__in=DashboardService._income_transaction_types(),
            ).aggregate(total=Sum('amount'))['total'] or 0

            daily_expense = all_posted_transactions.filter(
                transaction_date__gte=start_d,
                transaction_date__lt=end_d,
                transaction_type__in=DashboardService._expense_transaction_types(),
            ).aggregate(total=Sum('amount'))['total'] or 0

            chart_labels.append(date.strftime('%Y/%m/%d'))
            revenue_data.append(daily_income)
            expense_data.append(daily_expense)

        # Reservation aggregates
        active_reservations = reservation_qs
        cancelled_reservations = reservation_qs.filter(status=ReservationStatus.CANCELLED)

        cancelled_totals = cancelled_reservations.aggregate(
            total_cancelled_reservations=Count('id'),
            cancelled_received_amount=Sum('deposit_amount'),
            cancelled_damage_received=Sum('damage_amount'),
            cancelled_refunded_amount=Sum('refunded_amount'),
        )

        recent_reservations = active_reservations.order_by('-created_at')[:15]
        additional_fee_total = AdditionalFee.objects.filter(
            is_deleted=False,
            reservation__in=reservation_qs,
        ).aggregate(total=Sum('amount'))['total'] or 0
        uses_transaction_ledger = Transaction.objects.filter(
            transaction_status=Transaction.TransactionStatus.POSTED,
            is_voided=False,
        ).exists()

        if not uses_transaction_ledger:
            total_cash_inflow = active_reservations.aggregate(
                total=Sum(
                    F('deposit_amount') + F('remaining_payment_amount') - F('refunded_amount'),
                    output_field=BigIntegerField()
                )
            )['total'] or 0
            total_revenue = active_reservations.aggregate(
                total=Sum('final_price')
            )['total'] or 0
            total_deposit = active_reservations.aggregate(
                total=Sum('deposit_amount')
            )['total'] or 0
            total_remaining = active_reservations.aggregate(
                total=Sum('remaining_amount')
            )['total'] or 0
        else:
            total_cash_inflow = all_posted_transactions.filter(transaction_type__in=[
                Transaction.TransactionType.DEPOSIT,
                Transaction.TransactionType.FINAL_PAYMENT,
                Transaction.TransactionType.PARTIAL_PAYMENT,
                Transaction.TransactionType.DAMAGE_PAYMENT,
                Transaction.TransactionType.PENALTY_INCOME,
                Transaction.TransactionType.TRANSFER_IN,
                Transaction.TransactionType.ADJUSTMENT_IN,
            ]).aggregate(total=Sum('amount'))['total'] or 0
            total_deposit = all_posted_transactions.filter(transaction_type=Transaction.TransactionType.DEPOSIT).aggregate(total=Sum('amount'))['total'] or 0
            total_remaining = active_reservations.aggregate(total=Sum('remaining_amount'))['total'] or 0

        open_reconciliation_issues = 0
        try:
            from financial.services.reconciliation_service import ReconciliationService
            open_reconciliation_issues = len(ReconciliationService.get_open_problem_reservations(filters))
        except Exception:
            open_reconciliation_issues = 0

        return {
            'totals': {
                'total_revenue': total_revenue,
                'total_expenses': total_expenses,
                'net_profit': net_profit,
                'today_income': today_income,
                'today_transactions': today_income_transactions.count(),
                'total_cash_balance': total_cash_balance,
                'total_deposit': total_deposit,
                'total_remaining': total_remaining,
                'total_damage_received': (
                    all_posted_transactions.filter(transaction_type=Transaction.TransactionType.DAMAGE_PAYMENT).aggregate(total=Sum('amount'))['total'] or 0
                ) + (
                    all_posted_transactions.filter(transaction_type=Transaction.TransactionType.PENALTY_INCOME).aggregate(total=Sum('amount'))['total'] or 0
                ),
                'total_cash_inflow': total_cash_inflow,
                'total_refunded': all_posted_transactions.filter(transaction_type=Transaction.TransactionType.REFUND).aggregate(total=Sum('amount'))['total'] or 0,
                'total_additional_fee_revenue': additional_fee_total,
            },
            'cancelled_totals': {
                'total_cancelled_reservations': cancelled_totals.get('total_cancelled_reservations') or 0,
                'cancelled_received_amount': cancelled_totals.get('cancelled_received_amount') or 0,
                'cancelled_damage_received': cancelled_totals.get('cancelled_damage_received') or 0,
                'cancelled_refunded_amount': cancelled_totals.get('cancelled_refunded_amount') or 0,
            },
            'recent_reservations': recent_reservations,
            'uses_transaction_ledger': uses_transaction_ledger,
            'open_reconciliation_issues': open_reconciliation_issues,
            'reporting': {
                'reservation_summary': {
                    'total_gross_reservation_value': active_reservations.aggregate(total=Sum('rent_price'))['total'] or 0,
                }
            },
            'payment_stats': payment_stats,
            'recent_transactions': recent_transactions,
            'upcoming_payments': upcoming_payments,
            'chart_labels': chart_labels,
            'revenue_data': revenue_data,
            'expense_data': expense_data,
        }
