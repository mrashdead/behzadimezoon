# reservations/services/state_machin.py

from reservations.constants import ReservationStatus


class ReservationStateMachine:

    TRANSITIONS = {
        ReservationStatus.DRAFT: [
            ReservationStatus.CONFIRMED,
            ReservationStatus.CANCELLED,
        ],
        ReservationStatus.CONFIRMED: [
            ReservationStatus.DELIVERED,
            ReservationStatus.CANCELLED,
        ],
        ReservationStatus.DELIVERED: [
            ReservationStatus.RETURNED,
        ],
        ReservationStatus.RETURNED: [
            ReservationStatus.LAUNDRY,
        ],
        ReservationStatus.LAUNDRY: [],
        ReservationStatus.CANCELLED: [],
    }

    @classmethod
    def can_transition(cls, from_status, to_status):
        return to_status in cls.TRANSITIONS.get(from_status, [])
