from django.contrib import admin

from .models import Reservation, AdditionalFee

from financial.models import Guarantee, DamageRecord


class GuaranteeInline(admin.TabularInline):
    model = Guarantee
    extra = 0
    readonly_fields = ('received_at', 'returned_at')


class DamageInline(admin.TabularInline):
    model = DamageRecord
    extra = 0
    readonly_fields = ('detected_at',)


class AdditionalFeeInline(admin.TabularInline):
    model = AdditionalFee
    extra = 0
    readonly_fields = ('created_at', 'created_by')
    fields = ('title', 'amount', 'notes', 'is_deleted', 'created_by', 'created_at')


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'dress', 'start_date', 'end_date', 'status', 'payment_status', 'created_by')
    list_filter = ('status', 'payment_status', 'start_date')
    search_fields = ('customer__bride_first_name', 'customer__bride_last_name', 'dress__code')
    inlines = [GuaranteeInline, DamageInline, AdditionalFeeInline]


@admin.register(AdditionalFee)
class AdditionalFeeAdmin(admin.ModelAdmin):
    list_display = ('id', 'reservation', 'title', 'amount', 'created_by', 'created_at')
    list_filter = ('created_at', 'is_deleted')
    search_fields = ('title', 'reservation__id', 'reservation__customer__bride_first_name')
    readonly_fields = ('created_at', 'created_by')
    fields = ('reservation', 'title', 'amount', 'notes', 'is_deleted', 'created_by', 'created_at')
