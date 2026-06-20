# reservations/forms.py

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import jdatetime

from customers.models import Customer
from products.models import Dress
from reservations.models import Reservation
from reservations.constants import PaymentMethod
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

    def __init__(self, *args, **kwargs):
        self.rent_price = kwargs.pop("rent_price", None)
        super().__init__(*args, **kwargs)

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
        discount = cleaned_data.get("discount_amount") or 0

        if deposit < 0:
            raise ValidationError("بیعانه نمی‌تواند منفی باشد.")

        if discount < 0:
            raise ValidationError("تخفیف نمی‌تواند منفی باشد.")

        if self.rent_price is None:
            raise ValidationError("اطلاعات هزینه اجاره کامل نیست.")

        final_price = self.rent_price - discount
        if final_price < 0:
            final_price = 0

        if deposit > final_price:
            raise ValidationError("بیعانه نمی‌تواند بیشتر از هزینه نهایی اجاره باشد.")

        cleaned_data["discount_amount"] = discount
        return cleaned_data


class ReservationEditForm(forms.ModelForm):

    discount_amount = forms.IntegerField(
        min_value=0,
        required=False,
        label="تخفیف"
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

    class Meta:
        model = Reservation

        fields = [
            "dress",
            "start_date",
            "rental_days",
            "payment_method",
            "payment_tracking_code",
            "guarantee1_type",
            "guarantee1_tracking_code",
            "guarantee2_type",
            "guarantee2_tracking_code",
            "discount_amount",
        ]

        labels = {
            "payment_method": "روش پرداخت",
            "payment_tracking_code": "کد رهگیری پرداخت",
            "guarantee1_type": "نوع ضمانت اول",
            "guarantee1_tracking_code": "کد رهگیری ضمانت اول",
            "guarantee2_type": "نوع ضمانت دوم",
            "guarantee2_tracking_code": "کد رهگیری ضمانت دوم",
            "discount_amount": "تخفیف",
        }

    def __init__(self, *args, **kwargs):
        self.original_dress = kwargs.pop('original_dress', None)
        self.original_start_date = kwargs.pop('original_start_date', None)
        self.original_rental_days = kwargs.pop('original_rental_days', None)
        self.reservation_id = kwargs.pop('reservation_id', None)
        super().__init__(*args, **kwargs)

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
        discount = cleaned_data.get("discount_amount")

        if discount is None:
            discount = 0
            cleaned_data["discount_amount"] = 0

        if discount < 0:
            raise ValidationError("تخفیف نمی‌تواند منفی باشد.")

        if not dress or not start_date or not rental_days:
            return cleaned_data

        is_available, end_date = ReservationAvailabilityService.is_dress_available(
            dress=dress,
            start_date=start_date,
            rental_days=rental_days,
            exclude_reservation_id=self.reservation_id
        )

        if not is_available:
            raise ValidationError("این لباس در این بازه زمانی رزرو شده است.")

        cleaned_data["end_date"] = end_date

        return cleaned_data

class RemainingPaymentForm(forms.Form):

    remaining_payment_amount = forms.IntegerField(
        min_value=1,
        required=False,
        label="مبلغ پرداخت باقی‌مانده"
    )

    remaining_payment_method = forms.ChoiceField(
        choices=[("", "انتخاب کنید")] + list(PaymentMethod.CHOICES),
        required=False,
        label="روش پرداخت باقی‌مانده"
    )

    remaining_payment_tracking_code = forms.CharField(
        max_length=100,
        required=False,
        label="کد رهگیری پرداخت باقی‌مانده"
    )

    def clean(self):
        cleaned_data = super().clean()

        amount = cleaned_data.get("remaining_payment_amount")
        method = cleaned_data.get("remaining_payment_method")
        code = cleaned_data.get("remaining_payment_tracking_code")

        has_amount = amount is not None and amount > 0
        has_method = method and method != ""
        has_code = code and code.strip() != ""

        if has_amount or has_method or has_code:
            if not (has_amount and has_method and has_code):
                raise ValidationError(
                    "باید تمام اطلاعات پرداخت باقی‌مانده را وارد کنید یا هیچ‌کدام را وارد نکنید."
                )

        return cleaned_data

    def validate_payment_amount(self, remaining_amount):
        """Validate that payment amount matches the remaining amount."""
        amount = self.cleaned_data.get("remaining_payment_amount")

        if amount is None or amount == 0:
            return

        if amount != remaining_amount:
            raise ValidationError(
                f"مبلغ پرداخت باید برابر با باقی‌مانده ({remaining_amount} تومان) باشد."
            )
