from django.contrib import admin
from .models import LeaveRequest


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'leave_type', 'category', 'start_date', 'end_date', 'from_time', 'to_time', 'status', 'created_at')
    list_filter = ('leave_type', 'category', 'status')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
