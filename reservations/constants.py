# reservations/constants.py

class ReservationStatus:

    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    DELIVERED = "DELIVERED"
    RETURNED = "RETURNED"
    LAUNDRY = "LAUNDRY"
    CANCELLED = "CANCELLED"

    CHOICES = (
        (DRAFT, "پیش‌نویس"),
        (CONFIRMED, "قطعی"),
        (DELIVERED, "تحویل شده"),
        (RETURNED, "بازگشت داده شده"),
        (LAUNDRY, "خشکشویی"),
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
