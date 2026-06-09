from django.contrib import admin
from .models import Dress


@admin.register(Dress)
class DressAdmin(admin.ModelAdmin):
    list_display = ('code', 'daily_rent_price')
    search_fields = ('code',)

    def has_add_permission(self, request):
        return request.user.role in ['SUPER_ADMIN', 'MANAGER']

    def has_change_permission(self, request, obj=None):
        return request.user.role in ['SUPER_ADMIN', 'MANAGER']

    def has_delete_permission(self, request, obj=None):
        return False
