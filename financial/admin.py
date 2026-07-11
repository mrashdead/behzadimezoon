# financial/admin.py

from django.contrib import admin
from django.utils import timezone
from django.contrib.auth import get_user_model
from jalali_date.admin import ModelAdminJalaliMixin

from .models import (
    # Legacy models (to be kept/modified)
    Transaction, Guarantee, DamageRecord, CancellationRecord,
    # New models
    FinancialAccount, TransactionCategory, PaymentAllocation, ReconciliationEntry
)

User = get_user_model()


@admin.register(FinancialAccount)
class FinancialAccountAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = ['code', 'name', 'account_type', 'balance', 'is_active']
    list_filter = ['account_type', 'is_active']
    search_fields = ['code', 'name', 'description']
    readonly_fields = ['created_at']

    fieldsets = (
        (None, {'fields': ('code', 'name', 'account_type')}),
        ('جزئیات', {'fields': ('description', 'is_active', 'parent_account')}),
        ('موجودی', {'fields': ('balance',)}),
    )


@admin.register(TransactionCategory)
class TransactionCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'category_type', 'icon', 'color', 'description']
    list_filter = ['category_type']
    search_fields = ['name', 'description']


@admin.register(Transaction)
class TransactionAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = (
        'transaction_number', 'transaction_type', 'transaction_status',
        'amount', 'transaction_date', 'account', 'customer', 'reservation',
        'created_by', 'is_reconciled', 'is_posted'
    )
    list_filter = (
        'transaction_type', 'transaction_status', 'payment_method',
        'transaction_date', 'account', 'category', 'created_by',
        'is_reconciled', 'is_posted'
    )
    search_fields = (
        'transaction_number', 'description', 'notes', 'payment_reference',
        'customer__bride_first_name', 'customer__bride_last_name',
        'reservation__id', 'reservation__contract_number'
    )
    readonly_fields = (
        'transaction_number', 'created_at', 'updated_at',
        'posted_at', 'voided_at', 'created_by', 'approved_by', 'voided_by',
        'transaction_status', 'is_posted', 'is_voided', 'is_reconciled'
    )

    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('transaction_type', 'transaction_status', 'amount', 'currency', 'description', 'notes', 'attachment')
        }),
        ('ارجاع به', {
            'fields': ('reservation', 'customer', 'account', 'category')
        }),
        ('جزئیات پرداخت', {
            'fields': ('payment_method', 'payment_reference', 'receipt_number')
        }),
        ('تاریخ‌ها', {
            'fields': ('transaction_date', 'value_date', 'due_date')
        }),
        ('ربط', {
            'fields': ('related_transaction',)
        }),
        ('مدیریت و حسابداری', {
            'fields': ('created_by', 'approved_by', 'is_reconciled', 'is_posted', 'is_voided', 'posted_at', 'approved_at', 'voided_at', 'voided_by')
        }),
        ('سیستم', {
            'fields': ('transaction_number', 'created_at', 'updated_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        # Assign created_by automatically if creating a new object
        if not obj.pk:
            obj.created_by = request.user

        # Ensure transaction status and dates are handled correctly
        if obj.transaction_status == Transaction.TransactionStatus.POSTED and not obj.posted_at:
            obj.posted_at = timezone.now()
        elif obj.transaction_status == Transaction.TransactionStatus.APPROVED and not obj.approved_at:
            obj.approved_by = request.user
            obj.approved_at = timezone.now()
        elif obj.transaction_status == Transaction.TransactionStatus.VOIDED and not obj.voided_at:
            obj.voided_by = request.user
            obj.voided_at = timezone.now()

        super().save_model(request, obj, form, change)


@admin.register(Guarantee)
class GuaranteeAdmin(admin.ModelAdmin):
    list_display = ('id', 'tracking_code', 'guarantee_type', 'reservation', 'customer', 'status', 'estimated_value', 'received_at', 'returned_at')
    list_filter = ('status', 'guarantee_type', 'received_at')
    search_fields = ('tracking_code', 'customer__bride_first_name', 'customer__bride_last_name', 'reservation__id')


@admin.register(DamageRecord)
class DamageRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'damage_type', 'reservation', 'customer', 'amount', 'collected', 'detected_at')
    list_filter = ('collected', 'damage_type', 'detected_at')
    search_fields = ('damage_type', 'reservation__id', 'payment_reference')


@admin.register(CancellationRecord)
class CancellationRecordAdmin(admin.ModelAdmin):
    list_display = ('reservation', 'cancelled_at', 'refund_amount', 'penalty_amount')
    search_fields = ('reservation__id',)
    readonly_fields = ('cancelled_at',)


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(admin.ModelAdmin):
    list_display = ('payment_transaction', 'reservation', 'allocated_amount', 'allocated_at')
    list_filter = ('allocated_at',)
    search_fields = ('payment_transaction__transaction_number', 'reservation__id')


@admin.register(ReconciliationEntry)
class ReconciliationEntryAdmin(ModelAdminJalaliMixin, admin.ModelAdmin):
    list_display = [
        'reconciliation_date', 'opening_balance', 'closing_balance',
        'difference', 'status', 'resolved_by', 'created_at'
    ]
    list_filter = ['status', 'reconciliation_date']
    search_fields = ['notes', 'reconciliation_date']
    readonly_fields = ['created_at', 'reconciliation_date', 'opening_balance', 'closing_balance', 'difference', 'status', 'resolved_by', 'resolved_at']

    fieldsets = (
        ('اطلاعات هماهنگی', {
            'fields': ('reconciliation_date', 'opening_balance', 'closing_balance', 'difference', 'status', 'notes')
        }),
        ('مدیریت', {
            'fields': ('resolved_by', 'resolved_at')
        }),
        ('سیستم', {
            'fields': ('created_at',)
        })
    )

    actions = ['mark_as_resolved', 'mark_as_ignored']

    def get_readonly_fields(self, request, obj=None):
        # Make fields read-only once reconciliation is done or if user is not admin
        if obj and obj.status != ReconciliationEntry.Status.OPEN:
            return self.readonly_fields + ('reconciliation_date', 'opening_balance', 'closing_balance', 'difference', 'status', 'notes')
        elif request.user.role != User.Role.SUPER_ADMIN:
            return self.readonly_fields + ('reconciliation_date', 'opening_balance', 'closing_balance', 'difference', 'status', 'notes')
        return self.readonly_fields

    def mark_as_resolved(self, request, queryset):
        updated = queryset.update(status=ReconciliationEntry.Status.RESOLVED,
                               resolved_by=request.user, resolved_at=timezone.now())
        self.message_user(request, f'{updated} ورودی علامت‌گذاری شد.')
    mark_as_resolved.short_description = 'علامت‌گذاری به عنوان حل شده'

    def mark_as_ignored(self, request, queryset):
        updated = queryset.update(status=ReconciliationEntry.Status.IGNORED)
        self.message_user(request, f'{updated} ورودی نادیده گرفته شد.')
    mark_as_ignored.short_description = 'نادیده گرفتن'
