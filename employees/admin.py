#employees/admin.py
from django.contrib import admin
from .models import Employee, Leave


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('user', 'hire_date', 'is_active')

    def has_add_permission(self, request):
        return request.user.role == 'SUPER_ADMIN'

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Leave)
class LeaveAdmin(admin.ModelAdmin):
    list_display = ('employee', 'leave_type', 'status', 'created_at')
    list_filter = ('leave_type', 'status')
    readonly_fields = ('employee', 'leave_type', 'start_date', 'end_date',
                       'start_time', 'end_time', 'reason', 'created_at')

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.role == 'SELLER':
            return qs.filter(employee__user=request.user)

        return qs

    def has_add_permission(self, request):
        return request.user.role == 'SELLER'

    def has_change_permission(self, request, obj=None):
        if request.user.role == 'SELLER':
            return obj and obj.status == 'PENDING'
        return True

    def save_model(self, request, obj, form, change):
        if request.user.role == 'SELLER':
            obj.employee = request.user.employee_profile
            obj.status = 'PENDING'
        super().save_model(request, obj, form, change)
