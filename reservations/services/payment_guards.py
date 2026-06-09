# reservations/services/payment_guards.py

def has_paid_deposit(reservation):
    return reservation.deposit_amount and reservation.deposit_amount > 0


def is_fully_paid(reservation):
    return reservation.remaining_amount == 0
