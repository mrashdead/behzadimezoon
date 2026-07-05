from django.contrib import admin

from .models import Transaction, Guarantee, DamageRecord, CancellationRecord


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
	list_display = ('id', 'type', 'amount', 'transaction_date', 'reservation', 'created_by')
	list_filter = ('type', 'category', 'payment_method', 'transaction_date')
	search_fields = ('reservation__pk', 'external_reference', 'note', 'created_by__username', 'created_by__email')
	readonly_fields = ('created_at', 'reservation_snapshot')
	date_hierarchy = 'transaction_date'


@admin.register(Guarantee)
class GuaranteeAdmin(admin.ModelAdmin):
	list_display = ('id', 'tracking_code', 'guarantee_type', 'reservation', 'customer', 'status', 'estimated_value', 'received_at', 'returned_at')
	list_filter = ('status', 'guarantee_type', 'received_at')
	search_fields = ('tracking_code', 'customer__first_name', 'customer__last_name', 'reservation__pk')


@admin.register(DamageRecord)
class DamageRecordAdmin(admin.ModelAdmin):
	list_display = ('id', 'damage_type', 'reservation', 'customer', 'amount', 'collected', 'detected_at')
	list_filter = ('collected', 'damage_type', 'detected_at')
	search_fields = ('damage_type', 'reservation__pk', 'payment_reference')


@admin.register(CancellationRecord)
class CancellationRecordAdmin(admin.ModelAdmin):
	list_display = ('reservation', 'cancelled_at', 'refund_amount', 'penalty_amount')
	search_fields = ('reservation__pk',)
	readonly_fields = ('cancelled_at',)

