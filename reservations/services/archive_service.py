from django.db import transaction

from financial.models import Transaction
from reservations.constants import ReservationStatus
from reservations.models import ReservationArchiveSnapshot


class ReservationArchiveService:
    """
    Snapshot reservation data and related financial transactions before
    permanently deleting an archived reservation.
    """

    @staticmethod
    def create_snapshot_and_delete(reservation, user):
        if reservation.status != ReservationStatus.ARCHIVED:
            raise ValueError("فقط رزروهای آرشیو شده قابل حذف کامل هستند.")

        reservation_data = {
            'id': reservation.id,
            'customer_id': reservation.customer_id,
            'dress_id': reservation.dress_id,
            'start_date': str(reservation.start_date) if reservation.start_date else None,
            'rental_days': reservation.rental_days,
            'end_date': str(reservation.end_date) if reservation.end_date else None,
            'final_price': reservation.final_price,
            'deposit_amount': reservation.deposit_amount,
            'remaining_amount': reservation.remaining_amount,
            'status': reservation.status,
            'previous_status': reservation.previous_status,
            'archived_at': str(reservation.archived_at) if reservation.archived_at else None,
        }

        transactions = []
        for transaction_data in Transaction.objects.filter(reservation=reservation).values(
            'id',
            'amount',
            'type',
            'created_by_id',
            'created_at',
            'transaction_date',
            'note',
            'external_reference',
            'payment_method',
            'reservation_snapshot',
        ):
            if transaction_data.get('created_at') is not None:
                transaction_data['created_at'] = str(transaction_data['created_at'])
            if transaction_data.get('transaction_date') is not None:
                transaction_data['transaction_date'] = str(transaction_data['transaction_date'])
            transactions.append(transaction_data)

        snapshot_data = {
            'reservation': reservation_data,
            'transactions': transactions,
        }

        with transaction.atomic():
            ReservationArchiveSnapshot.objects.create(
                original_reservation_id=reservation.id,
                data=snapshot_data,
                created_by=user
            )

            from reservations.models import Reservation as ReservationModel
            # Use the unconditional manager to perform a real delete (bypass soft-delete)
            ReservationModel.all_objects.filter(pk=reservation.pk).delete()
