from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import User


@admin.register(User)
class CustomUserAdmin(DjangoUserAdmin):
    list_display = ('username', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_active')
    search_fields = ('username', 'email')

    ordering = ('username',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('اطلاعات شخصی', {'fields': ('first_name', 'last_name', 'email')}),
        ('سطح دسترسی', {'fields': ('role',)}),
        ('وضعیت', {'fields': ('is_active',)}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'role'),
        }),
    )

    # 🔒 محدودسازی نمایش کاربران
    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.role == 'MANAGER':
            return qs.filter(role='SELLER')

        return qs

    # 🔒 محدودسازی حذف
    def has_delete_permission(self, request, obj=None):
        if request.user.role == 'MANAGER':
            return False
        return True

    # 🔒 جلوگیری از تغییر role توسط MANAGER
    def get_readonly_fields(self, request, obj=None):
        if request.user.role == 'MANAGER':
            return ('role',)
        return ()

    # ✅ همگام‌سازی role با is_staff
    def save_model(self, request, obj, form, change):
        if request.user.role == 'MANAGER':
            obj.role = 'SELLER'

        if obj.role == 'SUPER_ADMIN':
            obj.is_staff = True
            obj.is_superuser = True
        elif obj.role == 'MANAGER':
            obj.is_staff = True
            obj.is_superuser = False
        else:  # SELLER
            obj.is_staff = False
            obj.is_superuser = False

        super().save_model(request, obj, form, change)
