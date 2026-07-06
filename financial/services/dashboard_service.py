from django.db.models import Count, Q, Sum, Case, When, Value, BigIntegerField

from financial.models import Transaction, DamageRecord, Guarantee, CancellationRecord
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
    def _apply_reservation_filters(queryset, filters):
        if not filters:
            return queryset

        seller_id = filters.get('seller_id')
        if seller_id:
            queryset = queryset.filter(created_by_id=seller_id)

        date_from = filters.get('date_from')
        date_to = filters.get('date_to')
        try:
            if date_from:
                df = datetime.date.fromisoformat(date_from)
                queryset = queryset.filter(start_date__gte=df)
            if date_to:
                dt = datetime.date.fromisoformat(date_to)
                queryset = queryset.filter(start_date__lte=dt)
        except Exception:
            pass

        return queryset

    @staticmethod
    def _apply_related_reservation_filters(queryset, filters):
        if not filters:
            return queryset

        seller_id = filters.get('seller_id')
        if seller_id:
            queryset = queryset.filter(reservation__created_by_id=seller_id)

        date_from = filters.get('date_from')
        date_to = filters.get('date_to')
        try:
            if date_from:
                df = datetime.date.fromisoformat(date_from)
                queryset = queryset.filter(reservation__start_date__gte=df)
            if date_to:
                dt = datetime.date.fromisoformat(date_to)
                queryset = queryset.filter(reservation__start_date__lte=dt)
        except Exception:
            pass

        return queryset

    @staticmethod
    def _get_transaction_totals_by_reservation(filters=None):
        filters = filters or {}
        qs = Transaction.objects.filter(
            reservation__status__in=DashboardService.ACTIVE_STATUSES,
            reservation__isnull=False,
        )
        seller_id = filters.get('seller_id')
        if seller_id:
            qs = qs.filter(reservation__created_by_id=seller_id)

        transaction_rows = (
            qs.values('reservation')
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
    def _build_damage_breakdown(filters=None):
        damage_qs = DashboardService._apply_related_reservation_filters(DamageRecord.objects.all(), filters or {})
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
        guarantee_qs = DashboardService._apply_related_reservation_filters(Guarantee.objects.all(), filters or {})
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
        cancellation_qs = DashboardService._apply_related_reservation_filters(CancellationRecord.objects.all(), filters or {})
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
        damage_qs = DashboardService._apply_related_reservation_filters(DamageRecord.objects.all(), filters or {})
        damage_totals = damage_qs.aggregate(
            total_damage_amount=Sum('amount'),
            total_damage_collected=Sum(Case(When(collected=True, then='amount'), default=Value(0), output_field=BigIntegerField())),
            total_damage_outstanding=Sum(Case(When(collected=False, then='amount'), default=Value(0), output_field=BigIntegerField())),
        )

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

        active_qs = Reservation.objects.exclude(
            status__in=[ReservationStatus.CANCELLED, ReservationStatus.ARCHIVED]
        )
        active_qs = DashboardService._apply_reservation_filters(active_qs, filters)

        transaction_totals_by_reservation = DashboardService._get_transaction_totals_by_reservation(filters)
        uses_transaction_ledger = bool(transaction_totals_by_reservation)

        reservation_totals = active_qs.aggregate(
            total_gross_rent=Sum('rent_price'),
            total_discounts=Sum('discount_amount'),
            total_net_reservation_value=Sum('final_price'),
            total_deposit=Sum('deposit_amount'),
            total_remaining=Sum('remaining_amount'),
            total_refunded=Sum('refunded_amount'),
            total_remaining_paid=Sum('remaining_payment_amount'),
        )

        transaction_qs = Transaction.objects.filter(
            reservation__status__in=DashboardService.ACTIVE_STATUSES,
            reservation__isnull=False,
        )
        transaction_qs = DashboardService._apply_related_reservation_filters(transaction_qs, filters)

        transaction_totals = transaction_qs.aggregate(
            total_deposit=Sum(Case(When(type=Transaction.Type.DEPOSIT, then='amount'), default=Value(0), output_field=BigIntegerField())),
            total_final_payment=Sum(Case(When(type=Transaction.Type.FINAL_PAYMENT, then='amount'), default=Value(0), output_field=BigIntegerField())),
            total_damage_payment=Sum(Case(When(type=Transaction.Type.DAMAGE_PAYMENT, then='amount'), default=Value(0), output_field=BigIntegerField())),
            total_refund=Sum(Case(When(type=Transaction.Type.REFUND, then='amount'), default=Value(0), output_field=BigIntegerField())),
            total_discount=Sum(Case(When(type=Transaction.Type.DISCOUNT, then='amount'), default=Value(0), output_field=BigIntegerField())),
            total_damage_charge=Sum(Case(When(type=Transaction.Type.DAMAGE_CHARGE, then='amount'), default=Value(0), output_field=BigIntegerField())),
            total_cancellation_fee=Sum(Case(When(type=Transaction.Type.CANCELLATION_FEE, then='amount'), default=Value(0), output_field=BigIntegerField())),
        )

        if uses_transaction_ledger:
            total_gross_rent = reservation_totals.get('total_gross_rent') or 0
            total_discounts = transaction_totals.get('total_discount') if transaction_totals.get('total_discount') is not None else (reservation_totals.get('total_discounts') or 0)
            total_net_value = total_gross_rent - total_discounts
            total_deposit = transaction_totals.get('total_deposit') or 0
            total_final_payment = transaction_totals.get('total_final_payment') or 0
            total_refunded = transaction_totals.get('total_refund') or 0
            total_remaining = reservation_totals.get('total_remaining') or 0
            total_damage_charge = transaction_totals.get('total_damage_charge') or 0
            total_damage_paid = transaction_totals.get('total_damage_payment') or 0
            total_cancellation_penalty = transaction_totals.get('total_cancellation_fee') or 0
            total_cash_inflow = total_deposit + total_final_payment + total_damage_paid - total_refunded
            total_revenue = total_deposit + total_final_payment
        else:
            total_gross_rent = reservation_totals.get('total_gross_rent') or 0
            total_discounts = reservation_totals.get('total_discounts') or 0
            total_net_value = reservation_totals.get('total_net_reservation_value') or 0
            total_deposit = reservation_totals.get('total_deposit') or 0
            total_final_payment = reservation_totals.get('total_remaining_paid') or 0
            total_refunded = reservation_totals.get('total_refunded') or 0
            total_remaining = reservation_totals.get('total_remaining') or 0
            total_damage_charge = transaction_totals.get('total_damage_charge') or 0
            total_damage_paid = transaction_totals.get('total_damage_payment') or 0
            total_cancellation_penalty = transaction_totals.get('total_cancellation_fee') or 0
            total_cash_inflow = total_deposit + total_final_payment + total_damage_paid - total_refunded
            total_revenue = total_net_value

        cancellation_summary = DashboardService._build_cancellation_report(filters)
        damage_summary = DashboardService._build_damage_report(filters, transaction_totals)
        guarantee_report = DashboardService._build_guarantee_summary(filters)

        cancelled_reservations = Reservation.objects.filter(status=ReservationStatus.CANCELLED)
        cancelled_reservations = DashboardService._apply_reservation_filters(cancelled_reservations, filters)
        cancelled_totals = cancelled_reservations.aggregate(
            total_cancelled_reservations=Count('pk'),
            cancelled_received_amount=Sum('deposit_amount'),
            cancelled_damage_received=Sum('damage_amount'),
            cancelled_refunded_amount=Sum('refunded_amount'),
        )

        # Combine active and cancelled reservations for recent list
        active_recent = list(
            active_qs.select_related('customer', 'dress', 'created_by')
        )
        cancelled_recent = list(
            cancelled_reservations.select_related('customer', 'dress', 'created_by')
        )
        all_recent = sorted(
            active_recent + cancelled_recent,
            key=lambda x: x.created_at,
            reverse=True
        )[:50]
        recent_reservations = all_recent

        recent_transactions = (
            transaction_qs.select_related('reservation', 'created_by')
            .order_by('-transaction_date')[:10]
        )

        discrepancies = ReconciliationService.get_open_problem_reservations()

        return {
            'totals': {
                'total_reservations': active_qs.count(),
                'total_revenue': total_revenue,
                'total_gross_rent': total_gross_rent,
                'total_discounts': total_discounts,
                'total_net_reservation_value': total_net_value,
                'total_deposit': total_deposit,
                'total_remaining': total_remaining,
                'total_damage_received': damage_summary.get('total_damage_paid') or 0,
                'total_cash_inflow': total_cash_inflow,
                'total_refunded': total_refunded,
            },
            'cancelled_totals': {
                'total_cancelled_reservations': cancelled_totals.get('total_cancelled_reservations') or 0,
                'cancelled_received_amount': cancelled_totals.get('cancelled_received_amount') or 0,
                'cancelled_damage_received': cancelled_totals.get('cancelled_damage_received') or 0,
                'cancelled_refunded_amount': cancelled_totals.get('cancelled_refunded_amount') or 0,
            },
            'reporting': {
                'reservation_summary': {
                    'total_gross_reservation_value': total_gross_rent,
                    'total_discount_amount': total_discounts,
                    'total_net_reservation_value': total_net_value,
                    'total_active_reservations': active_qs.count(),
                },
                'payment_summary': {
                    'total_deposit_received': total_deposit,
                    'total_remaining_receivable': total_remaining,
                    'total_cash_inflow': total_cash_inflow,
                },
                'refund_summary': {
                    'total_refunded_amount': total_refunded,
                },
                'cancellation_summary': cancellation_summary,
                'damage_summary': damage_summary,
                'guarantee_summary': guarantee_report['summary'],
                'guarantee_preview': guarantee_report['preview'],
                'discrepancy_summary': {
                    'open_issues': len(discrepancies),
                    'problems': discrepancies[:10],
                },
            },
            'recent_reservations': recent_reservations,
            'recent_transactions': recent_transactions,
            'uses_transaction_ledger': uses_transaction_ledger,
            'open_reconciliation_issues': len(discrepancies),
        }
