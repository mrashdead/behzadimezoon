from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings
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

    # -----------------------
    # وضعیت رزرو
    # -----------------------

    status = models.CharField(
        max_length=20,
        choices=ReservationStatus.CHOICES,
        default=ReservationStatus.DRAFT,
        verbose_name="وضعیت رزرو"
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

    @property
    def gross_rent_price(self):
        return self.rent_price or 0

    @property
    def net_cash_inflow(self):
        return self.total_received_amount() - (self.refunded_amount or 0)

    @property
    def outstanding_balance(self):
        return self.remaining_amount or 0

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

        self.calculate_dates()
        self.calculate_financials()
        self.full_clean()

        super().save(*args, **kwargs)

    @property
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
