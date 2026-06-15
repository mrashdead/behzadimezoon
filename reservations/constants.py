# reservations/constants.py

class ReservationStatus:

    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    DELIVERED = "DELIVERED"
    RETURNED = "RETURNED"
    LAUNDRY = "LAUNDRY"
    READY = "READY"
    CANCELLED = "CANCELLED"

    CHOICES = (
        (DRAFT, "پیش‌نویس"),
        (CONFIRMED, "قطعی"),
        (DELIVERED, "تحویل به مشتری"),
        (RETURNED, "بازگشت از مشتری"),
        (LAUNDRY, "ارسال شده به خشکشویی"),
        (READY, "آماده و آزاد"),
        (CANCELLED, "لغو شده"),
    )


class GuaranteeType:

    CHECK = "CHECK"
    CASH = "CASH"
    GOLD = "GOLD"
    PROMISSORY = "PROMISSORY"

    CHOICES = (
        (CHECK, "چک"),
        (CASH, "پول"),
        (GOLD, "طلا"),
        (PROMISSORY, "سفته"),
    )


class PaymentMethod:

    CARD = "CARD"
    CASH = "CASH"
    TRANSFER = "TRANSFER"
    POS = "POS"

    CHOICES = (
        (CARD, "کارت به کارت"),
        (CASH, "نقدی"),
        (TRANSFER, "انتقال بانکی"),
        (POS, "کارتخوان"),
    )
