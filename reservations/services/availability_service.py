# reservations/services/availability_service.py

from datetime import timedelta
from django.db.models import Q

from reservations.models import Reservation
from reservations.constants import ReservationStatus


class ReservationAvailabilityService:

    @staticmethod
    def calculate_end_date(start_date, rental_days):
        """
        محاسبه تاریخ پایان رزرو
        """
        return start_date + timedelta(days=rental_days)


    @staticmethod
    def get_blocking_statuses():
        """
        وضعیت‌هایی که باعث قفل بودن لباس می‌شوند
        """
        return [
            ReservationStatus.CONFIRMED,
            ReservationStatus.DELIVERED,
            ReservationStatus.RETURNED,
            ReservationStatus.LAUNDRY,
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

        # بررسی تداخل بازه‌ها
        overlap = reservations.filter(
            Q(start_date__lt=end_date) &
            Q(end_date__gt=start_date)
        ).exists()

        return not overlap, end_date
