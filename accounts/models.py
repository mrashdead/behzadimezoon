from django.contrib.auth.models import AbstractUser
from django.db import models
from .managers import UserManager


class User(AbstractUser):

    class Role(models.TextChoices):
        SUPER_ADMIN = 'SUPER_ADMIN', 'سوپر ادمین'
        MANAGER = 'MANAGER', 'مدیر داخلی'
        SELLER = 'SELLER', 'فروشنده'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.SELLER
    )

    objects = UserManager()  # ✅ خیلی مهم

    # def save(self, *args, **kwargs):
    #     if self.role == self.Role.SUPER_ADMIN:
    #         self.is_staff = True
    #         self.is_superuser = True
    #     elif self.role == self.Role.MANAGER:
    #         self.is_staff = True
    #         self.is_superuser = False
    #     else:
    #         self.is_staff = False
    #         self.is_superuser = False

    #     super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
