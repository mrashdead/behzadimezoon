#products/models.py
from django.db import models


class Dress(models.Model):
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_CHOICES = (
        (STATUS_ACTIVE, 'فعال'),
    )

    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='کد لباس'
    )

    daily_rent_price = models.PositiveIntegerField(
        verbose_name='قیمت اجاره روزانه (تومان)'
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        editable=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='تاریخ ثبت'
    )

    class Meta:
        verbose_name = 'لباس'
        verbose_name_plural = 'لباس‌ها'
        ordering = ['-id']

    def __str__(self):
        return self.code

# from django.db import models


# class Dress(models.Model):
#     STATUS_CHOICES = (
#         ('ACTIVE', 'فعال'),
#     )

#     code = models.CharField(
#         max_length=50,
#         unique=True,
#         verbose_name='کد لباس'
#     )

#     daily_rent_price = models.PositiveIntegerField(
#         verbose_name='قیمت اجاره روزانه (تومان)'
#     )

#     status = models.CharField(
#         max_length=10,
#         choices=STATUS_CHOICES,
#         default='ACTIVE',
#         editable=False
#     )

#     created_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return self.code
