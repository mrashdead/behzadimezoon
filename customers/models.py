#customers/models.py

from django.db import models
from django.conf import settings  # برای اتصال به مدل User
from django_jalali.db import models as jmodels # وارد کردن مدل‌های شمسی

class Customer(models.Model):
    # --- فیلدهای ضروری ---
    bride_first_name = models.CharField(
        max_length=50,
        verbose_name="نام عروس"
    )

    bride_last_name = models.CharField(
        max_length=50,
        verbose_name="نام خانوادگی عروس"
    )

    bride_phone = models.CharField(
        max_length=15,
        verbose_name="شماره تماس عروس"
    )

    ceremony_date = jmodels.jDateField(
        verbose_name="تاریخ مراسم"
    )
        # اگر فیلد زمان ثبت (auto_now_add) هم داری:
    # created_at = jmodels.jDateTimeField(
    #     auto_now_add=True, verbose_name='تاریخ ثبت'
    # )

    how_to_know = models.CharField(
        max_length=100,
        verbose_name="نحوه آشنایی"
    )

    city = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="شهر"
    )

    allow_contact = models.BooleanField(
        default=False,
        verbose_name="اجازه ارتباط با شما؟"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        editable=False,
        verbose_name="کاربر ثبت‌کننده"
    )

    # --- فیلدهای اضافی (اختیاری) ---
    groom_first_name = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="نام داماد"
    )

    groom_last_name = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="نام خانوادگی داماد"
    )

    groom_phone = models.CharField(
        max_length=15,
        blank=True,
        verbose_name="شماره تماس داماد"
    )

    requested_services = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="خدمات مورد نظر"
    )

    estimated_budget = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="بودجه تقریبی مدنظر (تومان)"
    )

    additional_services = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="خدمات جانبی مورد نیاز"
    )

    preferred_consultant = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="ترجیح می‌دهم مشاوره من توسط:"
    )

    guest_count = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name="تعداد تقریبی مهمان"
    )

    ceremony_decoration = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="تشریفات"
    )

    beauty_salon = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="اسم سالن زیبایی"
    )

    studio_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="آتلیه"
    )

    music_band = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="گروه موسیقی"
    )

    customer_note = models.TextField(
        blank=True,
        verbose_name="یادداشت مشتری"
    )


    @property
    def how_to_know_option(self):
        if not self.how_to_know:
            return ''
        return self.how_to_know.split(':', 1)[0].strip()

    @property
    def how_to_know_detail(self):
        if not self.how_to_know:
            return ''
        if ':' not in self.how_to_know:
            return ''
        return self.how_to_know.split(':', 1)[1].strip()

    def __str__(self):
        return f"{self.bride_first_name} {self.bride_last_name}"

    class Meta:
        verbose_name = "Customer"
        verbose_name_plural = "Customers"
        ordering = ['ceremony_date']
