from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from datetime import timedelta


class Reservation(models.Model):
    GUARANTEE_CHOICES = [
        ('check', 'چک'),
        ('cash', 'پول'),
        ('gold', 'طلا'),
        ('promissory_note', 'سفته'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('cash', 'نقدی'),
        ('card', 'کارت به کارت'),
        ('pos', 'دستگاه کارتخوان'),
        ('transfer', 'حواله'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_RESERVED = 'reserved'
    STATUS_DELIVERED = 'delivered'
    STATUS_RETURNED = 'returned'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'در انتظار'),
        (STATUS_RESERVED, 'رزرو شده'),
        (STATUS_DELIVERED, 'تحویل شده'),
        (STATUS_RETURNED, 'برگشت شده'),
        (STATUS_CANCELLED, 'لغو شده'),
    ]

    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.CASCADE,
        related_name='reservations',
        verbose_name='مشتری'
    )
    dress = models.ForeignKey(
        'products.Dress',
        on_delete=models.CASCADE,
        related_name='reservations',
        verbose_name='لباس'
    )

    rent_days = models.PositiveIntegerField(
        verbose_name='تعداد روز اجاره'
    )
    rent_date = models.DateField(
        verbose_name='تاریخ شروع اجاره'
    )
    ceremony_date = models.DateField(
        blank=True,
        null=True,
        verbose_name='تاریخ مراسم'
    )
    return_date = models.DateField(
        verbose_name='تاریخ تحویل'
    )

    rent_price_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        verbose_name='قیمت اجاره در زمان ثبت'
    )
    deposit_amount = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        verbose_name='مبلغ بیعانه'
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        blank=True,
        null=True,
        verbose_name='روش پرداخت'
    )
    payment_tracking_code = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='کد پیگیری پرداخت'
    )

    guarantee_type_1 = models.CharField(
        max_length=30,
        choices=GUARANTEE_CHOICES,
        verbose_name='ضمانت اول'
    )
    guarantee_1_tracking_code = models.CharField(
        max_length=100,
        verbose_name='کد ضمانت اول'
    )

    guarantee_type_2 = models.CharField(
        max_length=30,
        choices=GUARANTEE_CHOICES,
        blank=True,
        null=True,
        verbose_name='ضمانت دوم'
    )
    guarantee_2_tracking_code = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='کد ضمانت دوم'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        verbose_name='وضعیت'
    )

    description = models.TextField(
        blank=True,
        null=True,
        verbose_name='توضیحات'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'رزرو'
        verbose_name_plural = 'رزروها'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.customer} - {self.dress} - {self.rent_date}"

    def clean(self):
        if self.rent_days <= 0:
            raise ValidationError({'rent_days': 'تعداد روز اجاره باید بیشتر از صفر باشد.'})

        if self.rent_date and self.rent_days:
            calculated_return = self.rent_date + timedelta(days=self.rent_days)
            self.return_date = calculated_return

        if self.deposit_amount and self.rent_price_snapshot:
            if self.deposit_amount > self.rent_price_snapshot:
                raise ValidationError({'deposit_amount': 'مبلغ بیعانه نمی‌تواند بیشتر از مبلغ اجاره باشد.'})

        if self.guarantee_type_1 and not self.guarantee_1_tracking_code:
            raise ValidationError({'guarantee_1_tracking_code': 'کد ضمانت اول اجباری است.'})

        if self.guarantee_type_2 and not self.guarantee_2_tracking_code:
            raise ValidationError({'guarantee_2_tracking_code': 'برای ضمانت دوم، کد پیگیری هم باید وارد شود.'})

        overlapping = Reservation.objects.filter(
            dress=self.dress,
            rent_date__lt=self.return_date,
            return_date__gt=self.rent_date,
        ).exclude(
            status='cancelled'
        )

        if self.pk:
            overlapping = overlapping.exclude(pk=self.pk)

        if overlapping.exists():
            raise ValidationError({'dress': 'این لباس در این بازه زمانی قبلاً رزرو شده است.'})

    def save(self, *args, **kwargs):
        if self.rent_date and self.rent_days:
            self.return_date = self.rent_date + timedelta(days=self.rent_days)

        if self.dress and hasattr(self.dress, 'rent_price'):
            self.rent_price_snapshot = self.dress.rent_price

        if self.customer and hasattr(self.customer, 'ceremony_date'):
            self.ceremony_date = self.customer.ceremony_date

        self.full_clean()
        super().save(*args, **kwargs)
