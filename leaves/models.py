from django.conf import settings
from django.db import models
from datetime import datetime, date


class LeaveRequest(models.Model):
    class LeaveType(models.TextChoices):
        DAILY = 'DAILY', 'روزانه'
        HOURLY = 'HOURLY', 'ساعتی'

    class Category(models.TextChoices):
        ENTITLEMENT = 'ENTITLEMENT', 'استحقاقی'
        UNPAID = 'UNPAID', 'بدون حقوق'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'در انتظار'
        APPROVED = 'APPROVED', 'تایید شده'
        REJECTED = 'REJECTED', 'رد شده'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.CharField(max_length=10, choices=LeaveType.choices)
    category = models.CharField(max_length=20, choices=Category.choices)

    # Dates stored in Gregorian (DB) but forms will accept Jalali strings and convert
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    # For hourly leaves
    from_time = models.TimeField(null=True, blank=True)
    to_time = models.TimeField(null=True, blank=True)

    message = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def duration(self):
        if self.leave_type == self.LeaveType.DAILY:
            end = self.end_date or self.start_date
            return (end - self.start_date).days + 1
        else:
            if self.from_time and self.to_time:
                dt1 = datetime.combine(date.min, self.from_time)
                dt2 = datetime.combine(date.min, self.to_time)
                delta = dt2 - dt1
                return round(delta.total_seconds() / 3600, 2)
            return None

    def seller_full_name(self):
        return f"{self.user.first_name or ''} {self.user.last_name or ''}".strip() or self.user.username

    def __str__(self):
        return f"{self.user} - {self.leave_type} - {self.start_date}"
