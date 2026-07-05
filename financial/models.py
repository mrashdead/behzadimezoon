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

    reservation = models.ForeignKey(
        'reservations.Reservation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
        verbose_name='رزرو'
    )
    # store snapshot of reservation financials at time of transaction for audit
    reservation_snapshot = models.JSONField(null=True, blank=True, verbose_name='اسنپ‌شات مالی رزرو')
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
    related_transaction = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='related_transactions',
        verbose_name='تراکنش مرتبط'
    )
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
        ]

    def save(self, *args, **kwargs):
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
        super().save(*args, **kwargs)

    @property
    def signed_amount(self):
        if self.type == self.Type.REFUND or self.type == self.Type.DISCOUNT:
            return -(self.amount or 0)
        return self.amount or 0

    @property
    def is_cash(self):
        return self.category == self.Category.CASH

    @property
    def description(self):
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
        return f"{self.get_type_display()} {self.amount} تومان ({self.transaction_date:%Y-%m-%d %H:%M})"


class Guarantee(models.Model):
    RECEIVED = 'RECEIVED'
    RETURNED = 'RETURNED'
    FORFEITED = 'FORFEITED'
    STATUS_CHOICES = (
        (RECEIVED, 'دریافت‌شده'),
        (RETURNED, 'بازگردانده‌شده'),
        (FORFEITED, 'حفظ‌شده'),
    )

    reservation = models.ForeignKey('reservations.Reservation', on_delete=models.CASCADE, related_name='guarantees', verbose_name='رزرو')
    customer = models.ForeignKey('customers.Customer', on_delete=models.CASCADE, related_name='guarantees', verbose_name='مشتری')
    tracking_code = models.CharField(max_length=200, verbose_name='کد مرجع')
    guarantee_type = models.CharField(max_length=30, verbose_name='نوع تضمین')
    description = models.TextField(blank=True, verbose_name='شرح')
    estimated_value = models.BigIntegerField(null=True, blank=True, verbose_name='مبلغ تقریبی')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=RECEIVED, verbose_name='وضعیت')
    received_at = models.DateTimeField(auto_now_add=True, verbose_name='دریافت شده در')
    returned_at = models.DateTimeField(null=True, blank=True, verbose_name='بازگردانده شده در')
    notes = models.TextField(blank=True, verbose_name='یادداشت')

    class Meta:
        verbose_name = 'تضمین'
        verbose_name_plural = 'تضمین‌ها'

    def __str__(self):
        return f"{self.guarantee_type} {self.tracking_code}"


class DamageRecord(models.Model):
    reservation = models.ForeignKey('reservations.Reservation', on_delete=models.CASCADE, related_name='damage_records', verbose_name='رزرو')
    customer = models.ForeignKey('customers.Customer', on_delete=models.CASCADE, related_name='damage_records', verbose_name='مشتری')
    damage_type = models.CharField(max_length=100, verbose_name='نوع خسارت')
    description = models.TextField(blank=True, verbose_name='شرح')
    amount = models.BigIntegerField(null=True, blank=True, verbose_name='مبلغ خسارت')
    detected_at = models.DateTimeField(auto_now_add=True, verbose_name='شناسایی در')
    collected = models.BooleanField(default=False, verbose_name='پرداخت شده')
    payment_reference = models.CharField(max_length=200, null=True, blank=True, verbose_name='کد پیگیری پرداخت')
    notes = models.TextField(blank=True, verbose_name='یادداشت')
    related_transaction = models.ForeignKey('financial.Transaction', null=True, blank=True, on_delete=models.SET_NULL, related_name='+', verbose_name='تراکنش مرتبط')

    class Meta:
        verbose_name = 'خسارت'
        verbose_name_plural = 'خسارت‌ها'

    def __str__(self):
        return f"خسارت {self.damage_type} رزرو #{self.reservation_id} - {self.amount or 0}"


class CancellationRecord(models.Model):
    reservation = models.OneToOneField('reservations.Reservation', on_delete=models.CASCADE, related_name='cancellation_record', verbose_name='رزرو')
    reason = models.TextField(blank=True, verbose_name='دلیل لغو')
    cancelled_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ لغو')
    deposit_at_cancel = models.BigIntegerField(null=True, blank=True, verbose_name='بیعانه در زمان لغو')
    refund_amount = models.BigIntegerField(null=True, blank=True, verbose_name='مبلغ بازپرداخت')
    penalty_amount = models.BigIntegerField(null=True, blank=True, verbose_name='مبلغ جریمه نگه‌داشته‌شده')
    notes = models.TextField(blank=True, verbose_name='یادداشت')

    class Meta:
        verbose_name = 'رکورد لغو'
        verbose_name_plural = 'رکوردهای لغو'

    def __str__(self):
        return f"لغو رزرو #{self.reservation_id} — بازپرداخت: {self.refund_amount or 0} — جریمه: {self.penalty_amount or 0}"
