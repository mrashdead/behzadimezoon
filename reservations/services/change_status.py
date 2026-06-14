from typing import TYPE_CHECKING

from django.core.exceptions import PermissionDenied, ValidationError

from reservations.services.status_machine import can_change_status

if TYPE_CHECKING:
    from reservations.models import Reservation


def change_reservation_status(user, reservation, new_status):
    """
    تغییر وضعیت رزرو همراه با کنترل دسترسی و ثبت لاگ احتمالی.
    """

    old_status = reservation.status

    if old_status == new_status:
        return reservation

    if not can_change_status(user, reservation, new_status):
        raise PermissionDenied('شما اجازه تغییر این وضعیت را ندارید.')

    reservation.status = new_status
    reservation.save(update_fields=['status', 'updated_at'])

    _create_status_log(
        user=user,
        reservation=reservation,
        old_status=old_status,
        new_status=new_status,
    )

    return reservation


def _create_status_log(user, reservation, old_status, new_status):
    """
    اگر مدل ReservationStatusLog وجود داشته باشد، لاگ ثبت می‌کند.
    اگر هنوز این مدل را نساخته‌ای، خطا نمی‌دهد.
    """

    try:
        from reservations.models import ReservationStatusLog
    except ImportError:
        return

    try:
        ReservationStatusLog.objects.create(
            reservation=reservation,
            old_status=old_status,
            new_status=new_status,
            changed_by=user if getattr(user, 'is_authenticated', False) else None,
        )
    except Exception:
        # برای اینکه ثبت لاگ باعث شکست تغییر وضعیت نشود
        pass
