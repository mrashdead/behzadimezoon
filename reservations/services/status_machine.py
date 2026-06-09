# reservations/services/status_machine.py

from django.utils import timezone
from reservations.models import Reservation
from reservations.services.payment_guards import (
    has_paid_deposit,
    is_fully_paid
)

# Transition Map هماهنگ با مدل
RESERVATION_TRANSITIONS = {
    Reservation.Status.DRAFT: [
        Reservation.Status.CONFIRMED,
        Reservation.Status.CANCELED,
    ],
    Reservation.Status.CONFIRMED: [
        Reservation.Status.DELIVERED,
        Reservation.Status.CANCELED,
    ],
    Reservation.Status.DELIVERED: [
        Reservation.Status.RETURNED,
    ],
    Reservation.Status.RETURNED: [
        Reservation.Status.LAUNDRY,
    ],
    Reservation.Status.LAUNDRY: [],
    Reservation.Status.CANCELED: [],
}


def can_change_status(user, reservation, new_status):
    current_status = reservation.status
    role = user.role
    today = timezone.now().date()

    # 1️⃣ مسیر مجاز؟
    if new_status not in RESERVATION_TRANSITIONS.get(current_status, []):
        return False

    # 2️⃣ سوپرادمین → آزاد
    if role == 'SUPER_ADMIN':
        return _check_guards(reservation, current_status, new_status, today)

    # 3️⃣ مدیر
    if role == 'MANAGER':
        return _check_guards(reservation, current_status, new_status, today)

    # 4️⃣ فروشنده
    if role == 'SELLER':
        if current_status == Reservation.Status.DRAFT:
            allowed = new_status in [
                Reservation.Status.CONFIRMED,
                Reservation.Status.CANCELED,
            ]
        elif current_status == Reservation.Status.CONFIRMED:
            allowed = new_status == Reservation.Status.DELIVERED
        elif current_status == Reservation.Status.DELIVERED:
            allowed = new_status == Reservation.Status.RETURNED
        else:
            allowed = False

        if not allowed:
            return False

        return _check_guards(reservation, current_status, new_status, today)

    return False


def _check_guards(reservation, current_status, new_status, today):
    """
    Guards = زمان + پرداخت
    """

    # ⏱️ شرط زمانی تحویل
    if new_status == Reservation.Status.DELIVERED:
        if reservation.rent_date > today:
            return False

    # 💰 شرط بیعانه
    if current_status == Reservation.Status.DRAFT and new_status == Reservation.Status.CONFIRMED:
        return has_paid_deposit(reservation)

    # 💰 شرط تسویه کامل
    if current_status == Reservation.Status.DELIVERED and new_status == Reservation.Status.RETURNED:
        return is_fully_paid(reservation)

    return True
