#products/forms.py
from django import forms
from django.core.exceptions import ValidationError
from .models import Dress
from reservations.utils import normalize_digits


def parse_price_value(value):
    """Parse monetary input value with comma and Persian digit support."""
    if value in (None, ""):
        return 0

    if isinstance(value, (int, float)):
        return int(value)

    normalized = normalize_digits(str(value)).replace(",", "").replace("٬", "").strip()
    if normalized == "":
        return 0

    try:
        return int(normalized)
    except ValueError as exc:
        raise ValidationError("قیمت باید یک عدد صحیح باشد.") from exc


class DressForm(forms.ModelForm):
    class Meta:
        model = Dress
        fields = ['code', 'daily_rent_price']
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'مثلاً DR-1405-001',
                'autocomplete': 'off',
            }),
            'daily_rent_price': forms.TextInput(attrs={
                'class': 'form-control money-input',
                'placeholder': '0',
            }),
        }
        labels = {
            'code': 'کد لباس',
            'daily_rent_price': 'قیمت اجاره روزانه',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['code'].required = True
        self.fields['daily_rent_price'].required = True

    def clean_code(self):
        code = self.cleaned_data.get('code', '').strip()
        if not code:
            raise forms.ValidationError('کد لباس الزامی است.')
        return code

    def clean_daily_rent_price(self):
        price_str = self.cleaned_data.get('daily_rent_price')
        price = parse_price_value(price_str)
        if price <= 0:
            raise forms.ValidationError('قیمت اجاره روزانه باید بیشتر از صفر باشد.')
        return price
