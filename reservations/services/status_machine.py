# reservations/services/status_machine.py

from django.utils import timezone

from reservations.constants import RESERVATION_TRANSITIONS
from reservations.models import Reservation
from reservations.services.payment_guards import (
    has_paid_deposit,
    is_fully_paid,
)

ROLE_TRANSITION_PERMISSIONS = {
    'SUPER_ADMIN': None,  # None یعنی هر transition مجاز سیستمی
    'MANAGER': None,
    'SELLER': {
        Reservation.Status.DRAFT: [
            Reservation.Status.CONFIRMED,
            Reservation.Status.CANCELED,
        ],
        Reservation.Status.CONFIRMED: [
            Reservation.Status.DELIVERED,
        ],
        Reservation.Status.DELIVERED: [
            Reservation.Status.RETURNED,
        ],
        Reservation.Status.RETURNED: [],
        Reservation.Status.LAUNDRY: [],
        Reservation.Status.CANCELED: [],
    },
}


def get_allowed_next_statuses(user, reservation):
    current_status = reservation.status
    role = getattr(user, 'role', None)

    system_allowed = RESERVATION_TRANSITIONS.get(current_status, [])
    role_rules = ROLE_TRANSITION_PERMISSIONS.get(role)

    if role_rules is None:
        return system_allowed if role in ROLE_TRANSITION_PERMISSIONS else []

    role_allowed = role_rules.get(current_status, [])
    return [status for status in system_allowed if status in role_allowed]


def can_change_status(user, reservation, new_status):
    current_status = reservation.status
    today = timezone.now().date()

    if new_status not in get_allowed_next_statuses(user, reservation):
        return False

    return _check_guards(reservation, current_status, new_status, today)


def _check_guards(reservation, current_status, new_status, today):
    """
    Guards = زمان + پرداخت
    """

    if new_status == Reservation.Status.DELIVERED and reservation.rent_date > today:
        return False

    if (
        current_status == Reservation.Status.DRAFT
        and new_status == Reservation.Status.CONFIRMED
    ):
        return has_paid_deposit(reservation)

    if (
        current_status == Reservation.Status.DELIVERED
        and new_status == Reservation.Status.RETURNED
    ):
        return is_fully_paid(reservation)

    return True
