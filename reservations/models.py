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

    # --- مرحله اول ---
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

    # ✅ Price Snapshot (هسته مالی)
    rent_price_snapshot = models.PositiveIntegerField(
        verbose_name='قیمت اجاره لباس (Snapshot)',
        default=0
    )

    total_amount = models.PositiveIntegerField(
        verbose_name='مبلغ اجاره نهایی'
    )

    # --- مرحله دوم ---
    payment_method = models.CharField(
        max_length=20,
        choices=[
            ('POS', 'پوز'),
            ('CARD', 'کارت به کارت'),
            ('OTHER', 'سایر'),
        ]
    )

    payment_tracking_code = models.CharField(
        max_length=100
    )

    guarantee_type_1 = models.CharField(max_length=100)
    guarantee_type_2 = models.CharField(max_length=100, blank=True, null=True)
    guarantee_tracking_code = models.CharField(max_length=100)

    deposit_amount = models.PositiveIntegerField(verbose_name='بیعانه')

    # --- وضعیت ---
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )

    product_condition = models.TextField(
        verbose_name='سلامت کالا'
    )

    # --- سیستمی ---
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_reservations'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    # ==================================================
    # ✅ اعتبارسنجی Business Logic
    # ==================================================
    def clean(self):
        # 1️⃣ ترتیب تاریخ‌ها
        if not (self.rent_date <= self.ceremony_date <= self.return_date):
            raise ValidationError('ترتیب تاریخ‌ها نامعتبر است.')

        # 2️⃣ تطابق مدت اجاره با تاریخ‌ها
        calculated_days = (self.return_date - self.rent_date).days
        if calculated_days != self.rent_days:
            raise ValidationError('مدت اجاره با تاریخ‌ها همخوانی ندارد.')

        # 3️⃣ مبلغ رزرو نباید بعد از ایجاد تغییر کند
        if self.pk:
            original = Reservation.objects.get(pk=self.pk)
            if original.total_amount != self.total_amount:
                raise ValidationError('مبلغ رزرو پس از ثبت قابل تغییر نیست.')

        # 4️⃣ تداخل رزرو
        overlapping = Reservation.objects.filter(
            dress=self.dress,
            status__in=[
                Reservation.Status.DRAFT,
                Reservation.Status.CONFIRMED,
                Reservation.Status.DELIVERED,
            ],
            rent_date__lte=self.return_date,
            return_date__gte=self.rent_date
        ).exclude(pk=self.pk)

        if overlapping.exists():
            raise ValidationError('این لباس در این بازه زمانی رزرو شده است.')

    # ==================================================
    # ✅ Snapshot قیمت فقط هنگام ایجاد
    # ==================================================
    def save(self, *args, **kwargs):
        if not self.pk:
            self.rent_price_snapshot = self.dress.rent_price
            self.total_amount = self.rent_price_snapshot

        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"رزرو {self.dress.code} برای {self.customer}"
