# reservations/services/payment_guards.py

from decimal import Decimal


ZERO = Decimal("0")


def _money(value):
    """
    مقدار None را برای محاسبات مالی به صفر تبدیل می‌کند.
    """
    return value if value is not None else ZERO


def has_paid_deposit(reservation):
    """
    آیا رزرو بیعانه پرداخت‌شده دارد؟
    """

    deposit_amount = _money(getattr(reservation, "deposit_amount", None))
    return deposit_amount > ZERO


def is_fully_paid(reservation):
    """
    آیا رزرو کاملاً تسویه شده است؟
    """

    remaining_amount = _money(getattr(reservation, "remaining_amount", None))
    return remaining_amount <= ZERO
