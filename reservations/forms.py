from django import forms
from jalali_date.fields import JalaliDateField
from jalali_date.widgets import AdminJalaliDateWidget

from .models import Reservation


class ReservationForm(forms.ModelForm):
    rent_date = JalaliDateField(
        label='تاریخ اجاره',
        widget=AdminJalaliDateWidget(attrs={'class': 'form-control'}),
    )
    ceremony_date = JalaliDateField(
        label='تاریخ مراسم',
        required=False,
        widget=AdminJalaliDateWidget(attrs={'class': 'form-control'}),
    )
    return_date = JalaliDateField(
        label='تاریخ بازگشت',
        required=False,
        widget=AdminJalaliDateWidget(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = Reservation
        fields = [
            'customer',
            'dress',
            'rent_date',
            'ceremony_date',
            'return_date',
            'rent_days',
            'deposit_amount',
            'discount_amount',
            'extra_charge_amount',
            'payment_method',
            'guarantee_type',
            'guarantee_description',
            'notes',
            'status',
        ]
        widgets = {
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'dress': forms.Select(attrs={'class': 'form-select'}),
            'rent_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'deposit_amount': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'discount_amount': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'extra_charge_amount': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'guarantee_type': forms.Select(attrs={'class': 'form-select'}),
            'guarantee_description': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean(self):
        cleaned_data = super().clean()

        rent_date = cleaned_data.get('rent_date')
        return_date = cleaned_data.get('return_date')
        rent_days = cleaned_data.get('rent_days')
        customer = cleaned_data.get('customer')
        ceremony_date = cleaned_data.get('ceremony_date')

        if not ceremony_date and customer and hasattr(customer, 'ceremony_date'):
            cleaned_data['ceremony_date'] = customer.ceremony_date

        if rent_date and return_date and return_date < rent_date:
            self.add_error('return_date', 'تاریخ بازگشت نمی‌تواند قبل از تاریخ اجاره باشد.')

        if rent_days is not None and rent_days < 1:
            self.add_error('rent_days', 'مدت اجاره باید حداقل 1 روز باشد.')

        return cleaned_data
