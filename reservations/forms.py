# reservations/forms.py

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import jdatetime

from customers.models import Customer
from products.models import Dress
from reservations.models import Reservation
from reservations.services.availability_service import ReservationAvailabilityService
from .utils import parse_reservation_date


class ReservationStepOneForm(forms.Form):

    customer = forms.ModelChoiceField(
        queryset=Customer.objects.all(),
        required=True,
        label="مشتری"
    )

    dress = forms.ModelChoiceField(
        queryset=Dress.objects.filter(status=Dress.STATUS_ACTIVE),
        required=True,
        label="لباس"
    )

    start_date = forms.CharField(
        required=True,
        label="تاریخ شروع اجاره"
    )

    rental_days = forms.IntegerField(
        min_value=1,
        required=True,
        label="مدت اجاره (روز)"
    )

    def clean_start_date(self):
        value = self.cleaned_data.get("start_date")

        if not value:
            return None

        parsed_date = parse_reservation_date(value)

        if parsed_date is None:
            raise ValidationError("تاریخ نامعتبر است.")

        return parsed_date

    def clean(self):

        cleaned_data = super().clean()

        dress = cleaned_data.get("dress")
        start_date = cleaned_data.get("start_date")
        rental_days = cleaned_data.get("rental_days")

        if not dress or not start_date or not rental_days:
            return cleaned_data

        is_available, end_date = ReservationAvailabilityService.is_dress_available(
            dress=dress,
            start_date=start_date,
            rental_days=rental_days
        )

        if not is_available:
            raise ValidationError("این لباس در این بازه زمانی رزرو شده است.")

        cleaned_data["end_date"] = end_date

        return cleaned_data


class ReservationStepTwoForm(forms.ModelForm):

    discount_amount = forms.IntegerField(
        min_value=0,
        required=False,
        label="تخفیف"
    )

    class Meta:
        model = Reservation

        fields = [
            "payment_method",
            "payment_tracking_code",
            "guarantee1_type",
            "guarantee1_tracking_code",
            "guarantee2_type",
            "guarantee2_tracking_code",
            "deposit_amount",
            "discount_amount",
        ]

        labels = {
            "payment_method": "روش پرداخت",
            "payment_tracking_code": "کد رهگیری پرداخت",
            "guarantee1_type": "نوع ضمانت اول",
            "guarantee1_tracking_code": "کد رهگیری ضمانت اول",
            "guarantee2_type": "نوع ضمانت دوم",
            "guarantee2_tracking_code": "کد رهگیری ضمانت دوم",
            "deposit_amount": "بیعانه",
            "discount_amount": "تخفیف",
        }

    def clean(self):

        cleaned_data = super().clean()

        deposit = cleaned_data.get("deposit_amount") or 0
        discount = cleaned_data.get("discount_amount")
        if discount is None:
            discount = 0
            cleaned_data["discount_amount"] = 0

        if deposit < 0:
            raise ValidationError("بیعانه نمی‌تواند منفی باشد.")

        if discount < 0:
            raise ValidationError("تخفیف نمی‌تواند منفی باشد.")

        return cleaned_data
