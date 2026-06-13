from django.contrib import admin, messages
from reservations.models import Reservation
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
        success_count = 0

        for reservation in queryset:
            try:
                change_reservation_status(request.user, reservation, new_status)
                success_count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f'رزرو {reservation.id}: {str(e)}',
                    level=messages.ERROR
                )

        if success_count:
            self.message_user(
                request,
                f'{success_count} رزرو: {success_msg}',
                messages.SUCCESS
            )

    def confirm_reservation(self, request, queryset):
        self._change_status(
            request,
            queryset,
            Reservation.Status.CONFIRMED,
            'تأیید شدند'
        )

    def deliver_reservation(self, request, queryset):
        self._change_status(
            request,
            queryset,
            Reservation.Status.DELIVERED,
            'تحویل داده شدند'
        )

    def return_reservation(self, request, queryset):
        self._change_status(
            request,
            queryset,
            Reservation.Status.RETURNED,
            'بازگردانده شدند'
        )

    def send_to_laundry(self, request, queryset):
        self._change_status(
            request,
            queryset,
            Reservation.Status.LAUNDRY,
            'به خشکشویی ارسال شدند'
        )

    def cancel_reservation(self, request, queryset):
        self._change_status(
            request,
            queryset,
            Reservation.Status.CANCELED,
            'لغو شدند'
        )
