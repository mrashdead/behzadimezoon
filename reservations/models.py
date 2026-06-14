from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from django_jalali.db import models as jmodels


class Reservation(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'پیش‌نویس'
        CONFIRMED = 'confirmed', 'تأییدشده'
        DELIVERED = 'delivered', 'تحویل‌شده'
        RETURNED = 'returned', 'برگشت‌شده'
        LAUNDRY = 'laundry', 'رختشویی'
        CANCELED = 'canceled', 'لغوشده'

    class GuaranteeType(models.TextChoices):
        CHECK = 'check', 'چک'
        CASH = 'cash', 'وجه نقد'
        GOLD = 'gold', 'طلا'
        PROMISSORY_NOTE = 'promissory_note', 'سفته'

    class PaymentMethod(models.TextChoices):
        CASH = 'cash', 'نقدی'
        CARD = 'card', 'کارت به کارت'
        POS = 'pos', 'پوز'
        TRANSFER = 'transfer', 'حواله'

    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.CASCADE,
        related_name='reservations',
        verbose_name='مشتری',
    )

    # اگر مدل واقعی در اپ products اسمش Product است این را Product بگذار
    # اگر واقعاً Dress است، همین Dress را نگه دار
    dress = models.ForeignKey(
        'products.Dress',
        on_delete=models.PROTECT,
        related_name='reservations',
        verbose_name='لباس',
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_reservations',
        verbose_name='ایجادکننده',
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
        verbose_name='وضعیت',
    )

    rent_date = jmodels.jDateField(
        verbose_name='تاریخ اجاره'
    )
    ceremony_date = jmodels.jDateField(
        null=True,
        blank=True,
        verbose_name='تاریخ مراسم'
    )
    return_date = jmodels.jDateField(
        null=True,
        blank=True,
        verbose_name='تاریخ بازگشت'
    )

    rent_days = models.PositiveIntegerField(
        default=1,
        verbose_name='مدت اجاره (روز)'
    )

    rent_price_snapshot = models.PositiveBigIntegerField(
        default=0,
        verbose_name='مبلغ اجاره'
    )
    deposit_amount = models.PositiveBigIntegerField(
        default=0,
        verbose_name='بیعانه'
    )
    discount_amount = models.PositiveBigIntegerField(
        default=0,
        verbose_name='تخفیف'
    )
    extra_charge_amount = models.PositiveBigIntegerField(
        default=0,
        verbose_name='هزینه اضافی'
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        blank=True,
        verbose_name='روش پرداخت'
    )

    guarantee_type = models.CharField(
        max_length=30,
        choices=GuaranteeType.choices,
        blank=True,
        verbose_name='نوع ضمانت'
    )
    guarantee_description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='توضیحات ضمانت'
    )

    notes = models.TextField(
        blank=True,
        verbose_name='توضیحات'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ایجاد'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='آخرین بروزرسانی'
    )

    class Meta:
        verbose_name = 'رزرو'
        verbose_name_plural = 'رزروها'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['rent_date']),
            models.Index(fields=['ceremony_date']),
            models.Index(fields=['return_date']),
        ]

    def __str__(self):
        customer_name = getattr(self.customer, 'name', None) or str(self.customer)
        dress_name = getattr(self.dress, 'name', None) or str(self.dress)
        return f'{customer_name} - {dress_name}'

    @property
    def total_amount(self):
        """
        مبلغ نهایی قابل پرداخت:
        مبلغ پایه - تخفیف + هزینه اضافی
        """
        base = self.rent_price_snapshot or 0
        discount = self.discount_amount or 0
        extra = self.extra_charge_amount or 0
        total = base - discount + extra
        return max(total, 0)

    @property
    def remaining_amount(self):
        """
        مانده پرداختی:
        مبلغ کل - بیعانه
        """
        remaining = self.total_amount - (self.deposit_amount or 0)
        return max(remaining, 0)

    @property
    def is_paid_in_full(self):
        return self.remaining_amount == 0

    @property
    def duration_text(self):
        if self.rent_days == 1:
            return '1 روز'
        return f'{self.rent_days} روز'

    def clean(self):
        errors = {}

        if self.rent_days and self.rent_days < 1:
            errors['rent_days'] = 'مدت اجاره باید حداقل 1 روز باشد.'

        if self.deposit_amount and self.deposit_amount < 0:
            errors['deposit_amount'] = 'مبلغ بیعانه نمی‌تواند منفی باشد.'

        if self.discount_amount and self.discount_amount < 0:
            errors['discount_amount'] = 'مبلغ تخفیف نمی‌تواند منفی باشد.'

        if self.extra_charge_amount and self.extra_charge_amount < 0:
            errors['extra_charge_amount'] = 'هزینه اضافی نمی‌تواند منفی باشد.'

        if self.rent_date and self.return_date and self.return_date < self.rent_date:
            errors['return_date'] = 'تاریخ بازگشت نمی‌تواند قبل از تاریخ اجاره باشد.'

        if self.deposit_amount and self.deposit_amount > self.total_amount:
            errors['deposit_amount'] = 'بیعانه نمی‌تواند از مبلغ کل بیشتر باشد.'

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # اگر تاریخ مراسم خالی است و مشتری این فیلد را دارد، از مشتری بردار
        if not self.ceremony_date and self.customer_id:
            customer_ceremony_date = getattr(self.customer, 'ceremony_date', None)
            if customer_ceremony_date:
                self.ceremony_date = customer_ceremony_date

        # اگر return_date خالی است و rent_date + rent_days داریم، خودکار بساز
        if self.rent_date and self.rent_days and not self.return_date:
            self.return_date = self.rent_date + timedelta(days=self.rent_days)

        # اگر قیمت snapshot خالی است، از لباس بردار
        if (not self.rent_price_snapshot) and self.dress_id:
            dress_price = getattr(self.dress, 'rent_price', None)
            if dress_price is not None:
                self.rent_price_snapshot = dress_price

        self.full_clean()
        super().save(*args, **kwargs)
