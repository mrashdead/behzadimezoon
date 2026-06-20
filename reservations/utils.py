from datetime import date
import jdatetime
from django.utils.dateparse import parse_date
from django.conf import settings

User = settings.AUTH_USER_MODEL


def normalize_digits(value):
    """
    Convert Persian/Arabic digits to English digits.
    """
    if value is None:
        return ""

    value = str(value).strip()

    persian_arabic_digits = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789"
    )

    return value.translate(persian_arabic_digits)


def date_to_iso(value):
    """Convert a date or Jalali date value to a Gregorian ISO date string."""
    if not value:
        return None

    if hasattr(value, "togregorian"):
        return value.togregorian().isoformat()

    if hasattr(value, "isoformat"):
        return value.isoformat()

    return str(value)


def get_reservations_for_user(user):
    """
    Get filtered reservations based on user role.

    - SELLER: Only their own reservations (created_by = user)
    - MANAGER / SUPER_ADMIN: All reservations

    Args:
        user: User instance

    Returns:
        QuerySet of Reservation objects
    """
    from .models import Reservation

    if not user.is_authenticated:
        return Reservation.objects.none()

    # Sellers see only their own reservations
    if user.role == 'SELLER':
        return Reservation.objects.filter(created_by=user)

    # Managers and admins see all reservations
    return Reservation.objects.all()


def parse_reservation_date(value):
    """
    Parse date input and return as Gregorian date.

    Input formats accepted:
    - Jalali: 1405/03/24, ۱۴۰۵/۰۳/۲۴, 1405/3/24, 1405-03-24
    - Gregorian: 2026-06-14

    Returns: Gregorian date object
    """

    if not value:
        return None

    value = normalize_digits(value)
    value = value.strip()

    # Normalize separators to forward slash
    normalized = value.replace("-", "/")

    parts = normalized.split("/")

    if len(parts) == 3:
        try:
            year = int(parts[0])
            month = int(parts[1])
            day = int(parts[2])

            # Jalali years: 1300-1600 range
            if 1300 <= year <= 1600:
                j_date = jdatetime.date(year, month, day)
                return j_date.togregorian()

            # Gregorian years: 1900-2200 range
            if 1900 <= year <= 2200:
                return date(year, month, day)

        except (ValueError, OverflowError):
            return None

    # Fallback for standard Gregorian format (YYYY-MM-DD)
    parsed = parse_date(value)
    if parsed:
        return parsed

    return None
