from django.contrib import admin
from .models import Customer
from django_jalali.admin.filters import JDateFieldListFilter # برای فیلتر تاریخ
import django_jalali.admin as jadmin # ادمین شمسی


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        'bride_first_name', 'bride_last_name', 'bride_phone',
        'ceremony_date', 'how_to_know', 'allow_contact', 'created_by'
    )
    search_fields = (
        'bride_first_name', 'bride_last_name', 'bride_phone', JDateFieldListFilter
    )
    list_filter = ('ceremony_date', 'allow_contact')

    readonly_fields = ('created_by',)

    def save_model(self, request, obj, form, change):
        if not obj.pk:  # فقط برای ثبت جدید
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False  # حذف فیزیکی را ممنوع کنیم تا رزروها از بین نروند
