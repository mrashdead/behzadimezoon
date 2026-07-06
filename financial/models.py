from django.conf import settings
from django.db import models
from django.utils import timezone

from reservations.constants import PaymentMethod


class TransactionQuerySet(models.QuerySet):
    def cash_in(self):
        return self.filter(type__in=[
            self.model.Type.PAYMENT,
            self.model.Type.DEPOSIT,
            self.model.Type.FINAL_PAYMENT,
            self.model.Type.DAMAGE_PAYMENT,
        ])

    def cash_out(self):
        return self.filter(type__in=[
            self.model.Type.REFUND,
        ])

    def accrual(self):
        return self.filter(category=self.model.Category.ACCRUAL)

    def receivable(self):
        return self.filter(type__in=[
            self.model.Type.DAMAGE_CHARGE,
            self.model.Type.CANCELLATION_FEE,
        ])

    def for_reservation(self, reservation):
        return self.filter(reservation=reservation)


class TransactionManager(models.Manager.from_queryset(TransactionQuerySet)):
    pass


class Transaction(models.Model):
    class Type(models.TextChoices):
        PAYMENT = 'PAYMENT', 'پرداخت'
        DEPOSIT = 'DEPOSIT', 'بیعانه'
        FINAL_PAYMENT = 'FINAL_PAYMENT', 'پرداخت نهایی'
        REFUND = 'REFUND', 'بازپرداخت'
        DAMAGE_CHARGE = 'DAMAGE_CHARGE', 'خسارت'
        DAMAGE_PAYMENT = 'DAMAGE_PAYMENT', 'وصول خسارت'
        CANCELLATION_FEE = 'CANCELLATION_FEE', 'جریمه لغو'
        ADJUSTMENT = 'ADJUSTMENT', 'تعدیل دستی'
        DISCOUNT = 'DISCOUNT', 'تخفیف'

    class Category(models.TextChoices):
        CASH = 'CASH', 'نقدی'
        ACCRUAL = 'ACCRUAL', 'تعهدی'

    class PostingStatus(models.TextChoices):
        DRAFT = 'DRAFT', 'پیش‌نویس'
        POSTED = 'POSTED', 'ثبت شده'

    TYPE_CATEGORY_MAP = {
        Type.PAYMENT: Category.CASH,
        Type.DEPOSIT: Category.CASH,
        Type.FINAL_PAYMENT: Category.CASH,
        Type.REFUND: Category.CASH,
        Type.DAMAGE_PAYMENT: Category.CASH,
        Type.DISCOUNT: Category.ACCRUAL,
        Type.DAMAGE_CHARGE: Category.ACCRUAL,
        Type.CANCELLATION_FEE: Category.ACCRUAL,
        Type.ADJUSTMENT: Category.ACCRUAL,
    }

    # -----------------------
    # References
    # -----------------------

    reservation = models.ForeignKey(
        'reservations.Reservation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
        verbose_name='رزرو'
    )

    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
        verbose_name='مشتری',
        help_text='Direct customer link for traceability'
    )

    # -----------------------
    # Transaction Data
    # -----------------------

    # store snapshot of reservation financials at time of transaction for audit
    reservation_snapshot = models.JSONField(
        null=True,
        blank=True,
        verbose_name='اسنپ‌شات مالی رزرو',
        help_text='Immutable snapshot of reservation financial state at transaction time'
    )

    type = models.CharField(
        max_length=20,
        choices=Type.choices,
        verbose_name='نوع تراکنش'
    )

    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.CASH,
        verbose_name='لایه مالی'
    )

    posting_status = models.CharField(
        max_length=20,
        choices=PostingStatus.choices,
        default=PostingStatus.POSTED,
        verbose_name='وضعیت ثبت',
        help_text='DRAFT=tentative, POSTED=final; affects balance calculations'
    )

    amount = models.BigIntegerField(verbose_name='مبلغ')

    transaction_date = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        verbose_name='تاریخ تراکنش'
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.CHOICES,
        null=True,
        blank=True,
        verbose_name='روش پرداخت'
    )

    external_reference = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name='ارجاع خارجی'
    )

    sequence_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name='شماره ترتیب',
        help_text='Sequential number for journal ordering; auto-assigned on posting'
    )

    related_transaction = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='related_transactions',
        verbose_name='تراکنش مرتبط',
        help_text='Links paired transactions (e.g., payment to refund)'
    )

    is_immutable = models.BooleanField(
        default=False,
        verbose_name='ناپذیر تغییر',
        help_text='If True, cannot be edited; only reversals allowed'
    )

    # -----------------------
    # Metadata
    # -----------------------

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='transactions',
        verbose_name='ثبت کننده'
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='ایجاد شده در')

    note = models.TextField(blank=True, verbose_name='یادداشت')

    objects = TransactionManager()

    class Meta:
        ordering = ['-transaction_date', '-created_at']
        indexes = [
            models.Index(fields=['type']),
            models.Index(fields=['category']),
            models.Index(fields=['transaction_date']),
            models.Index(fields=['reservation']),
            models.Index(fields=['payment_method']),
            models.Index(fields=['customer']),
            models.Index(fields=['posting_status']),
        ]

    def save(self, *args, **kwargs):
        # Prevent editing immutable transactions
        if self.pk and self.is_immutable:
            raise ValueError("This transaction is immutable and cannot be edited.")
        
        self.category = self.TYPE_CATEGORY_MAP.get(self.type, self.category or self.Category.CASH)
        # capture reservation snapshot if available and not already set
        if self.reservation_id and self.reservation_snapshot is None:
            try:
                res = self.reservation
                self.reservation_snapshot = {
                    'deposit_amount': getattr(res, 'deposit_amount', None),
                    'remaining_payment_amount': getattr(res, 'remaining_payment_amount', None),
                    'refunded_amount': getattr(res, 'refunded_amount', None),
                    'damage_amount': getattr(res, 'damage_amount', None),
                    'final_price': getattr(res, 'final_price', None),
                    'discount_amount': getattr(res, 'discount_amount', None),
                }
            except Exception:
                pass
        
        # Auto-link customer from reservation if not explicitly set
        if self.reservation_id and not self.customer_id:
            try:
                self.customer = self.reservation.customer
            except Exception:
                pass
        
        super().save(*args, **kwargs)

    # -----------------------
    # Query Methods
    # -----------------------

    @property
    def signed_amount(self):
        """Return amount with sign: negative for refunds/discounts, positive for inflows."""
        if self.type == self.Type.REFUND or self.type == self.Type.DISCOUNT:
            return -(self.amount or 0)
        return self.amount or 0

    @property
    def is_cash(self):
        """Check if this is a cash transaction."""
        return self.category == self.Category.CASH

    @property
    def is_posted(self):
        """Check if transaction is posted (affects balances)."""
        return self.posting_status == self.PostingStatus.POSTED

    @property
    def is_inflow(self):
        """Check if this is a cash inflow (collection)."""
        return self.type in [
            self.Type.PAYMENT,
            self.Type.DEPOSIT,
            self.Type.FINAL_PAYMENT,
            self.Type.DAMAGE_PAYMENT,
        ]

    @property
    def is_outflow(self):
        """Check if this is a cash outflow (refund)."""
        return self.type == self.Type.REFUND

    @property
    def is_accrual(self):
        """Check if this is an accrual (not yet paid)."""
        return self.category == self.Category.ACCRUAL

    @property
    def is_reversible(self):
        """Check if transaction can be reversed (not already immutable)."""
        return not self.is_immutable

    @property
    def description(self):
        """Human-readable description of transaction."""
        if self.reservation_id:
            reservation_label = f"رزرو #{self.reservation_id}"
        else:
            reservation_label = "تراکنش بدون رزرو مرتبط"

        if self.type == self.Type.DEPOSIT:
            base = f"بیعانه {reservation_label}"
        elif self.type == self.Type.FINAL_PAYMENT:
            base = f"پرداخت نهایی {reservation_label}"
        elif self.type == self.Type.REFUND:
            base = f"بازپرداخت {reservation_label}"
        elif self.type == self.Type.DAMAGE_CHARGE:
            base = f"خسارت {reservation_label}"
        elif self.type == self.Type.DAMAGE_PAYMENT:
            base = f"وصول خسارت {reservation_label}"
        elif self.type == self.Type.CANCELLATION_FEE:
            base = f"جریمه لغو {reservation_label}"
        elif self.type == self.Type.ADJUSTMENT:
            base = f"تعدیل دستی {reservation_label}"
        elif self.type == self.Type.DISCOUNT:
            base = f"تخفیف {reservation_label}"
        elif self.type == self.Type.PAYMENT:
            base = f"پرداخت {reservation_label}"
        else:
            base = f"{self.get_type_display()} {reservation_label}"

        if self.note:
            return f"{base} — {self.note}"
        return base
        if self.reservation_id:
            reservation_label = f"رزرو #{self.reservation_id}"
        else:
            reservation_label = "تراکنش بدون رزرو مرتبط"

        if self.type == self.Type.DEPOSIT:
            base = f"بیعانه {reservation_label}"
        elif self.type == self.Type.FINAL_PAYMENT:
            base = f"پرداخت نهایی {reservation_label}"
        elif self.type == self.Type.REFUND:
            base = f"بازپرداخت {reservation_label}"
        elif self.type == self.Type.DAMAGE_CHARGE:
            base = f"خسارت {reservation_label}"
        elif self.type == self.Type.DAMAGE_PAYMENT:
            base = f"وصول خسارت {reservation_label}"
        elif self.type == self.Type.CANCELLATION_FEE:
            base = f"جریمه لغو {reservation_label}"
        elif self.type == self.Type.ADJUSTMENT:
            base = f"تعدیل دستی {reservation_label}"
        elif self.type == self.Type.DISCOUNT:
            base = f"تخفیف {reservation_label}"
        elif self.type == self.Type.PAYMENT:
            base = f"پرداخت {reservation_label}"
        else:
            base = f"{self.get_type_display()} {reservation_label}"

        if self.note:
            return f"{base} — {self.note}"
        return base

    def __str__(self):
        status_marker = "[DRAFT] " if not self.is_posted else ""
        return f"{status_marker}{self.get_type_display()} {self.amount} تومان ({self.transaction_date:%Y-%m-%d %H:%M})"


class Guarantee(models.Model):
    RECEIVED = 'RECEIVED'
    RETURNED = 'RETURNED'
    FORFEITED = 'FORFEITED'
    STATUS_CHOICES = (
        (RECEIVED, 'دریافت‌شده'),
        (RETURNED, 'بازگردانده‌شده'),
        (FORFEITED, 'حفظ‌شده'),
    )

    # -----------------------
    # References
    # -----------------------

    reservation = models.ForeignKey(
        'reservations.Reservation',
        on_delete=models.CASCADE,
        related_name='guarantees',
        verbose_name='رزرو'
    )

    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.CASCADE,
        related_name='guarantees',
        verbose_name='مشتری'
    )

    dress = models.ForeignKey(
        'products.Dress',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='guarantees',
        verbose_name='لباس',
        help_text='Which dress this guarantee is collateral for'
    )

    # -----------------------
    # Guarantee Details
    # -----------------------

    tracking_code = models.CharField(
        max_length=200,
        verbose_name='کد مرجع'
    )

    guarantee_type = models.CharField(
        max_length=30,
        verbose_name='نوع تضمین'
    )

    description = models.TextField(
        blank=True,
        verbose_name='شرح'
    )

    estimated_value = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name='مبلغ تقریبی'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=RECEIVED,
        verbose_name='وضعیت'
    )

    # -----------------------
    # Timestamps
    # -----------------------

    received_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='دریافت شده در'
    )

    returned_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='بازگردانده شده در'
    )

    refunded_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='تاریخ بازپرداخت وجه',
        help_text='When guarantee value was refunded (if applicable)'
    )

    notes = models.TextField(
        blank=True,
        verbose_name='یادداشت'
    )

    class Meta:
        verbose_name = 'تضمین'
        verbose_name_plural = 'تضمین‌ها'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['received_at']),
        ]

    def __str__(self):
        return f"{self.guarantee_type} {self.tracking_code}"


class DamageRecord(models.Model):
    # -----------------------
    # Severity Levels
    # -----------------------

    SEVERITY_MINOR = 'MINOR'
    SEVERITY_MODERATE = 'MODERATE'
    SEVERITY_SEVERE = 'SEVERE'
    SEVERITY_CHOICES = (
        (SEVERITY_MINOR, 'جزئی'),
        (SEVERITY_MODERATE, 'متوسط'),
        (SEVERITY_SEVERE, 'شدید'),
    )

    # -----------------------
    # Dispute Tracking
    # -----------------------

    DISPUTE_NONE = 'NONE'
    DISPUTE_OPEN = 'OPEN'
    DISPUTE_RESOLVED = 'RESOLVED'
    DISPUTE_STATUS_CHOICES = (
        (DISPUTE_NONE, 'بدون نزاع'),
        (DISPUTE_OPEN, 'نزاع باز'),
        (DISPUTE_RESOLVED, 'حل شده'),
    )

    # -----------------------
    # References
    # -----------------------

    reservation = models.ForeignKey(
        'reservations.Reservation',
        on_delete=models.CASCADE,
        related_name='damage_records',
        verbose_name='رزرو'
    )

    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.CASCADE,
        related_name='damage_records',
        verbose_name='مشتری'
    )

    dress = models.ForeignKey(
        'products.Dress',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='damage_records',
        verbose_name='لباس'
    )

    # -----------------------
    # Damage Details
    # -----------------------

    damage_type = models.CharField(
        max_length=100,
        verbose_name='نوع خسارت'
    )

    description = models.TextField(
        blank=True,
        verbose_name='شرح'
    )

    severity = models.CharField(
        max_length=20,
        choices=SEVERITY_CHOICES,
        null=True,
        blank=True,
        verbose_name='شدت خسارت'
    )

    amount = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name='مبلغ خسارت'
    )

    # -----------------------
    # Collection Status
    # -----------------------

    collected = models.BooleanField(
        default=False,
        verbose_name='پرداخت شده'
    )

    payment_reference = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        verbose_name='کد پیگیری پرداخت'
    )

    related_transaction = models.ForeignKey(
        'financial.Transaction',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='damage_records',
        verbose_name='تراکنش مرتبط'
    )

    # -----------------------
    # Detection & Approval
    # -----------------------

    detected_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='شناسایی در'
    )

    detected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='detected_damages',
        verbose_name='شناسایی شده توسط'
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_damages',
        verbose_name='تایید شده توسط'
    )

    # -----------------------
    # Dispute Workflow
    # -----------------------

    dispute_status = models.CharField(
        max_length=20,
        choices=DISPUTE_STATUS_CHOICES,
        default=DISPUTE_NONE,
        verbose_name='وضعیت نزاع'
    )

    dispute_opened_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='تاریخ باز کردن نزاع'
    )

    dispute_resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='تاریخ حل نزاع'
    )

    dispute_notes = models.TextField(
        blank=True,
        verbose_name='یادداشت نزاع'
    )

    # -----------------------
    # General Notes
    # -----------------------

    notes = models.TextField(
        blank=True,
        verbose_name='یادداشت'
    )

    class Meta:
        verbose_name = 'خسارت'
        verbose_name_plural = 'خسارت‌ها'
        indexes = [
            models.Index(fields=['collected']),
            models.Index(fields=['dispute_status']),
        ]

    def __str__(self):
        return f"خسارت {self.damage_type} رزرو #{self.reservation_id} - {self.amount or 0} (وضعیت نزاع: {self.get_dispute_status_display()})"


class CancellationRecord(models.Model):
    # -----------------------
    # Refund Status
    # -----------------------

    REFUND_REQUESTED = 'REQUESTED'
    REFUND_APPROVED = 'APPROVED'
    REFUND_POSTED = 'POSTED'
    REFUND_COMPLETED = 'COMPLETED'
    REFUND_STATUS_CHOICES = (
        (REFUND_REQUESTED, 'درخواست شده'),
        (REFUND_APPROVED, 'تایید شده'),
        (REFUND_POSTED, 'ثبت شده'),
        (REFUND_COMPLETED, 'تکمیل شده'),
    )

    # -----------------------
    # References
    # -----------------------

    reservation = models.OneToOneField(
        'reservations.Reservation',
        on_delete=models.CASCADE,
        related_name='cancellation_record',
        verbose_name='رزرو'
    )

    # -----------------------
    # Cancellation Details
    # -----------------------

    reason = models.TextField(
        blank=True,
        verbose_name='دلیل لغو'
    )

    cancelled_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ لغو'
    )

    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cancelled_reservations',
        verbose_name='لغو شده توسط'
    )

    # -----------------------
    # Financial Snapshot at Cancellation
    # -----------------------

    deposit_at_cancel = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name='بیعانه در زمان لغو',
        help_text='Snapshot of deposit amount at time of cancellation'
    )

    # -----------------------
    # Refund Workflow
    # -----------------------

    refund_amount = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name='مبلغ بازپرداخت'
    )

    related_transaction = models.ForeignKey(
        'financial.Transaction',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='cancellation_records',
        verbose_name='تراکنش مرتبط'
    )

    refund_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.CHOICES,
        null=True,
        blank=True,
        verbose_name='روش بازپرداخت'
    )

    refund_posted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='تاریخ ثبت بازپرداخت'
    )

    refund_status = models.CharField(
        max_length=20,
        choices=REFUND_STATUS_CHOICES,
        default=REFUND_REQUESTED,
        verbose_name='وضعیت بازپرداخت'
    )

    penalty_amount = models.BigIntegerField(
        null=True,
        blank=True,
        verbose_name='مبلغ جریمه نگه‌داشته‌شده'
    )

    # -----------------------
    # Approval Workflow
    # -----------------------

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_cancellations',
        verbose_name='تایید شده توسط'
    )

    approval_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='تاریخ تایید'
    )

    approval_notes = models.TextField(
        blank=True,
        verbose_name='یادداشت تایید'
    )

    # -----------------------
    # General Notes
    # -----------------------

    notes = models.TextField(
        blank=True,
        verbose_name='یادداشت'
    )

    class Meta:
        verbose_name = 'رکورد لغو'
        verbose_name_plural = 'رکوردهای لغو'
        indexes = [
            models.Index(fields=['refund_status']),
        ]

    def __str__(self):
        return f"لغو رزرو #{self.reservation_id} — بازپرداخت: {self.refund_amount or 0} — جریمه: {self.penalty_amount or 0} (وضعیت: {self.get_refund_status_display()})"
