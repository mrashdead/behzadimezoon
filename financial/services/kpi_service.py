from django.db.models import Sum, Case, When, Value, BigIntegerField, F

from financial.models import Transaction
from reservations.constants import ReservationStatus


class KPIService:
    @staticmethod
    def revenue_kpi_queryset(statuses=None):
        statuses = statuses or [
            ReservationStatus.CONFIRMED,
            ReservationStatus.DELIVERED,
            ReservationStatus.RETURNED,
            ReservationStatus.READY,
        ]
        return Transaction.objects.filter(reservation__status__in=statuses)

    @staticmethod
    def get_gross_contracted_revenue():
        return Transaction.objects.filter(
            type__in=[Transaction.Type.DEPOSIT, Transaction.Type.FINAL_PAYMENT],
            reservation__status__in=[
                ReservationStatus.CONFIRMED,
                ReservationStatus.DELIVERED,
                ReservationStatus.RETURNED,
                ReservationStatus.READY,
            ]
        ).aggregate(
            total=Sum('amount')
        )['total'] or 0

    @staticmethod
    def get_total_discounts():
        return Transaction.objects.filter(
            type=Transaction.Type.DISCOUNT,
            reservation__status__in=[
                ReservationStatus.CONFIRMED,
                ReservationStatus.DELIVERED,
                ReservationStatus.RETURNED,
                ReservationStatus.READY,
            ]
        ).aggregate(total=Sum('amount'))['total'] or 0

    @staticmethod
    def get_total_refunds():
        return Transaction.objects.filter(type=Transaction.Type.REFUND).aggregate(total=Sum('amount'))['total'] or 0
