#customers/forms.py
from datetime import date
import jdatetime
from django import forms
from .models import Customer
from jalali_date.fields import JalaliDateField
from jalali_date.widgets import AdminJalaliDateWidget

PERSIAN_DIGIT_MAP = str.maketrans(
    '۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩',
    '01234567890123456789'
)


def normalize_digits(value):
    if value is None:
        return value
    return str(value).translate(PERSIAN_DIGIT_MAP)


def parse_jalali_or_gregorian_date(value):
    if not value:
        return None

    value = normalize_digits(value).strip()
    normalized = value.replace('-', '/')
    parts = normalized.split('/')

    if len(parts) == 3:
        try:
            year = int(parts[0])
            month = int(parts[1])
            day = int(parts[2])

            if 1900 <= year <= 2200:
                return date(year, month, day)

            if 1300 <= year <= 1600:
                j_date = jdatetime.date(year, month, day)
                return j_date.togregorian()
        except (ValueError, OverflowError):
            pass

    return None


class CustomerForm(forms.ModelForm):
    ceremony_date = JalaliDateField(
        label='تاریخ مراسم',
        input_formats=['%Y/%m/%d', '%Y-%m-%d'],
        widget=AdminJalaliDateWidget(
            attrs={'class': 'form-control jalali-datepicker', 'autocomplete': 'off'}
        ),
    )

    class Meta:
        model = Customer
        exclude = ("created_by", "created_at")
        widgets = {
            "bride_first_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "نام عروس"}),
            "bride_last_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "نام خانوادگی عروس"}),
            "bride_phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "مثال: 09121234567"}),
            "how_to_know": forms.TextInput(attrs={"class": "form-control", "placeholder": "مثال: اینستاگرام، معرفی دوستان"}),
            "groom_first_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "نام داماد"}),
            "groom_last_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "نام خانوادگی داماد"}),
            "groom_phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "شماره تماس داماد"}),
            "requested_services": forms.TextInput(attrs={"class": "form-control", "placeholder": "مثال: لباس، فرمالیته"}),
            "estimated_budget": forms.TextInput(attrs={"class": "form-control", "placeholder": "بودجه تقریبی"}),
            "additional_services": forms.TextInput(attrs={"class": "form-control", "placeholder": "خدمات جانبی"}),
            "preferred_consultant": forms.TextInput(attrs={"class": "form-control", "placeholder": "نام مشاور ترجیحی"}),
            "guest_count": forms.NumberInput(attrs={"class": "form-control", "placeholder": "تعداد مهمان"}),
            "ceremony_decoration": forms.TextInput(attrs={"class": "form-control", "placeholder": "تشریفات"}),
            "beauty_salon": forms.TextInput(attrs={"class": "form-control", "placeholder": "نام سالن زیبایی"}),
            "studio_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "نام آتلیه"}),
            "music_band": forms.TextInput(attrs={"class": "form-control", "placeholder": "گروه موسیقی"}),
            "customer_note": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "یادداشت مشتری"}),
            "allow_contact": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        required_fields = [
            "bride_first_name",
            "bride_last_name",
            "bride_phone",
            "ceremony_date",
            "how_to_know",
        ]
        for field_name in required_fields:
            self.fields[field_name].required = True

    def clean_ceremony_date(self):
        raw_value = self.data.get('ceremony_date') or self.cleaned_data.get('ceremony_date')

        if isinstance(raw_value, date):
            return raw_value

        if raw_value:
            parsed_date = parse_jalali_or_gregorian_date(raw_value)
            if parsed_date is None:
                raise forms.ValidationError('تاریخ مراسم نامعتبر است. لطفاً قالب را بررسی کنید.')
            return parsed_date

        return None

