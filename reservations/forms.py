#Reservation/forms.py
from datetime import timedelta

from django import forms
from django.core.exceptions import ValidationError

from .models import Reservation


class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = [
            'customer',
            'dress',
            'rent_days',
            'rent_date',
            'ceremony_date',
            'return_date',
            'payment_method',
            'payment_tracking_code',
            'guarantee_type_1',
            'guarantee_1_tracking_code',
            'guarantee_type_2',
            'guarantee_2_tracking_code',
            'deposit_amount',
            'description',
            'status',
        ]
        widgets = {
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'dress': forms.Select(attrs={'class': 'form-select'}),
            'rent_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'rent_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'ceremony_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'readonly': 'readonly'}),
            'return_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'readonly': 'readonly'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'payment_tracking_code': forms.TextInput(attrs={'class': 'form-control'}),
            'guarantee_type_1': forms.Select(attrs={'class': 'form-select'}),
            'guarantee_1_tracking_code': forms.TextInput(attrs={'class': 'form-control'}),
            'guarantee_type_2': forms.Select(attrs={'class': 'form-select'}),
            'guarantee_2_tracking_code': forms.TextInput(attrs={'class': 'form-control'}),
            'deposit_amount': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean(self):
        cleaned_data = super().clean()

        dress = cleaned_data.get('dress')
        rent_days = cleaned_data.get('rent_days')
        rent_date = cleaned_data.get('rent_date')
        guarantee_type_1 = cleaned_data.get('guarantee_type_1')
        guarantee_1_tracking_code = cleaned_data.get('guarantee_1_tracking_code')
        guarantee_type_2 = cleaned_data.get('guarantee_type_2')
        guarantee_2_tracking_code = cleaned_data.get('guarantee_2_tracking_code')

        if rent_date and rent_days:
            return_date = rent_date + timedelta(days=rent_days)
            cleaned_data['return_date'] = return_date
            self.instance.return_date = return_date

        if guarantee_type_1 and not guarantee_1_tracking_code:
            self.add_error('guarantee_1_tracking_code', 'کد ضمانت اول اجباری است.')

        if guarantee_type_2 and not guarantee_2_tracking_code:
            self.add_error('guarantee_2_tracking_code', 'برای ضمانت دوم، کد پیگیری هم باید وارد شود.')

        if dress and rent_date and rent_days:
            return_date = cleaned_data.get('return_date')

            overlapping = Reservation.objects.filter(
                dress=dress,
                rent_date__lt=return_date,
                return_date__gt=rent_date,
            ).exclude(status='cancelled')

            if self.instance.pk:
                overlapping = overlapping.exclude(pk=self.instance.pk)

            if overlapping.exists():
                self.add_error('dress', 'این لباس در این بازه زمانی قبلاً رزرو شده است.')

        return cleaned_data
