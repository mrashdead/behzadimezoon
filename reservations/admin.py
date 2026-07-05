from django.contrib import admin

from .models import Reservation

from financial.models import Guarantee, DamageRecord


class GuaranteeInline(admin.TabularInline):
    model = Guarantee
    extra = 0
    readonly_fields = ('received_at', 'returned_at')


class DamageInline(admin.TabularInline):
    model = DamageRecord
    extra = 0
    readonly_fields = ('detected_at',)


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'dress', 'start_date', 'end_date', 'status', 'payment_status', 'created_by')
    list_filter = ('status', 'payment_status', 'start_date')
    search_fields = ('customer__bride_first_name', 'customer__bride_last_name', 'dress__code')
    inlines = [GuaranteeInline, DamageInline]
