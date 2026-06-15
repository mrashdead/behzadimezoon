#products/models.py
import jdatetime
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

    @property
    def is_currently_rented(self):
        from reservations.models import Reservation
        from reservations.services.availability_service import ReservationAvailabilityService

        today = jdatetime.date.today()
        blocking_statuses = ReservationAvailabilityService.get_blocking_statuses()

        return Reservation.objects.filter(
            dress=self,
            status__in=blocking_statuses,
            start_date__lte=today,
            end_date__gt=today
        ).exists()

    @property
    def availability_label(self):
        if self.is_currently_rented:
            return 'در اجاره'
        return self.get_status_display()

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
