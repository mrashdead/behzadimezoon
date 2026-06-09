# reservations/constants.py

class ReservationStatus:
    DRAFT = 'DRAFT'
    CONFIRMED = 'CONFIRMED'
    DELIVERED = 'DELIVERED'
    RETURNED = 'RETURNED'
    LAUNDRY = 'LAUNDRY'
    CANCELED = 'CANCELED'

    CHOICES = [
        (DRAFT, 'Draft'),
        (CONFIRMED, 'Confirmed'),
        (DELIVERED, 'Delivered'),
        (RETURNED, 'Returned'),
        (LAUNDRY, 'Laundry'),
        (CANCELED, 'Canceled'),
    ]


RESERVATION_TRANSITIONS = {
    ReservationStatus.DRAFT: [
        ReservationStatus.CONFIRMED,
        ReservationStatus.CANCELED,
    ],
    ReservationStatus.CONFIRMED: [
        ReservationStatus.DELIVERED,
        ReservationStatus.CANCELED,
    ],
    ReservationStatus.DELIVERED: [
        ReservationStatus.RETURNED,
    ],
    ReservationStatus.RETURNED: [
        ReservationStatus.LAUNDRY,
    ],
    ReservationStatus.LAUNDRY: [],
    ReservationStatus.CANCELED: [],
}
