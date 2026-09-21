# reservations/services/payment_stage_service.py
"""
منبع واحد محاسبات پرداخت‌های مرحله‌ای (بیعانه‌ها) برای رزرو.

این سرویس «تنها منبع حقیقت» برای مبالغ پرداختی، مانده، اضافه‌پرداخت و
وضعیت تسویه است. فاکتور، بخش مالی، رزرو و Payment Guard همگی باید از
همین سرویس استفاده کنند تا محاسبات متناقض ایجاد نشود.

مدل ذخیره‌سازی همان ``financial.Transaction`` است (بدون مدل موازی):
    * نوع پرداخت      -> transaction_type (DEPOSIT / PARTIAL_PAYMENT / FINAL_PAYMENT)
    * شماره مرحله     -> sequence_number
    * تاریخ پرداخت    -> transaction_date
    * تاریخ سررسید    -> due_date
    * روش پرداخت      -> payment_method
    * کد رهگیری       -> payment_reference
    * توضیحات         -> description / notes
    * ثبت‌کننده        -> created_by
    * ایجاد/ویرایش    -> created_at / updated_at
    * فعال/حذف‌شده     -> transaction_status (POSTED = فعال، VOIDED = حذف‌شده)
"""

from datetime import datetime, time

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from financial.models import Transaction, FinancialAccount
from financial.services.transaction_service import TransactionService
from reservations.constants import PaymentMethod


# ترتیب مراحل پرداخت (همه انواعی که به عنوان «پرداخت رزرو» شمارش می‌شوند)
STAGED_PAYMENT_TYPES = (
    Transaction.TransactionType.DEPOSIT,
    Transaction.TransactionType.PARTIAL_PAYMENT,
    Transaction.TransactionType.FINAL_PAYMENT,
)

# انواعی که به عنوان ورودی نقدی قابل انتخاب توسط کاربر هستند
SELECTABLE_PAYMENT_TYPES = STAGED_PAYMENT_TYPES

# انواعی که هنگام محاسبه «دریافتی» باید کسر شوند
OUTFLOW_TYPES = (
    Transaction.TransactionType.REFUND,
)

_PERSIAN_ORDINALS = [
    "اول", "دوم", "سوم", "چهارم", "پنجم", "ششم", "هفتم", "هشتم", "نهم", "دهم",
    "یازدهم", "دوازدهم", "سیزدهم", "چهاردهم", "پانزدهم", "شانزدهم", "هفدهم",
    "هجدهم", "نوزدهم", "بیستم",
]

_TYPE_BASE_LABELS = {
    Transaction.TransactionType.DEPOSIT: "بیعانه",
    Transaction.TransactionType.PARTIAL_PAYMENT: "پرداخت تکمیلی",
    Transaction.TransactionType.FINAL_PAYMENT: "پرداخت نهایی",
    Transaction.TransactionType.PAYMENT: "پرداخت",
}

# برای سازگاری با داده‌های قدیمی که نوع پرداخت ندارند
DEFAULT_PAYMENT_TYPE = Transaction.TransactionType.DEPOSIT

# شناسه‌های مجازی برای «ردیف‌های منتقل‌نشده» رزروهای قدیمی.
# این شناسه‌ها هرگز در دیتابیس ذخیره نمی‌شوند؛ فقط به رابط کاربری اجازه
# می‌دهند بیعانه قدیمی را ببیند/ویرایش کند و در زمان ذخیره به تراکنش واقعی
# نگاشت شوند (بدون از دست رفتن داده).
LEGACY_DEPOSIT_ROW_ID = -1
LEGACY_BALANCE_ROW_ID = -2
LEGACY_ROW_IDS = (LEGACY_DEPOSIT_ROW_ID, LEGACY_BALANCE_ROW_ID)


class PaymentStageError(ValidationError):
    """خطای دامنه‌ای برای پرداخت‌های مرحله‌ای (پیام‌ها فارسی و قابل نمایش هستند)."""


class _StageProxy:
    """نمای سبک برای محاسبه برچسب مرحله پیش از ایجاد تراکنش."""

    def __init__(self, transaction_type, sequence_number):
        self.transaction_type = transaction_type
        self.sequence_number = sequence_number


def _persian_ordinal(index):
    """۱ -> اول ، ۲ -> دوم ، ..."""
    if index is None:
        return ""
    if 1 <= index <= len(_PERSIAN_ORDINALS):
        return _PERSIAN_ORDINALS[index - 1]
    return str(index)


def _to_int(value, label="مبلغ"):
    """تبدیل ورودی (فارسی/انگلیسی، با جداکننده هزارگان) به عدد صحیح."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise PaymentStageError(f"{label} نامعتبر است.")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != int(value):
            raise PaymentStageError(f"{label} باید یک عدد صحیح باشد.")
        return int(value)

    text = str(value).strip()
    # اعداد فارسی/عربی -> انگلیسی
    text = text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    # حذف جداکننده‌ها و فاصله‌ها
    for ch in (",", "٬", "٫", " ", "\u200c", "\u202f"):
        text = text.replace(ch, "")
    if text == "":
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise PaymentStageError(f"{label} باید یک عدد صحیح باشد.") from exc


def _parse_jalali_or_gregorian_date(value, label="تاریخ"):
    """ورودی تاریخ شمسی/میلادی را به date میلادی تبدیل می‌کند."""
    from reservations.utils import parse_reservation_date

    if value in (None, ""):
        return None
    if hasattr(value, "togregorian"):
        return value.togregorian()
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        return value

    parsed = parse_reservation_date(value)
    if parsed is None:
        raise PaymentStageError(f"{label} نامعتبر است.")
    return parsed


def _to_aware_datetime(gregorian_date):
    """date میلادی -> datetime آگاه از منطقه زمانی (ساعت ۱۲ ظهر)."""
    if gregorian_date is None:
        return timezone.now()
    naive = datetime.combine(gregorian_date, time(12, 0))
    if timezone.is_naive(naive):
        try:
            return timezone.make_aware(naive, timezone.get_current_timezone())
        except Exception:
            return timezone.make_aware(naive)
    return naive


def _coerce_datetime(value, fallback=None):
    """
    تبدیل ورودی تاریخ/زمان (شمسی یا میلادی، date یا datetime) به datetime
    آگاه از منطقه زمانی. برای مقادیر ``jdatetime`` نیز درست کار می‌کند.
    """
    if value is None:
        return fallback
    if hasattr(value, "togregorian"):
        value = value.togregorian()
    if isinstance(value, datetime):
        dt = value
    elif hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        hour = getattr(value, "hour", 12)
        minute = getattr(value, "minute", 0)
        second = getattr(value, "second", 0)
        dt = datetime(value.year, value.month, value.day, hour, minute, second)
    else:
        return fallback
    if timezone.is_naive(dt):
        try:
            return timezone.make_aware(dt, timezone.get_current_timezone())
        except Exception:
            return timezone.make_aware(dt)
    return dt


class ReservationPaymentService:
    """سرویس مرکزی پرداخت‌های مرحله‌ای رزرو."""

    STAGED_TYPES = STAGED_PAYMENT_TYPES
    SELECTABLE_PAYMENT_TYPES = SELECTABLE_PAYMENT_TYPES

    # ------------------------------------------------------------------
    # کوئری‌ها
    # ------------------------------------------------------------------
    @classmethod
    def payments_queryset(cls, reservation, include_voided=False):
        """پرداخت‌های مرحله‌ای یک رزرو (به‌صورت پیش‌فرض فقط فعال‌ها)."""
        if reservation is None or reservation.pk is None:
            return Transaction.objects.none()

        qs = Transaction.objects.filter(
            reservation_id=reservation.pk,
            transaction_type__in=cls.STAGED_TYPES,
        )
        if not include_voided:
            qs = qs.filter(
                transaction_status=Transaction.TransactionStatus.POSTED,
                is_voided=False,
            )
        return qs.order_by("sequence_number", "transaction_date", "pk")

    @classmethod
    def valid_payments(cls, reservation):
        """لیست پرداخت‌های معتبر (فعال) رزرو."""
        return list(cls.payments_queryset(reservation))

    @classmethod
    def next_sequence_number(cls, reservation):
        """شماره مرحله بعدی برای ثبت یک پرداخت جدید."""
        from django.db.models import Max

        if reservation is None or reservation.pk is None:
            return 1
        current = cls.payments_queryset(reservation, include_voided=True).aggregate(
            maximum=Max("sequence_number")
        )["maximum"] or 0
        return current + 1

    # ------------------------------------------------------------------
    # سازگاری با رکوردهای قدیمی (بدون تراکنش)
    # ------------------------------------------------------------------
    @classmethod
    def has_payment_history(cls, reservation):
        """
        آیا برای این رزرو حداقل یک تراکنش پرداخت (حتی حذف‌شده) ثبت شده است؟

        رزروهای قدیمی که فقط مقدار ``deposit_amount`` دارند و هیچ تراکنشی
        ندارند، از مقادیر کش‌شده به‌عنوان جایگزین استفاده می‌کنند تا اطلاعات
        مالی گذشته از بین نرود.
        """
        if reservation is None or reservation.pk is None:
            return False
        return cls.payments_queryset(reservation, include_voided=True).exists()

    @classmethod
    def has_deposit_history(cls, reservation):
        """
        آیا تراکنش بیعانه‌ای (حتی حذف‌شده) برای این رزرو وجود دارد؟

        تفکیک «سطل» بیعانه از «سطل» پرداخت تکمیلی/نهایی باعث می‌شود مقدار
        کش‌شده قدیمی فقط زمانی نادیده گرفته شود که همان سطل واقعاً در دفتر
        تراکنش‌ها ثبت شده باشد؛ بنابراین ثبت یک پرداخت نهایی، بیعانه قدیمی را
        حذف نمی‌کند.
        """
        if reservation is None or reservation.pk is None:
            return False
        return cls.payments_queryset(reservation, include_voided=True).filter(
            transaction_type=Transaction.TransactionType.DEPOSIT
        ).exists()

    @classmethod
    def has_balance_history(cls, reservation):
        """آیا تراکنش پرداخت تکمیلی/نهایی (حتی حذف‌شده) وجود دارد؟"""
        if reservation is None or reservation.pk is None:
            return False
        return cls.payments_queryset(reservation, include_voided=True).filter(
            transaction_type__in=[
                Transaction.TransactionType.PARTIAL_PAYMENT,
                Transaction.TransactionType.FINAL_PAYMENT,
            ]
        ).exists()

    @classmethod
    def pending_legacy_amounts(cls, reservation):
        """
        مقادیر کش‌شده قدیمی که هنوز به تراکنش تبدیل نشده‌اند.

        خروجی: ``{"deposit": int, "balance": int}``
        """
        if reservation is None or reservation.pk is None:
            return {"deposit": 0, "balance": 0}
        deposit = 0
        balance = 0
        if not cls.has_deposit_history(reservation):
            deposit = reservation.deposit_amount or 0
        if not cls.has_balance_history(reservation):
            balance = reservation.remaining_payment_amount or 0
        return {"deposit": deposit, "balance": balance}

    # ------------------------------------------------------------------
    # برچسب مرحله (بیعانه اول/دوم/...)
    # ------------------------------------------------------------------
    @classmethod
    def stage_label(cls, transaction_obj, stage_index=None):
        """برچسب خوانای مرحله پرداخت."""
        tx_type = getattr(transaction_obj, "transaction_type", DEFAULT_PAYMENT_TYPE)
        base = _TYPE_BASE_LABELS.get(tx_type, "پرداخت")

        if stage_index is None:
            stage_index = getattr(transaction_obj, "sequence_number", None)

        # پرداخت نهایی یک مفهوم یگانه است و شماره مرحله نمی‌گیرد
        if tx_type == Transaction.TransactionType.FINAL_PAYMENT and stage_index in (None, 0, 1):
            return base
        if stage_index:
            return f"{base} {_persian_ordinal(stage_index)}"
        return base

    @classmethod
    def _label_pairs(cls, payments):
        """
        جفت (پرداخت، برچسب) با شماره‌گذاری خودکار و پایدار.

        شماره هر مرحله درون «نوع خودش» شمرده می‌شود؛ بنابراین برچسب‌ها
        همیشه «بیعانه اول، بیعانه دوم، ...» می‌مانند و کاربر نمی‌تواند
        آن‌ها را دستکاری کند. ``order`` ترتیب کلی نمایش است.
        """
        counters = {}
        result = []
        for index, tx in enumerate(payments, start=1):
            tx_type = getattr(tx, "transaction_type", DEFAULT_PAYMENT_TYPE)
            counters[tx_type] = counters.get(tx_type, 0) + 1
            stage_index = counters[tx_type]
            result.append((tx, stage_index, cls.stage_label(tx, stage_index), index))
        return result

    # ------------------------------------------------------------------
    # محاسبات مرکزی
    # ------------------------------------------------------------------
    @classmethod
    def total_deposit(cls, reservation):
        """مجموع بیعانه‌های معتبر (با سازگاری عقب‌رو در سطح همان سطل)."""
        if reservation is None:
            return 0
        if not cls.has_deposit_history(reservation):
            # رزرو قدیمی: بیعانه فقط در فیلد کش‌شده وجود دارد
            return reservation.deposit_amount or 0
        return cls.payments_queryset(reservation).filter(
            transaction_type=Transaction.TransactionType.DEPOSIT
        ).aggregate(total=Sum("amount"))["total"] or 0

    @classmethod
    def total_balance_payments(cls, reservation):
        """مجموع پرداخت‌های تکمیلی/نهایی معتبر (با سازگاری عقب‌رو)."""
        if reservation is None:
            return 0
        if not cls.has_balance_history(reservation):
            return reservation.remaining_payment_amount or 0
        return cls.payments_queryset(reservation).filter(
            transaction_type__in=[
                Transaction.TransactionType.PARTIAL_PAYMENT,
                Transaction.TransactionType.FINAL_PAYMENT,
            ]
        ).aggregate(total=Sum("amount"))["total"] or 0

    @classmethod
    def total_paid(cls, reservation):
        """
        مجموع تمام پرداخت‌های معتبر رزرو (بیعانه + تکمیلی + نهایی).

        این مقدار همیشه برابر جمع دو سطل بالا است تا هیچ‌گاه دو محاسبه
        متناقض (مثلاً «جمع کل تراکنش‌ها» در برابر «جمع سطل‌ها») شکل نگیرد.
        """
        if reservation is None:
            return 0
        return cls.total_deposit(reservation) + cls.total_balance_payments(reservation)

    @classmethod
    def total_refunded(cls, reservation):
        """مجموع بازپرداخت‌های معتبر."""
        if reservation is None or reservation.pk is None:
            return 0
        has_refund_history = Transaction.objects.filter(
            reservation_id=reservation.pk,
            transaction_type__in=OUTFLOW_TYPES,
        ).exists()
        if not has_refund_history:
            # سازگاری عقب‌رو: مقدار کش‌شده بازپرداخت
            return reservation.refunded_amount or 0
        return Transaction.objects.filter(
            reservation_id=reservation.pk,
            transaction_type__in=OUTFLOW_TYPES,
            transaction_status=Transaction.TransactionStatus.POSTED,
            is_voided=False,
        ).aggregate(total=Sum("amount"))["total"] or 0

    @classmethod
    def total_due(cls, reservation):
        """مبلغ کل قابل پرداخت رزرو (مبلغ نهایی + هزینه‌های جانبی + خسارت + جریمه لغو)."""
        total = reservation.final_price or 0
        try:
            total += reservation.total_additional_fees() or 0
        except Exception:
            pass
        total += reservation.damage_amount or 0
        total += reservation.cancellation_fee or 0
        return total

    @classmethod
    def remaining_amount(cls, reservation):
        """مانده قابل پرداخت = مبلغ کل - مجموع پرداخت‌های معتبر - بازپرداخت‌ها."""
        remaining = cls.total_due(reservation) - cls.total_paid(reservation) - cls.total_refunded(reservation)
        return remaining

    @classmethod
    def core_remaining_amount(cls, reservation):
        """
        مانده «هسته‌ای» فقط بر پایه مبلغ نهایی رزرو (بدون هزینه‌های جانبی،
        خسارت و جریمه لغو).

        این مقدار برای منطق‌های وضعیت/تحویل استفاده می‌شود تا رفتار قبلی
        سیستم حفظ شود.
        """
        return (reservation.final_price or 0) - cls.total_paid(reservation) - cls.total_refunded(reservation)

    @classmethod
    def outstanding_amount(cls, reservation):
        """مانده مثبت (بدون منفی)."""
        return max(cls.remaining_amount(reservation), 0)

    @classmethod
    def overpaid_amount(cls, reservation):
        """مبلغ اضافه‌پرداخت (در صورت منفی بودن مانده)."""
        return max(-cls.remaining_amount(reservation), 0)

    @classmethod
    def settlement_status(cls, reservation):
        """وضعیت تسویه به‌همراه برچسب فارسی."""
        remaining = cls.remaining_amount(reservation)
        if remaining > 0:
            return {"code": "DEBTOR", "label": "دارای بدهی", "amount": remaining}
        if remaining == 0:
            return {"code": "SETTLED", "label": "تسویه کامل", "amount": 0}
        return {"code": "OVERPAID", "label": "اضافه‌پرداخت", "amount": -remaining}

    @classmethod
    def capacity_for_payment(cls, reservation):
        """حداکثر مبلغی که هنوز می‌توان به‌عنوان پرداخت جدید ثبت کرد."""
        return max(cls.remaining_amount(reservation), 0)

    # ------------------------------------------------------------------
    # کنترل هم‌زمانی / ارسال دوباره
    # ------------------------------------------------------------------
    @staticmethod
    def payment_revision(reservation):
        """
        توکن ساده و پایدار برای تشخیص «ارسال دوباره فرم» یا «ویرایش هم‌زمان
        توسط کاربر دیگر». هر بار ذخیره رزرو، این مقدار تغییر می‌کند.
        """
        updated_at = getattr(reservation, "updated_at", None)
        if updated_at is None:
            return "0"
        if hasattr(updated_at, "togregorian"):
            updated_at = updated_at.togregorian()
        try:
            return updated_at.isoformat()
        except Exception:
            return str(updated_at)

    # ------------------------------------------------------------------
    # سریال‌سازی برای قالب/JSON
    # ------------------------------------------------------------------
    @classmethod
    @staticmethod
    def _format_jalali(value):
        """تبدیل date/datetime میلادی به رشته تاریخ شمسی."""
        import jdatetime

        if not value:
            return ""
        try:
            if hasattr(value, "togregorian"):
                value = value.togregorian()
            if hasattr(value, "date"):
                value = value.date()
            return jdatetime.date.fromgregorian(date=value).strftime("%Y/%m/%d")
        except Exception:
            return ""

    @classmethod
    def legacy_virtual_rows(cls, reservation):
        """
        ردیف‌های مجازی برای مقادیر کش‌شده قدیمی که هنوز تراکنش ندارند.

        این ردیف‌ها با شناسه منفی علامت‌گذاری می‌شوند تا در فرم قابل ویرایش
        باشند و هنگام ذخیره به تراکنش واقعی نگاشت شوند (بدون از دست رفتن داده).
        """
        pending = cls.pending_legacy_amounts(reservation)
        created_jalali = cls._format_jalali(getattr(reservation, "created_at", None))
        rows = []

        if pending["deposit"] > 0:
            rows.append({
                "id": LEGACY_DEPOSIT_ROW_ID,
                "is_legacy": True,
                "amount": pending["deposit"],
                "payment_type": Transaction.TransactionType.DEPOSIT,
                "payment_type_label": _TYPE_BASE_LABELS[Transaction.TransactionType.DEPOSIT],
                "stage_number": 1,
                "stage_label": f"{_TYPE_BASE_LABELS[Transaction.TransactionType.DEPOSIT]} اول",
                "order": 1,
                "payment_date": None,
                "payment_date_jalali": created_jalali,
                "due_date": None,
                "due_date_jalali": "",
                "payment_method": reservation.payment_method or "",
                "payment_method_label": dict(PaymentMethod.CHOICES).get(
                    reservation.payment_method, reservation.payment_method or ""
                ),
                "payment_reference": reservation.payment_tracking_code or "",
                "description": "بیعانه اول (داده قدیمی)",
                "created_by": reservation.created_by_id,
                "created_at": getattr(reservation, "created_at", None),
                "updated_at": getattr(reservation, "updated_at", None),
                "is_voided": False,
                "status": Transaction.TransactionStatus.POSTED,
            })

        if pending["balance"] > 0:
            rows.append({
                "id": LEGACY_BALANCE_ROW_ID,
                "is_legacy": True,
                "amount": pending["balance"],
                "payment_type": Transaction.TransactionType.FINAL_PAYMENT,
                "payment_type_label": _TYPE_BASE_LABELS[Transaction.TransactionType.FINAL_PAYMENT],
                "stage_number": 1,
                "stage_label": _TYPE_BASE_LABELS[Transaction.TransactionType.FINAL_PAYMENT],
                "order": 2,
                "payment_date": None,
                "payment_date_jalali": cls._format_jalali(
                    getattr(reservation, "remaining_paid_at", None)
                ) or created_jalali,
                "due_date": None,
                "due_date_jalali": "",
                "payment_method": reservation.remaining_payment_method or "",
                "payment_method_label": dict(PaymentMethod.CHOICES).get(
                    reservation.remaining_payment_method, reservation.remaining_payment_method or ""
                ),
                "payment_reference": reservation.remaining_payment_tracking_code or "",
                "description": "پرداخت نهایی (داده قدیمی)",
                "created_by": reservation.created_by_id,
                "created_at": getattr(reservation, "created_at", None),
                "updated_at": getattr(reservation, "updated_at", None),
                "is_voided": False,
                "status": Transaction.TransactionStatus.POSTED,
            })

        return rows

    @classmethod
    def serialize_payments(cls, reservation, include_voided=False):
        """لیست پرداخت‌های رزرو به‌صورت دیکشنری آماده نمایش."""
        payments = list(cls.payments_queryset(reservation, include_voided=include_voided))
        rows = []
        for tx, stage_index, label, order in cls._label_pairs(payments):
            payment_date = getattr(tx, "transaction_date", None)
            due_date = getattr(tx, "due_date", None)
            rows.append({
                "id": tx.pk,
                "is_legacy": False,
                "amount": tx.amount or 0,
                "payment_type": tx.transaction_type,
                "payment_type_label": _TYPE_BASE_LABELS.get(tx.transaction_type, "پرداخت"),
                "stage_number": stage_index,
                "stage_label": label,
                "order": order,
                "payment_date": payment_date,
                "payment_date_jalali": cls._format_jalali(payment_date),
                "due_date": due_date,
                "due_date_jalali": cls._format_jalali(due_date),
                "payment_method": tx.payment_method or "",
                "payment_method_label": dict(PaymentMethod.CHOICES).get(tx.payment_method, tx.payment_method or ""),
                "payment_reference": tx.payment_reference or "",
                "description": tx.description or tx.notes or "",
                "created_by": tx.created_by,
                "created_at": tx.created_at,
                "updated_at": tx.updated_at,
                "is_voided": tx.transaction_status != Transaction.TransactionStatus.POSTED or tx.is_voided,
                "status": tx.transaction_status,
            })

        if include_voided:
            # ردیف‌های مجازی فقط برای نمایش «پرداخت‌های معتبر» معنا دارند
            return rows

        # ردیف‌های مجازی رزروهای قدیمی: بیعانه در ابتدا، پرداخت نهایی در انتها
        virtual_rows = cls.legacy_virtual_rows(reservation)
        deposits = [row for row in virtual_rows if row["payment_type"] == Transaction.TransactionType.DEPOSIT]
        balances = [row for row in virtual_rows if row["payment_type"] != Transaction.TransactionType.DEPOSIT]

        combined = deposits + rows + balances
        for index, row in enumerate(combined, start=1):
            row["order"] = index
        return combined


    @classmethod
    def build_financial_summary(cls, reservation):
        """خلاصه مالی کامل و یکپارچه (فاکتور، بخش مالی و رزرو از همین استفاده می‌کنند)."""
        status = cls.settlement_status(reservation)
        return {
            "total_price": cls.total_due(reservation),
            "final_price": reservation.final_price or 0,
            "additional_fees": (reservation.total_additional_fees() if reservation.pk else 0),
            "damage_amount": reservation.damage_amount or 0,
            "cancellation_fee": reservation.cancellation_fee or 0,
            "total_paid": cls.total_paid(reservation),
            "total_deposit": cls.total_deposit(reservation),
            "total_balance_payments": cls.total_balance_payments(reservation),
            "total_refunded": cls.total_refunded(reservation),
            "remaining_amount": status["amount"] if status["code"] != "OVERPAID" else 0,
            "signed_remaining": cls.remaining_amount(reservation),
            "overpaid_amount": cls.overpaid_amount(reservation),
            "settlement_code": status["code"],
            "settlement_label": status["label"],
            "payments": cls.serialize_payments(reservation),
        }

    # ------------------------------------------------------------------
    # همگام‌سازی فیلدهای کش رزرو با تراکنش‌ها
    # ------------------------------------------------------------------
    @classmethod
    def sync_reservation_payment_caches(cls, reservation, save=False):
        """
        فیلدهای ``deposit_amount`` و ``remaining_payment_amount`` را از
        مجموع تراکنش‌های معتبر بازنویسی می‌کند تا هیچ‌گاه مبلغ پرداختی
        با جمع‌زدن فیلدهای پراکنده محاسبه نشود.

        ``remaining_amount`` و ``payment_status`` توسط
        ``ReservationFinancialService`` (منبع موجود) به‌روزرسانی می‌شوند.
        """
        if reservation is None or reservation.pk is None:
            return reservation

        reservation.deposit_amount = cls.total_deposit(reservation)
        reservation.remaining_payment_amount = cls.total_balance_payments(reservation)

        # بازمحاسبه تخفیف/مبلغ نهایی پیش از محاسبه مانده
        try:
            reservation.discount_amount = reservation.calculate_discount_amount()
        except Exception:
            pass

        from financial.services.reservation_financial_service import ReservationFinancialService
        ReservationFinancialService.update_financial_status(reservation)

        if save:
            reservation.save()
        return reservation

    # ------------------------------------------------------------------
    # تازه‌سازی هدفمند کش‌های مالی
    # ------------------------------------------------------------------
    CACHE_FIELDS = (
        "deposit_amount",
        "remaining_payment_amount",
        "remaining_amount",
        "refunded_amount",
        "payment_status",
        "remaining_payment_method",
        "remaining_payment_tracking_code",
        "remaining_paid_at",
    )

    @classmethod
    def refresh_payment_caches(cls, reservation):
        """
        فقط «فیلدهای کش مالی» را از دیتابیس روی همان نمونه تازه می‌کند.

        چرا این متد لازم است؟
            پس از ``replace_staged_payments`` که خودش یک نسخهٔ قفل‌شده از
            رزرو را می‌خواند و ذخیره می‌کند، نمونهٔ در دسترس ویو از نظر کش
            مالی کهنه می‌شود. راه‌حل ساده اما **مخرب** این است که
            ``refresh_from_db()`` صدا زده شود؛ اما آن تمام تغییرات ویرایش‌نشدهٔ
            فرم (تاریخ، لباس، شماره قرارداد، تضامین و...) را هم از بین می‌برد.

        این متد تنها همان فیلدهایی را به‌روزرسانی می‌کند که سرویس پرداخت
        مسئول آن‌هاست، و بقیهٔ تغییرات فرم را دست‌نخورده نگه می‌دارد.
        """
        if reservation is None or reservation.pk is None:
            return reservation

        fresh = (
            type(reservation)
            .all_objects.filter(pk=reservation.pk)
            .values(*cls.CACHE_FIELDS)
            .first()
        )
        if not fresh:
            return reservation

        for field, value in fresh.items():
            setattr(reservation, field, value)
        return reservation

    # ------------------------------------------------------------------
    # اعتبارسنجی ردیف‌های ورودی
    # ------------------------------------------------------------------
    @classmethod
    def _clean_row(cls, row, reservation):
        """اعتبارسنجی یک ردیف پرداخت. ``None`` یعنی ردیف خالی/حذف‌شده."""
        if row.get("deleted"):
            return None

        amount = _to_int(row.get("amount"), "مبلغ پرداخت")
        if amount is None:
            # ردیف کاملاً خالی -> نادیده گرفته می‌شود
            if not (row.get("payment_reference") or row.get("description") or row.get("payment_date")):
                return None
            raise PaymentStageError("مبلغ پرداخت الزامی است.")
        if amount <= 0:
            raise PaymentStageError("مبلغ پرداخت باید بیشتر از صفر باشد.")

        payment_type = row.get("payment_type") or DEFAULT_PAYMENT_TYPE
        if payment_type not in cls.SELECTABLE_PAYMENT_TYPES:
            raise PaymentStageError("نوع پرداخت نامعتبر است.")

        payment_method = (row.get("payment_method") or "").strip()
        if payment_method and payment_method not in dict(PaymentMethod.CHOICES):
            raise PaymentStageError("روش پرداخت نامعتبر است.")

        payment_reference = (row.get("payment_reference") or "").strip()
        if payment_method and payment_method != PaymentMethod.CASH and not payment_reference:
            raise PaymentStageError("برای روش پرداخت غیرنقدی باید کد رهگیری وارد شود.")

        payment_date = _parse_jalali_or_gregorian_date(row.get("payment_date"), "تاریخ پرداخت")
        due_date = _parse_jalali_or_gregorian_date(row.get("due_date"), "تاریخ سررسید")

        if due_date and payment_date and due_date < payment_date:
            raise PaymentStageError("تاریخ سررسید نمی‌تواند قبل از تاریخ پرداخت باشد.")

        # تاریخ پرداخت نباید قبل از تاریخ ثبت رزرو باشد
        created_date = cls._reservation_created_date(reservation)
        if payment_date and created_date and payment_date < created_date:
            raise PaymentStageError("تاریخ پرداخت نمی‌تواند قبل از تاریخ ثبت رزرو باشد.")

        return {
            "id": row.get("id"),
            "amount": amount,
            "payment_type": payment_type,
            "payment_method": payment_method or None,
            "payment_reference": payment_reference,
            "description": (row.get("description") or "").strip(),
            "payment_date": payment_date,
            "due_date": due_date,
        }

    @staticmethod
    def _reservation_created_date(reservation):
        """تاریخ ثبت رزرو به میلادی (با مدیریت jdatetime)."""
        created_at = getattr(reservation, "created_at", None)
        if created_at is None:
            return None
        if hasattr(created_at, "togregorian"):
            created_at = created_at.togregorian()
        try:
            return created_at.date()
        except AttributeError:
            return created_at

    # ------------------------------------------------------------------
    # جایگزینی اتمیک پرداخت‌های مرحله‌ای (ایجاد/ویرایش/حذف)
    # ------------------------------------------------------------------
    @classmethod
    @transaction.atomic
    def replace_staged_payments(cls, reservation, rows, user, allow_overpay=False,
                                expected_revision=None):
        """
        پرداخت‌های مرحله‌ای رزرو را با ``rows`` جایگزین می‌کند.

        * رزرو با ``select_for_update`` قفل می‌شود (ضد Race Condition).
        * مجموع جدید داخل همان تراکنش بازمحاسبه می‌شود؛ به مقدار نمایش‌داده‌شده
          در صفحه اعتماد نمی‌شود.
        * ردیف‌های حذف‌شده به‌صورت نرم (VOIDED) علامت می‌خورند تا سابقه حفظ شود.
        * ترتیب مراحل به‌صورت خودکار تعیین می‌شود (کاربر نمی‌تواند آن را خراب کند).
        """
        if reservation is None or reservation.pk is None:
            raise PaymentStageError("رزرو نامعتبر است.")

        reservation = (
            type(reservation).all_objects.select_for_update().get(pk=reservation.pk)
        )

        # تشخیص ارسال دوباره یا ویرایش هم‌زمان
        if expected_revision is not None and str(expected_revision) != cls.payment_revision(reservation):
            raise PaymentStageError(
                "این پرداخت قبلاً ثبت شده یا توسط کاربر دیگری تغییر کرده است. "
                "لطفاً صفحه را دوباره بارگذاری کنید."
            )

        # مبلغ کل مجاز = مبلغ نهایی + هزینه‌های جانبی + خسارت + جریمه لغو - بازپرداخت‌ها
        allowed_total = cls.total_due(reservation) - cls.total_refunded(reservation)
        if allowed_total < 0:
            allowed_total = 0

        # --- تبدیل مقادیر کش‌شده قدیمی به تراکنش واقعی (بدون از دست رفتن داده) ---
        # فقط زمانی که کلاینت ردیف مجازی (شناسه منفی) فرستاده باشد، مقدار قدیمی
        # به تراکنش تبدیل می‌شود؛ در غیر این صورت فرم‌های قدیمی که ردیف پرداخت
        # نمی‌فرستند باعث پاک شدن بیعانه نمی‌شوند (شبکه ایمنی پایین‌تر).
        pending_before = cls.pending_legacy_amounts(reservation)
        pending_total = pending_before["deposit"] + pending_before["balance"]
        client_saw_legacy = any(
            (row or {}).get("id") in LEGACY_ROW_IDS for row in (rows or [])
        )

        legacy_id_map = {}
        if client_saw_legacy:
            legacy_id_map = cls.materialize_legacy_payments(reservation, user)
            if legacy_id_map:
                reservation.refresh_from_db()

        cleaned_rows = []
        new_total = 0
        for row in rows or []:
            row = dict(row)
            raw_id = row.get("id")
            if raw_id in LEGACY_ROW_IDS:
                row["id"] = legacy_id_map.get(raw_id)
            cleaned = cls._clean_row(row, reservation)
            if cleaned is None:
                continue
            new_total += cleaned["amount"]
            cleaned_rows.append(cleaned)

        if new_total > allowed_total and not allow_overpay:
            raise PaymentStageError(
                f"مجموع پرداخت‌ها نمی‌تواند از مبلغ کل رزرو ({allowed_total:,} تومان) بیشتر شود."
            )

        # شبکه ایمنی: اگر مقدار قدیمی وجود دارد اما کلاینت آن را ندیده و هیچ
        # ردیفی هم نفرستاده، اجازه پاک شدن اطلاعات را نمی‌دهیم.
        if pending_total > 0 and new_total == 0 and not client_saw_legacy:
            raise PaymentStageError(
                "اطلاعات پرداخت این رزرو قدیمی است. لطفاً صفحه را دوباره بارگذاری کنید."
            )

        existing = {
            tx.pk: tx
            for tx in cls.payments_queryset(reservation, include_voided=True)
        }

        kept_ids = set()
        # --- به‌روزرسانی/ایجاد ردیف‌ها با ترتیب خودکار ---
        for position, row in enumerate(cleaned_rows, start=1):
            tx = existing.get(row["id"]) if row["id"] else None
            if tx is not None:
                kept_ids.add(tx.pk)
                cls._update_payment(tx, row, position, user)
            else:
                tx = cls._create_payment(reservation, row, position, user)
                kept_ids.add(tx.pk)

        # --- نرم‌حذف ردیف‌های حذف‌شده ---
        for tx_id, tx in existing.items():
            if tx_id in kept_ids:
                continue
            if tx.transaction_status == Transaction.TransactionStatus.POSTED and not tx.is_voided:
                cls._void_payment(tx, user)

        # --- همگام‌سازی کش‌های مالی رزرو (داخل همان تراکنش) ---
        cls.sync_reservation_payment_caches(reservation, save=False)
        reservation.updated_by = user
        reservation.save()

        # --- اسنپ‌شات مالی برای حسابرسی ---
        try:
            from financial.services.reservation_financial_service import ReservationFinancialService
            ReservationFinancialService.capture_financial_snapshot(reservation, "staged_payments")
            reservation.save()
        except Exception:
            pass

        return reservation

    # ------------------------------------------------------------------
    # عملیات سطح تراکنش
    # ------------------------------------------------------------------
    @staticmethod
    def _default_account():
        return FinancialAccount.objects.filter(
            account_type=FinancialAccount.AccountType.CASH
        ).first()

    @classmethod
    def _apply_account_balance(cls, account, amount, direction=1):
        if account is None:
            return
        account.balance = (account.balance or 0) + (direction * (amount or 0))
        account.save(update_fields=["balance"])

    @classmethod
    def _create_payment(cls, reservation, row, position, user):
        account = cls._default_account()
        default_description = cls.stage_label(
            _StageProxy(row["payment_type"], position)
        )
        tx = TransactionService.create(
            reservation=reservation,
            transaction_type=row["payment_type"],
            amount=row["amount"],
            created_by=user,
            account=account,
            payment_method=row["payment_method"],
            payment_reference=row["payment_reference"],
            description=row["description"] or default_description,
            transaction_date=_to_aware_datetime(row["payment_date"]),
        )
        Transaction.objects.filter(pk=tx.pk).update(
            sequence_number=position, due_date=row["due_date"]
        )
        tx.sequence_number = position
        tx.due_date = row["due_date"]
        return tx

    @classmethod
    def _update_payment(cls, tx, row, position, user):
        old_amount = tx.amount or 0
        old_is_posted = (
            tx.transaction_status == Transaction.TransactionStatus.POSTED and not tx.is_voided
        )
        was_voided = not old_is_posted

        tx.amount = row["amount"]
        tx.transaction_type = row["payment_type"]
        tx.payment_method = row["payment_method"]
        tx.payment_reference = row["payment_reference"]
        if row["description"]:
            tx.description = row["description"]
        tx.transaction_date = _to_aware_datetime(row["payment_date"])
        tx.due_date = row["due_date"]
        tx.sequence_number = position
        tx.transaction_status = Transaction.TransactionStatus.POSTED
        tx.is_voided = False
        if user is not None and tx.created_by_id is None:
            tx.created_by = user
        tx.save()

        # اصلاح تراز حساب در صورت تغییر مبلغ یا احیای تراکنش ابطال‌شده
        account = tx.account or cls._default_account()
        if account is not None:
            if was_voided:
                cls._apply_account_balance(account, row["amount"], direction=1)
            elif old_amount != row["amount"]:
                cls._apply_account_balance(account, row["amount"] - old_amount, direction=1)
        return tx

    @classmethod
    def _void_payment(cls, tx, user):
        """حذف نرم پرداخت با اصلاح تراز حساب."""
        account = tx.account or cls._default_account()
        cls._apply_account_balance(account, tx.amount or 0, direction=-1)

        tx.transaction_status = Transaction.TransactionStatus.VOIDED
        tx.is_voided = True
        tx.voided_at = timezone.now()
        if user is not None:
            tx.voided_by = user
        if not tx.void_reason:
            tx.void_reason = "حذف از بخش ویرایش بیعانه‌ها"
        tx.save()
        return tx

    # ------------------------------------------------------------------
    # سازگاری با داده‌های قدیمی
    # ------------------------------------------------------------------
    @classmethod
    @transaction.atomic
    def materialize_legacy_payments(cls, reservation, user=None):
        """
        مقادیر کش‌شده قدیمی (``deposit_amount`` / ``remaining_payment_amount``)
        که هنوز تراکنش ندارند را به تراکنش واقعی تبدیل می‌کند.

        هر «سطل» مستقل بررسی می‌شود؛ بنابراین ثبت یک پرداخت نهایی جدید باعث
        نادیده گرفته شدن بیعانه قدیمی نمی‌شود. idempotent است.

        خروجی: نگاشت ``{LEGACY_DEPOSIT_ROW_ID: pk, LEGACY_BALANCE_ROW_ID: pk}``
        """
        if reservation is None or reservation.pk is None:
            return {}

        pending = cls.pending_legacy_amounts(reservation)
        if pending["deposit"] <= 0 and pending["balance"] <= 0:
            return {}

        account = cls._default_account()
        creator = user or reservation.created_by
        base_position = cls.next_sequence_number(reservation)
        mapping = {}

        if pending["deposit"] > 0:
            tx = TransactionService.create(
                reservation=reservation,
                transaction_type=Transaction.TransactionType.DEPOSIT,
                amount=pending["deposit"],
                created_by=creator,
                account=account,
                payment_method=reservation.payment_method,
                payment_reference=reservation.payment_tracking_code or "",
                description="بیعانه اول (انتقال از داده قدیمی)",
                transaction_date=_coerce_datetime(
                    getattr(reservation, "created_at", None), timezone.now()
                ),
            )
            Transaction.objects.filter(pk=tx.pk).update(sequence_number=base_position)
            base_position += 1
            mapping[LEGACY_DEPOSIT_ROW_ID] = tx.pk

        if pending["balance"] > 0:
            tx = TransactionService.create(
                reservation=reservation,
                transaction_type=Transaction.TransactionType.FINAL_PAYMENT,
                amount=pending["balance"],
                created_by=creator,
                account=account,
                payment_method=reservation.remaining_payment_method,
                payment_reference=reservation.remaining_payment_tracking_code or "",
                description="پرداخت نهایی (انتقال از داده قدیمی)",
                transaction_date=_coerce_datetime(
                    getattr(reservation, "remaining_paid_at", None),
                    _coerce_datetime(getattr(reservation, "created_at", None), timezone.now()),
                ),
            )
            Transaction.objects.filter(pk=tx.pk).update(sequence_number=base_position)
            mapping[LEGACY_BALANCE_ROW_ID] = tx.pk

        cls.sync_reservation_payment_caches(reservation, save=True)
        return mapping

    @classmethod
    @transaction.atomic
    def ensure_legacy_deposit_payment(cls, reservation, user=None):
        """
        سازگاری عقب‌رو: مقادیر قدیمی رزرو را (در صورت وجود) به تراکنش تبدیل
        می‌کند و ``True`` برمی‌گرداند اگر چیزی منتقل شده باشد.
        """
        return bool(cls.materialize_legacy_payments(reservation, user))


    @classmethod
    @transaction.atomic
    def backfill_sequence_numbers(cls):
        """
        شماره مرحله (``sequence_number``) را برای تراکنش‌های پرداخت قدیمی
        بر اساس ترتیب تاریخ پر می‌کند. idempotent است.

        فقط پرداخت‌های معتبر (POSTED و حذف‌نشده) شماره‌گذاری می‌شوند تا
        برچسب «بیعانه اول/دوم/...» با شماره‌گذاری رابط کاربری یکسان بماند.
        """
        updated = 0
        reservation_ids = (
            cls.payments_queryset_all()
            .values_list("reservation_id", flat=True)
            .distinct()
        )
        for reservation_id in reservation_ids:
            if reservation_id is None:
                continue
            txs = list(
                Transaction.objects.filter(
                    reservation_id=reservation_id,
                    transaction_type__in=cls.STAGED_TYPES,
                    transaction_status=Transaction.TransactionStatus.POSTED,
                    is_voided=False,
                ).order_by("transaction_date", "pk")
            )
            for position, tx in enumerate(txs, start=1):
                if tx.sequence_number != position:
                    Transaction.objects.filter(pk=tx.pk).update(sequence_number=position)
                    updated += 1
        return updated

    @classmethod
    def payments_queryset_all(cls):
        """تمام تراکنش‌های پرداخت مرحله‌ای (شامل حذف‌شده‌ها) بدون فیلتر رزرو."""
        return Transaction.objects.filter(transaction_type__in=cls.STAGED_TYPES)

