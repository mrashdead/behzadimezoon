from django.db.models import Count, Sum, Case, When, Value, BigIntegerField

from financial.models import Transaction
from financial.services.reconciliation_service import ReconciliationService
from reservations.constants import ReservationStatus
from reservations.models import Reservation
import datetime


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
    def _get_transaction_totals_by_reservation():
        transaction_rows = (
            Transaction.objects.filter(
                reservation__status__in=DashboardService.ACTIVE_STATUSES,
                reservation__isnull=False,
            )
            .values('reservation')
            .annotate(
                total_deposit=Sum(Case(When(type=Transaction.Type.DEPOSIT, then='amount'), default=Value(0), output_field=BigIntegerField())),
                total_final_payment=Sum(Case(When(type=Transaction.Type.FINAL_PAYMENT, then='amount'), default=Value(0), output_field=BigIntegerField())),
                total_damage_payment=Sum(Case(When(type=Transaction.Type.DAMAGE_PAYMENT, then='amount'), default=Value(0), output_field=BigIntegerField())),
                total_refund=Sum(Case(When(type=Transaction.Type.REFUND, then='amount'), default=Value(0), output_field=BigIntegerField())),
                total_discount=Sum(Case(When(type=Transaction.Type.DISCOUNT, then='amount'), default=Value(0), output_field=BigIntegerField())),
                total_damage_charge=Sum(Case(When(type=Transaction.Type.DAMAGE_CHARGE, then='amount'), default=Value(0), output_field=BigIntegerField())),
                total_cancellation_fee=Sum(Case(When(type=Transaction.Type.CANCELLATION_FEE, then='amount'), default=Value(0), output_field=BigIntegerField())),
                total_adjustment=Sum(Case(When(type=Transaction.Type.ADJUSTMENT, then='amount'), default=Value(0), output_field=BigIntegerField())),
            )
        )
        return {row['reservation']: row for row in transaction_rows}

    @staticmethod
    def _prefer_transaction_value(transaction_value, reservation_value):
        if transaction_value is not None:
            return transaction_value
        return reservation_value or 0

    @staticmethod
    def get_financial_context(filters=None):
        filters = filters or {}

        active_qs = Reservation.objects.exclude(
            status__in=[ReservationStatus.CANCELLED, ReservationStatus.ARCHIVED]
        )

        # apply seller filter
        seller_id = filters.get('seller_id') if filters else None
        if seller_id:
            active_qs = active_qs.filter(created_by_id=seller_id)

        # apply date range filter (expects YYYY-MM-DD strings)
        date_from = filters.get('date_from') if filters else None
        date_to = filters.get('date_to') if filters else None
        try:
            if date_from:
                df = datetime.date.fromisoformat(date_from)
                active_qs = active_qs.filter(start_date__gte=df)
            if date_to:
                dt = datetime.date.fromisoformat(date_to)
                active_qs = active_qs.filter(start_date__lte=dt)
        except Exception:
            # ignore invalid date filters
            pass

        # if ledger_mode toggle is provided we still compute by checking transactions
        transaction_totals_by_reservation = DashboardService._get_transaction_totals_by_reservation()
        uses_transaction_ledger = bool(transaction_totals_by_reservation)

        legacy_totals = active_qs.aggregate(
            total_gross_rent=Sum('rent_price'),
            total_discounts=Sum('discount_amount'),
            total_revenue=Sum('final_price'),
            total_deposit=Sum('deposit_amount'),
            total_remaining=Sum('remaining_amount'),
            total_damage_received=Sum('damage_amount'),
            total_refunded=Sum('refunded_amount'),
            total_remaining_paid=Sum('remaining_payment_amount'),
        )

        if uses_transaction_ledger:
            total_gross_rent = legacy_totals.get('total_gross_rent') or 0
            active_totals = {
                'total_revenue': 0,
                'total_gross_rent': total_gross_rent,
                'total_discounts': 0,
                'total_deposit': 0,
                'total_remaining': 0,
                'total_damage_received': 0,
                'total_refunded': 0,
                'total_remaining_paid': 0,
                'total_cash_inflow': 0,
            }

            reservation_values = active_qs.values(
                'pk',
                'final_price',
                'deposit_amount',
                'remaining_payment_amount',
                'refunded_amount',
                'discount_amount'
            )

            for reservation in reservation_values:
                tx_totals = transaction_totals_by_reservation.get(reservation['pk'])
                deposit = DashboardService._prefer_transaction_value(
                    tx_totals.get('total_deposit') if tx_totals else None,
                    reservation.get('deposit_amount')
                )
                final_payment = DashboardService._prefer_transaction_value(
                    tx_totals.get('total_final_payment') if tx_totals else None,
                    reservation.get('remaining_payment_amount')
                )
                damage_payment = (tx_totals.get('total_damage_payment') if tx_totals else 0) or 0
                refund = DashboardService._prefer_transaction_value(
                    tx_totals.get('total_refund') if tx_totals else None,
                    reservation.get('refunded_amount')
                )
                discount = DashboardService._prefer_transaction_value(
                    tx_totals.get('total_discount') if tx_totals else None,
                    reservation.get('discount_amount')
                )

                active_totals['total_revenue'] += deposit + final_payment
                active_totals['total_discounts'] += discount
                active_totals['total_deposit'] += deposit
                active_totals['total_remaining_paid'] += final_payment
                active_totals['total_damage_received'] += damage_payment
                active_totals['total_refunded'] += refund
                active_totals['total_cash_inflow'] += deposit + final_payment + damage_payment - refund
                active_totals['total_remaining'] += max((reservation.get('final_price') or 0) - (deposit + final_payment), 0)
        else:
            active_totals = legacy_totals
            active_totals['total_cash_inflow'] = (
                (legacy_totals.get('total_deposit') or 0)
                + (legacy_totals.get('total_remaining_paid') or 0)
                - (legacy_totals.get('total_refunded') or 0)
            )

        cancelled_reservations = Reservation.objects.filter(status=ReservationStatus.CANCELLED)
        cancelled_totals = cancelled_reservations.aggregate(
            total_cancelled_reservations=Count('id'),
            cancelled_received_amount=Sum('deposit_amount'),
            cancelled_damage_received=Sum('damage_amount'),
            cancelled_refunded_amount=Sum('refunded_amount'),
        )

        recent_reservations = (
            active_qs.select_related('customer', 'dress', 'created_by')
            .order_by('-created_at')[:50]
        )

        recent_transactions = (
            Transaction.objects.select_related('reservation', 'created_by')
            .order_by('-transaction_date')[:10]
        )

        return {
            'totals': {
                'total_reservations': active_qs.count(),
                'total_revenue': active_totals.get('total_revenue') or 0,
                'total_gross_rent': active_totals.get('total_gross_rent') or 0,
                'total_discounts': active_totals.get('total_discounts') or 0,
                'total_deposit': active_totals.get('total_deposit') or 0,
                'total_remaining': active_totals.get('total_remaining') if active_totals.get('total_remaining') is not None else (legacy_totals.get('total_remaining') or 0),
                'total_damage_received': active_totals.get('total_damage_received') or 0,
                'total_cash_inflow': active_totals.get('total_cash_inflow') or 0,
                'total_refunded': active_totals.get('total_refunded') or 0,
            },
            'cancelled_totals': {
                'total_cancelled_reservations': cancelled_totals.get('total_cancelled_reservations') or 0,
                'cancelled_received_amount': cancelled_totals.get('cancelled_received_amount') or 0,
                'cancelled_damage_received': cancelled_totals.get('cancelled_damage_received') or 0,
                'cancelled_refunded_amount': cancelled_totals.get('cancelled_refunded_amount') or 0,
            },
            'recent_reservations': recent_reservations,
            'recent_transactions': recent_transactions,
            'uses_transaction_ledger': uses_transaction_ledger,
            'open_reconciliation_issues': len(ReconciliationService.get_open_problem_reservations()),
        }
