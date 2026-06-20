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

    discount_amount = models.PositiveIntegerField(
        default=0,
        verbose_name="تخفیف"
    )

    final_price = models.PositiveIntegerField(
        verbose_name="مبلغ نهایی"
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

    def calculate_financials(self):

        if self.rent_price is None:
            self.rent_price = 0

        self.final_price = self.rent_price - (self.discount_amount or 0)
        if self.final_price < 0:
            self.final_price = 0

        if self.remaining_payment_amount and self.remaining_payment_amount > 0:
            self.remaining_amount = 0
        else:
            self.remaining_amount = self.final_price - (self.deposit_amount or 0)
            if self.remaining_amount < 0:
                self.remaining_amount = 0

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

        # قیمت لباس
        if self.dress:
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
