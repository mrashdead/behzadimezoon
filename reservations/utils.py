from datetime import date
import jdatetime
from django.utils.dateparse import parse_date


def normalize_digits(value):
    if value is None:
        return ""

    value = str(value).strip()

    persian_arabic_digits = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789"
    )

    return value.translate(persian_arabic_digits)


def parse_reservation_date(value):
    """
    خروجی همیشه date میلادی است.

    ورودی‌های قابل قبول:
    1405/03/24
    ۱۴۰۵/۰۳/۲۴
    1405/3/24
    1405-03-24
    2026-06-14
    """

    if not value:
        return None

    value = normalize_digits(value)
    value = value.strip()

    # یکدست‌سازی جداکننده‌ها
    normalized = value.replace("-", "/")

    parts = normalized.split("/")

    if len(parts) == 3:
        try:
            year = int(parts[0])
            month = int(parts[1])
            day = int(parts[2])

            # اگر سال در بازه شمسی بود
            if 1300 <= year <= 1600:
                return jdatetime.date(year, month, day).togregorian()

            # اگر سال میلادی بود
            if 1900 <= year <= 2200:
                return date(year, month, day)

        except Exception:
            return None

    # fallback فقط برای تاریخ‌های استاندارد میلادی
    parsed = parse_date(value)
    if parsed:
        return parsed

    return None
