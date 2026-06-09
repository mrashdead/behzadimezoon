# reservations/admin.py

from django.contrib import admin, messages
from reservations.models import Reservation
from reservations.constants import ReservationStatus
from reservations.services.change_status import change_reservation_status


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'dress', 'status')
    readonly_fields = ('status',)

    actions = [
        'confirm_reservation',
        'deliver_reservation',
        'return_reservation',
        'send_to_laundry',
        'cancel_reservation',
    ]

    def _change_status(self, request, queryset, new_status, success_msg):
        for reservation in queryset:
            try:
                change_reservation_status(
                    request.user,
                    reservation,
                    new_status
                )
            except Exception as e:
                self.message_user(
                    request,
                    f'رزرو {reservation.id}: {str(e)}',
                    level=messages.ERROR
                )
        self.message_user(request, success_msg, messages.SUCCESS)

    def confirm_reservation(self, request, queryset):
        self._change_status(
            request, queryset,
            ReservationStatus.CONFIRMED,
            'رزروهای انتخاب شده تأیید شدند'
        )

    def deliver_reservation(self, request, queryset):
        self._change_status(
            request, queryset,
            ReservationStatus.DELIVERED,
            'رزروهای انتخاب شده تحویل داده شدند'
        )

    def return_reservation(self, request, queryset):
        self._change_status(
            request, queryset,
            ReservationStatus.RETURNED,
            'رزروهای انتخاب شده بازگردانده شدند'
        )

    def send_to_laundry(self, request, queryset):
        self._change_status(
            request, queryset,
            ReservationStatus.LAUNDRY,
            'رزروهای انتخاب شده به خشکشویی ارسال شدند'
        )

    def cancel_reservation(self, request, queryset):
        self._change_status(
            request, queryset,
            ReservationStatus.CANCELED,
            'رزروهای انتخاب شده لغو شدند'
        )
