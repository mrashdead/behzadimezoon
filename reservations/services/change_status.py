# reservations/services/change_status.py

from typing import TYPE_CHECKING
from django.core.exceptions import PermissionDenied
from reservations.services.status_machine import can_change_status

# این ایمپورت فقط برای IDE (مثل VS Code) کار می‌کند و در زمان اجرا نادیده گرفته می‌شود
if TYPE_CHECKING:
    from reservations.models import ReservationStatusLog

def change_reservation_status(user, reservation, new_status):
    # ایمپورت داخلی (Lazy Import) - مدل در لحظه اجرا فراخوانی می‌شود
    from reservations.models import ReservationStatusLog

    old_status = reservation.status

    if not can_change_status(user, reservation, new_status):
        raise PermissionDenied('اجازه تغییر وضعیت این رزرو را ندارید.')

    reservation.status = new_status
    reservation.save(update_fields=['status'])

    # حالا اینجا بدون مشکل از مدل استفاده می‌شود
    ReservationStatusLog.objects.create(
        reservation=reservation,
        old_status=old_status,
        new_status=new_status,
        changed_by=user
    )
