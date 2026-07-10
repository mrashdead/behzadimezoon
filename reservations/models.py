from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from django_jalali.db import models as jmodels

from customers.models import Customer
from products.models import Dress

from .constants import ReservationStatus, GuaranteeType, PaymentMethod
from .services.state_machin import ReservationStateMachine


User = settings.AUTH_USER_MODEL


class Reservation(models.Model):

    # -----------------------
    # روابط اصلی
    # -----------------------

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="reservations",
        verbose_name="مشتری"
    )

    dress = models.ForeignKey(
        Dress,
        on_delete=models.PROTECT,
        related_name="reservations",
        verbose_name="لباس"
    )

    # -----------------------
    # اطلاعات زمانی رزرو
    # -----------------------

    start_date = jmodels.jDateField(
        verbose_name="تاریخ شروع اجاره"
    )

    rental_days = models.PositiveIntegerField(
        verbose_name="مدت اجاره (روز)"
    )

    end_date = jmodels.jDateField(
        editable=False,
        verbose_name="تاریخ بازگشت"
    )

    delivery_date = jmodels.jDateField(
        editable=False,
        null=True,
        blank=True,
        verbose_name="تاریخ تحویل لباس"
    )

    event_date = jmodels.jDateField(
        null=True,
        blank=True,
        verbose_name="تاریخ مراسم"
    )

    returned_at = jmodels.jDateField(
        null=True,
        blank=True,
        verbose_name="تاریخ واقعی بازگشت"
    )

    # -----------------------
    # اطلاعات مالی
    # -----------------------

    rent_price = models.PositiveIntegerField(
        verbose_name="هزینه اجاره لباس"
    )

    deposit_amount = models.PositiveIntegerField(
        verbose_name="بیعانه"
    )

    DISCOUNT_NONE = 'NONE'
    DISCOUNT_AMOUNT = 'AMOUNT'
    DISCOUNT_PERCENT = 'PERCENT'

    DISCOUNT_TYPE_CHOICES = (
        (DISCOUNT_NONE, 'بدون تخفیف'),
        (DISCOUNT_AMOUNT, 'مبلغ ثابت'),
        (DISCOUNT_PERCENT, 'درصد'),
    )

    discount_type = models.CharField(
        max_length=10,
        choices=DISCOUNT_TYPE_CHOICES,
        default=DISCOUNT_NONE,
        verbose_name="نوع تخفیف"
    )

    discount_value = models.PositiveIntegerField(
        default=0,
        verbose_name="مقدار تخفیف"
    )

    discount_amount = models.PositiveIntegerField(
        default=0,
        verbose_name="مبلغ تخفیف"
    )

    final_price = models.PositiveIntegerField(
        verbose_name="مبلغ نهایی"
    )

    refunded_amount = models.PositiveIntegerField(
        default=0,
        verbose_name="مبلغ مرجوعی"
    )

    remaining_amount = models.PositiveIntegerField(
        verbose_name="باقی مانده"
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.CHOICES,
        verbose_name="روش پرداخت"
    )

    payment_tracking_code = models.CharField(
        max_length=100,
        verbose_name="کد رهگیری پرداخت"
    )

    remaining_payment_amount = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="مبلغ پرداخت باقی‌مانده"
    )

    remaining_payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.CHOICES,
        null=True,
        blank=True,
        verbose_name="روش پرداخت باقی‌مانده"
    )

    remaining_payment_tracking_code = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="کد رهگیری پرداخت باقی‌مانده"
    )

    remaining_paid_at = jmodels.jDateTimeField(
        null=True,
        blank=True,
        verbose_name="تاریخ پرداخت باقی‌مانده"
    )

    tailor_name = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name="نام خیاط"
    )

    # -----------------------
    # ضمانت ها
    # -----------------------

    guarantee1_type = models.CharField(
        max_length=20,
        choices=GuaranteeType.CHOICES,
        verbose_name="نوع ضمانت اول"
    )

    guarantee1_tracking_code = models.CharField(
        max_length=100,
        verbose_name="کد رهگیری ضمانت اول"
    )

    guarantee1_payee = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="در وجه ضمانت اول"
    )

    guarantee2_type = models.CharField(
        max_length=20,
        choices=GuaranteeType.CHOICES,
        null=True,
        blank=True,
        verbose_name="نوع ضمانت دوم"
    )

    guarantee2_tracking_code = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="کد رهگیری ضمانت دوم"
    )

    guarantee2_payee = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="در وجه ضمانت دوم"
    )

    # -----------------------
    # وضعیت رزرو
    # -----------------------

    status = models.CharField(
        max_length=20,
        choices=ReservationStatus.CHOICES,
        default=ReservationStatus.DRAFT,
        verbose_name="وضعیت رزرو"
    )

    previous_status = models.CharField(
        max_length=20,
        choices=ReservationStatus.CHOICES,
        null=True,
        blank=True,
        verbose_name="وضعیت قبلی"
    )

    # Payment status is separate from reservation status and is important
    # for financial auditing and queries.
    PAYMENT_UNPAID = 'UNPAID'
    PAYMENT_PARTIAL = 'PARTIAL'
    PAYMENT_PAID = 'PAID'
    PAYMENT_REFUNDED = 'REFUNDED'

    PAYMENT_STATUS_CHOICES = (
        (PAYMENT_UNPAID, 'پرداخت نشده'),
        (PAYMENT_PARTIAL, 'پرداخت جزئی'),
        (PAYMENT_PAID, 'پرداخت شده'),
        (PAYMENT_REFUNDED, 'پرداخت برگشتی'),
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_UNPAID,
        verbose_name="وضعیت پرداخت"
    )

    # -----------------------
    # اطلاعات مدیریتی
    # -----------------------

    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_reservations",
        verbose_name="ثبت کننده"
    )

    updated_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="updated_reservations",
        null=True,
        blank=True,
        verbose_name="ویرایش کننده"
    )

    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name="تاریخ ایجاد"
    )

    updated_at = jmodels.jDateTimeField(
        auto_now=True,
        verbose_name="آخرین ویرایش"
    )

    # Soft-delete flag (non-destructive)
    is_deleted = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="حذف نرم"
    )

    cancelled_at = jmodels.jDateTimeField(
        null=True,
        blank=True,
        verbose_name="تاریخ لغو"
    )

    archived_at = jmodels.jDateTimeField(
        null=True,
        blank=True,
        verbose_name="تاریخ آرشیو"
    )

    archived_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="archived_reservations",
        verbose_name="آرشیو کننده"
    )

    cancellation_fee = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="جریمه لغو"
    )

    notes = models.TextField(
        blank=True,
        verbose_name="یادداشت"
    )

    # -----------------------
    # اطلاعات خسارت و آسیب
    # -----------------------

    item_damaged = models.BooleanField(
        default=False,
        verbose_name="آیا لباس آسیب‌دیده است؟"
    )

    damage_amount = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="مبلغ خسارت"
    )

    damage_notes = models.TextField(
        blank=True,
        verbose_name="توضیحات خسارت"
    )

    # -----------------------
    # اطلاعات پرداخت جریمه‌ها
    # -----------------------

    cancellation_fee_paid_amount = models.PositiveIntegerField(
        default=0,
        verbose_name="مبلغ پرداخت شده جریمه لغو"
    )

    cancellation_fee_payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.CHOICES,
        null=True,
        blank=True,
        verbose_name="روش پرداخت جریمه لغو"
    )

    cancellation_fee_tracking_code = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="کد رهگیری پرداخت جریمه لغو"
    )

    cancellation_fee_paid_at = jmodels.jDateTimeField(
        null=True,
        blank=True,
        verbose_name="زمان پرداخت جریمه لغو"
    )

    damage_fee_paid_amount = models.PositiveIntegerField(
        default=0,
        verbose_name="مبلغ پرداخت شده جریمه خسارت"
    )

    damage_fee_payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.CHOICES,
        null=True,
        blank=True,
        verbose_name="روش پرداخت جریمه خسارت"
    )

    damage_fee_tracking_code = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="کد رهگیری پرداخت جریمه خسارت"
    )

    damage_fee_paid_at = jmodels.jDateTimeField(
        null=True,
        blank=True,
        verbose_name="زمان پرداخت جریمه خسارت"
    )

    # -----------------------
    # Snapshot Fields (for historical audit & immutability)
    # -----------------------

    dress_daily_price_snapshot = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="قیمت روزانه لباس در زمان رزرو (snapshot)",
        help_text="Immutable snapshot of dress.daily_rent_price at time of reservation creation"
    )

    customer_phone_snapshot = models.CharField(
        max_length=15,
        blank=True,
        verbose_name="شماره تماس عروس در زمان رزرو (snapshot)",
        help_text="Snapshot of customer phone for historical audit"
    )

    financial_snapshot = models.JSONField(
        null=True,
        blank=True,
        verbose_name="snapshot مالی رزرو",
        help_text="JSON snapshot of financial state captured at key events (deposit, balance, return, etc.)"
    )

    total_cash_collected_snapshot = models.PositiveIntegerField(
        default=0,
        verbose_name="کل نقد دریافت شده (snapshot)",
        help_text="Snapshot of total cash collected: deposit + remaining_payment - refunds"
    )

    # -----------------------
    # متدهای محاسباتی
    # -----------------------

    def calculate_dates(self):
        """Calculate return and delivery dates for the reservation."""

        if self.start_date and self.rental_days:
            self.end_date = self.start_date + timedelta(days=self.rental_days)

        if self.start_date:
            self.delivery_date = self.start_date - timedelta(days=1)

    @property
    def return_date(self):
        return self.end_date

    def calculate_discount_amount(self):
        if self.discount_type == self.DISCOUNT_AMOUNT:
            return self.discount_value or 0

        if self.discount_type == self.DISCOUNT_PERCENT:
            percent = self.discount_value or 0
            discount = (self.rent_price * percent) // 100
            return min(discount, self.rent_price)

        return 0

    def calculate_financials(self):

        if self.rent_price is None:
            self.rent_price = 0

        self.discount_amount = self.calculate_discount_amount()
        self.final_price = self.rent_price - self.discount_amount
        if self.final_price < 0:
            self.final_price = 0

        if self.remaining_payment_amount and self.remaining_payment_amount > 0:
            self.remaining_amount = 0
        else:
            self.remaining_amount = self.final_price - (self.deposit_amount or 0)
            if self.remaining_amount < 0:
                self.remaining_amount = 0

    def total_received_amount(self):
        return (self.deposit_amount or 0) + (self.remaining_payment_amount or 0)

    def active_additional_fees(self):
        if self._state.adding or self.pk is None:
            from .models import AdditionalFee
            return AdditionalFee.objects.none()
        return self.additional_fees.filter(is_deleted=False)

    def total_additional_fees(self):
        """Calculate total of all additional fees for this reservation."""
        from django.db.models import Sum
        result = self.active_additional_fees().aggregate(total=Sum('amount'))
        return result['total'] or 0

    def remaining_amount_with_fees(self):
        """Calculate remaining amount including additional fees."""
        base_remaining = self.remaining_amount or 0
        total_fees = self.total_additional_fees()
        return base_remaining + total_fees

    @property
    def gross_rent_price(self):
        return self.rent_price or 0

    @property
    def net_cash_inflow(self):
        return self.total_received_amount() - (self.refunded_amount or 0)

    @property
    def outstanding_balance(self):
        return self.remaining_amount or 0

    def has_financial_activity(self):
        return any(
            [
                (self.deposit_amount or 0) > 0,
                (self.remaining_payment_amount or 0) > 0,
                (self.refunded_amount or 0) > 0,
                (self.damage_amount or 0) > 0,
            ]
        )

    def can_be_permanently_deleted(self):
        # If reservation has any on-record financial activity, block permanent deletion.
        if self.has_financial_activity():
            return False

        # Also block permanent deletion if any related financial Transaction records exist.
        # financial.Transaction defines related_name='transactions'.
        try:
            if hasattr(self, 'transactions') and self.transactions.exists():
                return False
        except Exception:
            # Be conservative: if we can't verify, do not allow permanent deletion.
            return False

        return True

    def clean(self):
        if self.discount_amount is None:
            self.discount_amount = 0

        if self.rent_price is None:
            return

        final_price = self.rent_price - (self.discount_amount or 0)
        if final_price < 0:
            final_price = 0

        deposit = self.deposit_amount or 0

        if deposit < 0:
            raise ValidationError({
                "deposit_amount": "بیعانه نمی‌تواند منفی باشد."
            })

        if deposit > final_price:
            raise ValidationError({
                "deposit_amount": "بیعانه نمی‌تواند بیشتر از هزینه نهایی اجاره باشد."
            })

    def save(self, *args, **kwargs):

        # قیمت پایه رزرو را در زمان ثبت یا تغییر رشته/مدت ثبت می‌کنیم.
        # Set rent_price to the base product price (do not multiply by rental days)
        if self.dress:
            if self._state.adding or self.rent_price is None or self.rent_price == 0:
                self.rent_price = self.dress.daily_rent_price
                # Capture snapshot of dress price at creation time
                self.dress_daily_price_snapshot = self.dress.daily_rent_price
            elif self.pk:
                original = Reservation.objects.filter(pk=self.pk).values(
                    'dress_id', 'rental_days'
                ).first()
                if original and original['dress_id'] != self.dress_id:
                    # If the selected dress changed, update to the new dress base price
                    self.rent_price = self.dress.daily_rent_price

        # تاریخ مراسم از مشتری
        if self.customer and not self.event_date:
            self.event_date = getattr(self.customer, "ceremony_date", None)
            # Capture snapshot of customer phone at creation time
            if self._state.adding:
                self.customer_phone_snapshot = getattr(self.customer, "bride_phone", "")

        self.calculate_dates()
        self.calculate_financials()

        # Update snapshot of collected cash
        self.total_cash_collected_snapshot = self.total_received_amount()

        self.full_clean()

        super().save(*args, **kwargs)

    # -----------------------
    # Financial Query Methods
    # -----------------------

    def get_price_snapshot_for_audit(self):
        """Return immutable pricing snapshot for audit trail."""
        return {
            'dress_id': self.dress_id,
            'dress_daily_price_snapshot': self.dress_daily_price_snapshot,
            'rent_price': self.rent_price,
            'discount_type': self.discount_type,
            'discount_value': self.discount_value,
            'discount_amount': self.discount_amount,
            'final_price': self.final_price,
        }

    def get_payment_snapshot_for_audit(self):
        """Return immutable payment snapshot for audit trail."""
        return {
            'deposit_amount': self.deposit_amount,
            'remaining_payment_amount': self.remaining_payment_amount,
            'refunded_amount': self.refunded_amount,
            'damage_amount': self.damage_amount,
            'cancellation_fee': self.cancellation_fee,
            'total_cash_collected': self.total_received_amount(),
            'outstanding_balance': self.outstanding_balance,
        }

    def capture_financial_snapshot(self, event_type):
        """Capture complete financial snapshot at key event."""
        self.financial_snapshot = {
            'event_type': event_type,
            'captured_at': str(timezone.now()),
            'status': self.status,
            'payment_status': self.payment_status,
            'pricing': self.get_price_snapshot_for_audit(),
            'payments': self.get_payment_snapshot_for_audit(),
        }

    def is_fully_paid(self):
        """Check if all amounts due (including damages) have been collected."""
        total_due = self.final_price + (self.damage_amount or 0) + (self.cancellation_fee or 0)
        total_collected = self.total_received_amount()
        return total_collected >= total_due

    def is_partially_paid(self):
        """Check if some payment has been received but not all."""
        collected = self.total_received_amount()
        return 0 < collected < (self.final_price + (self.damage_amount or 0))

    def is_unpaid(self):
        """Check if no payment has been received."""
        return self.total_received_amount() == 0

    def calculate_remaining_due(self):
        """Calculate total amount still owed."""
        total_due = self.final_price + (self.damage_amount or 0) + (self.cancellation_fee or 0)
        total_collected = self.total_received_amount()
        remaining = total_due - total_collected
        return max(remaining, 0)

    # -----------------------
    # Allowable Transitions
    # -----------------------
    def allowed_transitions(self):
        return ReservationStateMachine.TRANSITIONS.get(self.status, [])

    def __str__(self):
        return f"{self.customer} - {self.dress} - {self.start_date}"

    class Meta:
        verbose_name = "رزرو"
        verbose_name_plural = "رزروها"
        ordering = ["-id"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["payment_status"]),
            models.Index(fields=["start_date"]),
            models.Index(fields=["event_date"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["is_deleted"]),
        ]


# Soft-delete aware queryset/manager
class ReservationQuerySet(models.QuerySet):
    def delete(self):
        return self.update(is_deleted=True)

    def hard_delete(self):
        return super().delete()

    def alive(self):
        return self.filter(is_deleted=False)


class ReservationManager(models.Manager):
    def get_queryset(self):
        return ReservationQuerySet(self.model, using=self._db).filter(is_deleted=False)


# attach manager to model dynamically to avoid migration churn when not applied
Reservation.add_to_class('objects', ReservationManager())
Reservation.add_to_class('all_objects', models.Manager())


class ReservationArchiveSnapshot(models.Model):
    original_reservation_id = models.IntegerField(db_index=True)
    data = models.JSONField()
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='reservation_snapshots',
        verbose_name="ایجاد کننده snapshot"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)

    class Meta:
        verbose_name = "نسخه آرشیوی رزرو"
        verbose_name_plural = "نسخه‌های آرشیوی رزرو"
        ordering = ['-created_at']

    def __str__(self):
        return f"Snapshot for reservation {self.original_reservation_id} at {self.created_at}"


class ReservationStatusLog(models.Model):
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name='status_logs'
    )
    old_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    changed_at = jmodels.jDateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ['-changed_at']
        indexes = [models.Index(fields=['changed_at']), models.Index(fields=['reservation'])]

    def __str__(self):
        return f"{self.reservation_id}: {self.old_status} -> {self.new_status} at {self.changed_at}"


class AdditionalFee(models.Model):
    """
    هزینه‌های جانبی/اضافی برای رزرو
    مثل هزینه اتوکشی، تعمیر، لکه‌بری، بسته‌بندی، ارسال و ...
    """

    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name='additional_fees',
        verbose_name="رزرو"
    )

    title = models.CharField(
        max_length=100,
        verbose_name="عنوان هزینه"
    )

    amount = models.PositiveIntegerField(
        verbose_name="مبلغ هزینه"
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_additional_fees',
        verbose_name="ثبت کننده"
    )

    created_at = jmodels.jDateTimeField(
        auto_now_add=True,
        verbose_name="تاریخ ثبت"
    )

    notes = models.TextField(
        blank=True,
        verbose_name="یادداشت"
    )

    is_deleted = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="حذف نرم"
    )

    class Meta:
        verbose_name = "هزینه جانبی"
        verbose_name_plural = "هزینه‌های جانبی"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['reservation']),
            models.Index(fields=['created_at']),
            models.Index(fields=['is_deleted']),
        ]

    def __str__(self):
        return f"{self.title} - {self.amount} تومان ({self.reservation_id})"
