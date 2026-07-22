# reservations/services/availability_service.py

from datetime import timedelta
from django.db.models import Q

from reservations.models import Reservation
from reservations.constants import ReservationStatus


class ReservationAvailabilityService:

    @staticmethod
    def calculate_end_date(start_date, rental_days):
        """
        محاسبه تاریخ تحویل/پایان رزرو با فرمول شامل روز اول.
        اگر شروع اجاره 28 باشد و مدت 1 روز باشد، تحویل 28 است.
        """
        if rental_days < 1:
            return start_date
        return start_date + timedelta(days=rental_days - 1)


    @staticmethod
    def get_blocking_statuses():
        """
        وضعیت‌هایی که باعث قفل بودن لباس می‌شوند

        نکته: LAUNDRY (ارسال شده به خشکشویی) یک حالت موقتی است و لباس در این حالت
        می‌تواند دوباره اجاره شود. فقط وضعیت‌های فعال رزرو یا تحویل فیزیکی به مشتری
        باعث قفل شدن لباس می‌شوند.
        """
        return [
            ReservationStatus.CONFIRMED,
            ReservationStatus.DELIVERED,
        ]


    @classmethod
    def is_dress_available(cls, dress, start_date, rental_days, exclude_reservation_id=None):
        """
        بررسی آزاد بودن لباس در بازه زمانی مشخص
        """

        end_date = cls.calculate_end_date(start_date, rental_days)

        blocking_statuses = cls.get_blocking_statuses()

        reservations = Reservation.objects.filter(
            dress=dress,
            status__in=blocking_statuses
        )

        if exclude_reservation_id:
            reservations = reservations.exclude(id=exclude_reservation_id)

        # بررسی تداخل بازه‌ها با بازه بسته شامل روز شروع و روز تحویل.
        overlap = reservations.filter(
            Q(start_date__lte=end_date) &
            Q(end_date__gte=start_date)
        ).exists()

        return not overlap, end_date
