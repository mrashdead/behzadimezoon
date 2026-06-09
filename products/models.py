#products/models.py

from django.db import models


class Dress(models.Model):
    STATUS_CHOICES = (
        ('ACTIVE', 'فعال'),
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
        default='ACTIVE',
        editable=False
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code
