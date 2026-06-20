#accounts/forms.py
from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User
from .permissions import allowed_creatable_roles


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "نام"}),
            "last_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "نام خانوادگی"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "ایمیل"}),
        }
        labels = {
            "first_name": "نام",
            "last_name": "نام خانوادگی",
            "email": "ایمیل",
        }


class SettingsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "نام"}),
            "last_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "نام خانوادگی"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "ایمیل"}),
        }
        labels = {
            "first_name": "نام",
            "last_name": "نام خانوادگی",
            "email": "ایمیل",
        }


class AdminUserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "is_active"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class ManagedUserCreationForm(forms.ModelForm):
    """
    Form for internal staff user creation.
    - Restricts role choices based on request.user
    - Validates password with Django validators
    - Confirms password match
    """
    password = forms.CharField(
        label="رمز عبور",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "رمز عبور"}),
        help_text="رمز عبور باید حداقل 8 کاراکتر باشد"
    )
    password_confirm = forms.CharField(
        label="تکرار رمز عبور",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "تکرار رمز عبور"}),
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "role"]
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control", "placeholder": "نام کاربری"}),
            "first_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "نام"}),
            "last_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "نام خانوادگی"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "ایمیل"}),
            "role": forms.Select(attrs={"class": "form-select"}),
        }
        labels = {
            "username": "نام کاربری",
            "first_name": "نام",
            "last_name": "نام خانوادگی",
            "email": "ایمیل",
            "role": "نقش کاربری",
        }

    def __init__(self, *args, request_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter role choices based on requesting user's permissions
        if request_user:
            allowed_roles = allowed_creatable_roles(request_user)
            self.fields["role"].choices = [
                (role, User.Role(role).label)
                for role in allowed_roles
            ]
        else:
            # Fallback to SELLER only if no user provided
            self.fields["role"].choices = [(User.Role.SELLER, User.Role.SELLER.label)]

    def clean_username(self):
        """Check username uniqueness."""
        username = self.cleaned_data.get("username", "").strip()
        if User.objects.filter(username=username).exists():
            raise ValidationError("این نام کاربری قبلاً استفاده شده است.")
        return username

    def clean_email(self):
        """Validate email is not empty and format is valid."""
        email = self.cleaned_data.get("email", "").strip()
        if not email:
            raise ValidationError("ایمیل الزامی است.")
        if User.objects.filter(email=email).exists():
            raise ValidationError("این ایمیل قبلاً ثبت شده است.")
        return email

    def clean_password(self):
        """Validate password against Django's validators."""
        password = self.cleaned_data.get("password", "")
        try:
            validate_password(password)
        except ValidationError as e:
            raise ValidationError(e.messages)
        return password

    def clean(self):
        """Validate password confirmation and role."""
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")
        role = cleaned_data.get("role")

        # Check password match
        if password and password_confirm:
            if password != password_confirm:
                raise ValidationError({"password_confirm": "رمز عبور و تکرار آن مطابقت ندارند."})

        # Validate role is allowed (server-side enforcement)
        # This prevents tampering with POST data
        # Note: request_user must have been set in __init__
        if role and not hasattr(self, "_request_user"):
            raise ValidationError({"role": "نقش انتخاب‌شده نامعتبر است."})

        return cleaned_data

    def save(self, commit=True):
        """Create user with password."""
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.is_active = True
        if commit:
            user.save()
        return user


class PasswordChangeFormPersian(forms.Form):
    """
    Custom password change form with Persian labels.
    """
    current_password = forms.CharField(
        label="رمز عبور فعلی",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "رمز عبور فعلی"}),
    )
    new_password = forms.CharField(
        label="رمز عبور جدید",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "رمز عبور جدید"}),
        help_text="رمز عبور باید حداقل 8 کاراکتر باشد"
    )
    new_password_confirm = forms.CharField(
        label="تکرار رمز عبور جدید",
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "تکرار رمز عبور جدید"}),
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_current_password(self):
        """Verify current password."""
        current_password = self.cleaned_data.get("current_password")
        if not self.user.check_password(current_password):
            raise ValidationError("رمز عبور فعلی صحیح نیست.")
        return current_password

    def clean_new_password(self):
        """Validate new password with Django validators."""
        new_password = self.cleaned_data.get("new_password")
        try:
            validate_password(new_password, self.user)
        except ValidationError as e:
            raise ValidationError(e.messages)
        return new_password

    def clean(self):
        """Validate new password confirmation."""
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        new_password_confirm = cleaned_data.get("new_password_confirm")

        if new_password and new_password_confirm:
            if new_password != new_password_confirm:
                raise ValidationError({"new_password_confirm": "رمز عبور جدید و تکرار آن مطابقت ندارند."})

        return cleaned_data

    def save(self):
        """Change user password."""
        self.user.set_password(self.cleaned_data["new_password"])
        self.user.save()
        return self.user

