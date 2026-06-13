# reservations/services/change_status.py

from typing import TYPE_CHECKING

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from reservations.services.status_machine import can_change_status

if TYPE_CHECKING:
    from reservations.models import Reservation, ReservationStatusLog


def change_reservation_status(user, reservation, new_status):
    """
    تغییر وضعیت رزرو به‌صورت امن، اتمیک و همراه با ثبت لاگ.
    """

    from reservations.models import Reservation, ReservationStatusLog

    with transaction.atomic():
        locked_reservation = Reservation.objects.select_for_update().get(
            pk=reservation.pk
        )

        old_status = locked_reservation.status

        if old_status == new_status:
            raise ValidationError('وضعیت جدید با وضعیت فعلی یکسان است.')

        if not can_change_status(user, locked_reservation, new_status):
            raise PermissionDenied('تغییر وضعیت این رزرو مجاز نیست.')

        locked_reservation.status = new_status
        locked_reservation.save(update_fields=['status'])

        ReservationStatusLog.objects.create(
            reservation=locked_reservation,
            old_status=old_status,
            new_status=new_status,
            changed_by=user,
        )

    return locked_reservation
