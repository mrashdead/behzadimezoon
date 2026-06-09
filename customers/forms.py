from django import forms
from .models import Customer


class CustomerForm(forms.ModelForm):
    ceremony_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
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
