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


HOW_TO_KNOW_CHOICES = [
    ('اینستاگرام', 'اینستاگرام'),
    ('معرفی دوستان یا آشنایان', 'معرفی دوستان یا آشنایان'),
    ('جستجو اینترنتی', 'جستجو اینترنتی'),
    ('تبلیغات', 'تبلیغات'),
    ('سالن زیبایی', 'سالن زیبایی'),
    ('تشریفات عروس', 'تشریفات عروس'),
    ('گروه موسیقی', 'گروه موسیقی'),
    ('سایر', 'سایر'),
]

REQUESTED_SERVICE_CHOICES = [
    ('اجاره لباس', 'اجاره لباس'),
    ('خرید لباس', 'خرید لباس'),
    ('دوخت اختصاصی', 'دوخت اختصاصی'),
    ('جزئیات تکمیلی (اکسسوری)', 'جزئیات تکمیلی (اکسسوری)'),
]

PREFERRED_CONSULTANT_CHOICES = [
    ('مشاوره تخصصی لباس', 'مشاوره تخصصی لباس'),
    ('مشاور زیبایی', 'مشاور زیبایی'),
    ('مشاوره کامل', 'مشاوره کامل'),
]

ESTIMATED_BUDGET_CHOICES = [
    ('اقتصادی', 'اقتصادی'),
    ('متوسط', 'متوسط'),
    ('پرمیوم', 'پرمیوم'),
    ('ویژه', 'ویژه'),
]

ADDITIONAL_SERVICE_CHOICES = [
    ('آتلیه', 'آتلیه'),
    ('تشریفات', 'تشریفات'),
    ('گروه موسیقی', 'گروه موسیقی'),
    ('سالن زیبایی', 'سالن زیبایی'),
]


class CustomerForm(forms.ModelForm):
    ceremony_date = JalaliDateField(
        label='تاریخ مراسم',
        input_formats=['%Y/%m/%d', '%Y-%m-%d'],
        widget=AdminJalaliDateWidget(
            attrs={'class': 'form-control jalali-datepicker', 'autocomplete': 'off'}
        ),
    )
    how_to_know = forms.ChoiceField(
        label='نحوه آشنایی',
        choices=[('', 'انتخاب کنید')] + HOW_TO_KNOW_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    how_to_know_detail = forms.CharField(
        label='توضیحات تکمیلی',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'توضیح یا نام سالن/سایر'}),
    )
    requested_services = forms.MultipleChoiceField(
        label='خدمات مورد نظر',
        choices=REQUESTED_SERVICE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
    )
    additional_services = forms.MultipleChoiceField(
        label='خدمات جانبی',
        choices=ADDITIONAL_SERVICE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
    )
    estimated_budget = forms.ChoiceField(
        label='بودجه تقریبی',
        choices=[('', 'انتخاب کنید')] + ESTIMATED_BUDGET_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    preferred_consultant = forms.ChoiceField(
        label='مشاور ترجیحی',
        choices=[('', 'انتخاب کنید')] + PREFERRED_CONSULTANT_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = Customer
        exclude = ("created_by", "created_at")
        widgets = {
            "bride_first_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "نام عروس"}),
            "bride_last_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "نام خانوادگی عروس"}),
            "bride_phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "مثال: 09121234567"}),
            "city": forms.TextInput(attrs={"class": "form-control", "placeholder": "نام شهر"}),
            "groom_first_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "نام داماد"}),
            "groom_last_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "نام خانوادگی داماد"}),
            "groom_phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "شماره تماس داماد"}),
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

        self.fields['bride_phone'].widget.attrs.update({'maxlength': '11', 'pattern': '\d{11}', 'inputmode': 'numeric'})
        self.fields['groom_phone'].widget.attrs.update({'maxlength': '11', 'pattern': '\d{11}', 'inputmode': 'numeric'})

        if self.instance and self.instance.pk:
            current_how_to_know = self.instance.how_to_know or ''
            if ':' in current_how_to_know:
                option, detail = current_how_to_know.split(':', 1)
                self.initial['how_to_know'] = option.strip()
                self.initial['how_to_know_detail'] = detail.strip()
            else:
                self.initial['how_to_know'] = current_how_to_know

            if self.instance.requested_services:
                self.initial['requested_services'] = [item.strip() for item in self.instance.requested_services.split(',') if item.strip()]
            if self.instance.additional_services:
                self.initial['additional_services'] = [item.strip() for item in self.instance.additional_services.split(',') if item.strip()]
            if self.instance.estimated_budget:
                self.initial['estimated_budget'] = self.instance.estimated_budget
            if self.instance.preferred_consultant:
                self.initial['preferred_consultant'] = self.instance.preferred_consultant

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

    def clean_how_to_know(self):
        selected_value = self.cleaned_data.get('how_to_know')
        detail_value = self.data.get('how_to_know_detail') or self.cleaned_data.get('how_to_know_detail') or ''
        if selected_value in {'سالن زیبایی', 'سایر'} and detail_value:
            return f"{selected_value}: {detail_value.strip()}"
        return selected_value or ''

    def clean_bride_phone(self):
        value = normalize_digits(self.cleaned_data.get('bride_phone') or '')
        if value and len(value) != 11:
            raise forms.ValidationError('شماره تماس عروس باید دقیقاً 11 رقم باشد.')
        return value

    def clean_groom_phone(self):
        value = normalize_digits(self.cleaned_data.get('groom_phone') or '')
        if value and len(value) != 11:
            raise forms.ValidationError('شماره تماس داماد باید دقیقاً 11 رقم باشد.')
        return value

    def clean_requested_services(self):
        selected_values = self.cleaned_data.get('requested_services') or []
        return ', '.join(selected_values)

    def clean_additional_services(self):
        selected_values = self.cleaned_data.get('additional_services') or []
        return ', '.join(selected_values)

