# reservations/models.py
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from customers.models import Customer
from products.models import Dress
from django_jalali.db import models as jmodels


class Reservation(models.Model):

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'پیش‌نویس'
        CONFIRMED = 'CONFIRMED', 'قطعی'
        DELIVERED = 'DELIVERED', 'تحویل شده'
        RETURNED = 'RETURNED', 'بازگشت داده شده'
        LAUNDRY = 'LAUNDRY', 'خشکشویی'
        CANCELED = 'CANCELED', 'لغو شده'

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='reservations'
    )
    dress = models.ForeignKey(
        Dress,
        on_delete=models.PROTECT,
        related_name='reservations'
    )

    rent_days = models.PositiveSmallIntegerField(
        verbose_name='مدت اجاره (روز)'
    )

    rent_date = jmodels.jDateField(verbose_name='تاریخ اجاره')
    ceremony_date = jmodels.jDateField(verbose_name='تاریخ مراسم')
    return_date = jmodels.jDateField(verbose_name='تاریخ تحویل')

    rent_price_snapshot = models.PositiveIntegerField(
        verbose_name='قیمت اجاره لباس (Snapshot)',
        default=0
    )

    total_amount = models.PositiveIntegerField(
        verbose_name='مبلغ اجاره نهایی'
    )

    payment_method = models.CharField(
        max_length=20,
        choices=[
            ('POS', 'پوز'),
            ('CARD', 'کارت به کارت'),
            ('OTHER', 'سایر'),
        ],
        blank=True,
        null=True,
    )

    payment_tracking_code = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    guarantee_type_1 = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )
    guarantee_type_2 = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )
    guarantee_tracking_code = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    deposit_amount = models.PositiveIntegerField(
        verbose_name='بیعانه',
        default=0,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )

    product_condition = models.TextField(
        verbose_name='سلامت کالا',
        blank=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_reservations'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def remaining_amount(self):
        return max(self.total_amount - self.deposit_amount, 0)

    def clean(self):
        errors = {}

        if self.rent_date and self.ceremony_date and self.return_date:
            if not (self.rent_date <= self.ceremony_date <= self.return_date):
                errors['ceremony_date'] = 'ترتیب تاریخ‌ها نامعتبر است.'
                errors['return_date'] = 'تاریخ بازگشت باید بعد از تاریخ مراسم باشد.'

            calculated_days = (self.return_date - self.rent_date).days
            if calculated_days != self.rent_days:
                errors['rent_days'] = 'مدت اجاره با تاریخ‌ها همخوانی ندارد.'

        if self.total_amount <= 0:
            errors['total_amount'] = 'مبلغ کل باید بیشتر از صفر باشد.'

        if self.deposit_amount > self.total_amount:
            errors['deposit_amount'] = 'بیعانه نمی‌تواند از مبلغ کل بیشتر باشد.'

        if self.deposit_amount > 0 and not self.payment_method:
            errors['payment_method'] = 'برای بیعانه، روش پرداخت باید مشخص شود.'

        if self.payment_tracking_code and not self.payment_method:
            errors['payment_method'] = 'بدون روش پرداخت، کد پیگیری معتبر نیست.'

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"رزرو {self.dress} برای {self.customer}"

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['rent_date']),
            models.Index(fields=['return_date']),
            models.Index(fields=['dress', 'status']),
            models.Index(fields=['customer', 'status']),
        ]
