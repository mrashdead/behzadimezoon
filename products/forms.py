#products/forms.py
from django import forms
from .models import Dress

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
            'daily_rent_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'مثلاً 1200000',
                'min': '0',
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
        price = self.cleaned_data.get('daily_rent_price')
        if price is None:
            raise forms.ValidationError('قیمت اجاره روزانه الزامی است.')
        if price < 0:
            raise forms.ValidationError('قیمت اجاره روزانه نمی‌تواند منفی باشد.')
        return price
