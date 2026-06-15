# reservations/services/change_status.py

from django.utils import timezone
from reservations.services.state_machin import ReservationStateMachine
from reservations.constants import ReservationStatus


class ReservationStatusService:

    @staticmethod
    def change_status(reservation, new_status, user):

        if not ReservationStateMachine.can_transition(
            reservation.status,
            new_status
        ):
            readable_status = dict(ReservationStatus.CHOICES).get(new_status, new_status)
            raise ValueError(
                f"انتقال وضعیت از {reservation.get_status_display()} به {readable_status} مجاز نیست."
            )

        if new_status == ReservationStatus.CANCELLED:
            reservation.cancelled_at = timezone.now()

        reservation.status = new_status
        reservation.updated_by = user
        reservation.save()

        return reservation
