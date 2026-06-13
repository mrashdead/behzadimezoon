from django.utils import timezone
from reservations.models import Reservation
from reservations.services.payment_guards import has_paid_deposit, is_fully_paid


ROLE_TRANSITION_PERMISSIONS = {
    'SUPER_ADMIN': None,
    'MANAGER': None,
    'SELLER': {
        Reservation.STATUS_PENDING: [
            Reservation.STATUS_RESERVED,
            Reservation.STATUS_CANCELLED,
        ],
        Reservation.STATUS_RESERVED: [
            Reservation.STATUS_DELIVERED,
            Reservation.STATUS_CANCELLED,
        ],
        Reservation.STATUS_DELIVERED: [
            Reservation.STATUS_RETURNED,
        ],
        Reservation.STATUS_RETURNED: [],
        Reservation.STATUS_CANCELLED: [],
    },
}

RESERVATION_TRANSITIONS = {
    Reservation.STATUS_PENDING: [
        Reservation.STATUS_RESERVED,
        Reservation.STATUS_CANCELLED,
    ],
    Reservation.STATUS_RESERVED: [
        Reservation.STATUS_DELIVERED,
        Reservation.STATUS_CANCELLED,
    ],
    Reservation.STATUS_DELIVERED: [
        Reservation.STATUS_RETURNED,
    ],
    Reservation.STATUS_RETURNED: [],
    Reservation.STATUS_CANCELLED: [],
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
    if new_status == Reservation.STATUS_DELIVERED and reservation.rent_date > today:
        return False

    if (
        current_status == Reservation.STATUS_PENDING
        and new_status == Reservation.STATUS_RESERVED
    ):
        return has_paid_deposit(reservation)

    if (
        current_status == Reservation.STATUS_DELIVERED
        and new_status == Reservation.STATUS_RETURNED
    ):
        return is_fully_paid(reservation)

    return True
