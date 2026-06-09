#employees/models.py
from django.conf import settings
from django.db import models


class Employee(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='employee_profile'
    )

    hire_date = models.DateField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.user.username

class Leave(models.Model):
    LEAVE_TYPE_CHOICES = (
        ('DAILY', 'روزانه'),
        ('HOURLY', 'ساعتی'),
    )

    STATUS_CHOICES = (
        ('PENDING', 'در انتظار تایید'),
        ('APPROVED', 'تایید شده'),
        ('REJECTED', 'رد شده'),
    )

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='leaves'
    )

    leave_type = models.CharField(
        max_length=10,
        choices=LEAVE_TYPE_CHOICES
    )

    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    reason = models.TextField(blank=True)

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='PENDING'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employee} - {self.leave_type}"
