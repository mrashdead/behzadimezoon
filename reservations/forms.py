# reservations/forms.py

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import jdatetime

from customers.models import Customer
from products.models import Dress
from reservations.models import Reservation
from reservations.constants import GuaranteeType, PaymentMethod
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

    discount_type = forms.ChoiceField(
        choices=Reservation.DISCOUNT_TYPE_CHOICES,
        required=False,
        label="نوع تخفیف"
    )

    discount_value = forms.IntegerField(
        min_value=0,
        required=False,
        label="مقدار تخفیف"
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
            "discount_type",
            "discount_value",
        ]

        labels = {
            "payment_method": "روش پرداخت",
            "payment_tracking_code": "کد رهگیری پرداخت",
            "guarantee1_type": "نوع ضمانت اول",
            "guarantee1_tracking_code": "کد رهگیری ضمانت اول",
            "guarantee2_type": "نوع ضمانت دوم",
            "guarantee2_tracking_code": "کد رهگیری ضمانت دوم",
            "deposit_amount": "بیعانه",
            "discount_type": "نوع تخفیف",
            "discount_value": "مقدار تخفیف",
        }

    def clean(self):

        cleaned_data = super().clean()

        deposit = cleaned_data.get("deposit_amount") or 0
        discount_type = cleaned_data.get("discount_type") or Reservation.DISCOUNT_NONE
        discount_value = cleaned_data.get("discount_value") or 0

        if deposit < 0:
            raise ValidationError("بیعانه نمی‌تواند منفی باشد.")

        if discount_value < 0:
            raise ValidationError("مقدار تخفیف نمی‌تواند منفی باشد.")

        if discount_type == Reservation.DISCOUNT_NONE and discount_value > 0:
            raise ValidationError("اگر نوع تخفیف انتخاب نشده، مقدار تخفیف باید صفر باشد.")

        if discount_type == Reservation.DISCOUNT_PERCENT and discount_value > 100:
            raise ValidationError("درصد تخفیف نمی‌تواند بیشتر از ۱۰۰٪ باشد.")

        if self.rent_price is None:
            raise ValidationError("اطلاعات هزینه اجاره کامل نیست.")

        if discount_type == Reservation.DISCOUNT_AMOUNT:
            discount_amount = discount_value
        elif discount_type == Reservation.DISCOUNT_PERCENT:
            discount_amount = (self.rent_price * discount_value) // 100
        else:
            discount_amount = 0

        final_price = self.rent_price - discount_amount
        if final_price < 0:
            final_price = 0

        if deposit > final_price:
            raise ValidationError("بیعانه نمی‌تواند بیشتر از هزینه نهایی اجاره باشد.")

        cleaned_data["discount_type"] = discount_type
        cleaned_data["discount_value"] = discount_value
        return cleaned_data


class ReservationEditForm(forms.ModelForm):

    discount_type = forms.ChoiceField(
        choices=[("", "بدون تخفیف")] + list(Reservation.DISCOUNT_TYPE_CHOICES),
        required=False,
        label="نوع تخفیف"
    )

    discount_value = forms.IntegerField(
        min_value=0,
        required=False,
        label="مقدار تخفیف"
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

    payment_method = forms.ChoiceField(
        choices=PaymentMethod.CHOICES,
        required=True,
        label="روش پرداخت"
    )

    payment_tracking_code = forms.CharField(
        max_length=100,
        required=True,
        label="کد رهگیری پرداخت"
    )

    guarantee1_type = forms.ChoiceField(
        choices=GuaranteeType.CHOICES,
        required=True,
        label="نوع ضمانت اول"
    )

    guarantee1_tracking_code = forms.CharField(
        max_length=100,
        required=True,
        label="کد رهگیری ضمانت اول"
    )

    guarantee2_type = forms.ChoiceField(
        choices=[("", "ندارد")] + list(GuaranteeType.CHOICES),
        required=False,
        label="نوع ضمانت دوم"
    )

    guarantee2_tracking_code = forms.CharField(
        max_length=100,
        required=False,
        label="کد رهگیری ضمانت دوم"
    )

    deposit_amount = forms.IntegerField(
        min_value=0,
        required=True,
        label="بیعانه"
    )

    class Meta:
        model = Reservation

        fields = [
            "dress",
            "start_date",
            "rental_days",
            "discount_type",
            "discount_value",
            "payment_method",
            "payment_tracking_code",
            "guarantee1_type",
            "guarantee1_tracking_code",
            "guarantee2_type",
            "guarantee2_tracking_code",
            "deposit_amount",
        ]

        labels = {
            "discount_type": "نوع تخفیف",
            "discount_value": "مقدار تخفیف",
            "payment_method": "روش پرداخت",
            "payment_tracking_code": "کد رهگیری پرداخت",
            "guarantee1_type": "نوع ضمانت اول",
            "guarantee1_tracking_code": "کد رهگیری ضمانت اول",
            "guarantee2_type": "نوع ضمانت دوم",
            "guarantee2_tracking_code": "کد رهگیری ضمانت دوم",
            "deposit_amount": "بیعانه",
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
        discount_type = cleaned_data.get("discount_type") or Reservation.DISCOUNT_NONE
        discount_value = cleaned_data.get("discount_value") or 0

        if discount_type == Reservation.DISCOUNT_NONE and discount_value > 0:
            raise ValidationError({
                "discount_value": "اگر نوع تخفیف انتخاب نشده، مقدار باید صفر باشد."
            })

        if discount_value < 0:
            raise ValidationError({"discount_value": "مقدار تخفیف نمی‌تواند منفی باشد."})

        if discount_type == Reservation.DISCOUNT_PERCENT and discount_value > 100:
            raise ValidationError({
                "discount_value": "درصد تخفیف نمی‌تواند بیشتر از ۱۰۰٪ باشد."
            })

        payment_method = cleaned_data.get("payment_method")
        payment_tracking_code = cleaned_data.get("payment_tracking_code")
        guarantee1_type = cleaned_data.get("guarantee1_type")
        guarantee1_tracking_code = cleaned_data.get("guarantee1_tracking_code")
        guarantee2_type = cleaned_data.get("guarantee2_type")
        guarantee2_tracking_code = cleaned_data.get("guarantee2_tracking_code")
        deposit_amount = cleaned_data.get("deposit_amount") or 0

        # Both guarantee2 fields are optional as a pair.
        # If user selects guarantee2_type (non-empty), code is required.
        if guarantee2_type and guarantee2_type.strip():
            if not guarantee2_tracking_code or not guarantee2_tracking_code.strip():
                raise ValidationError({
                    "guarantee2_tracking_code": "در صورت انتخاب ضمانت دوم، کد رهگیری آن الزامی است."
                })

        # If user enters guarantee2_tracking_code, type is required.
        if guarantee2_tracking_code and guarantee2_tracking_code.strip():
            if not guarantee2_type or not guarantee2_type.strip():
                raise ValidationError({
                    "guarantee2_type": "اگر کد رهگیری ضمانت دوم وارد شده است، نوع ضمانت دوم را انتخاب کنید."
                })

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

        rent_price = dress.daily_rent_price

        if discount_type == Reservation.DISCOUNT_AMOUNT:
            discount_amount = discount_value
        elif discount_type == Reservation.DISCOUNT_PERCENT:
            discount_amount = (rent_price * discount_value) // 100
        else:
            discount_amount = 0

        final_price = rent_price - discount_amount
        if final_price < 0:
            final_price = 0

        if deposit_amount > final_price:
            raise ValidationError({
                "deposit_amount": "بیعانه نمی‌تواند بیشتر از مبلغ نهایی اجاره باشد."
            })

        remaining_payment_amount = self.instance.remaining_payment_amount or 0
        if remaining_payment_amount > 0 and deposit_amount + remaining_payment_amount > final_price:
            raise ValidationError({
                "deposit_amount": "جمع بیعانه و پرداخت باقی‌مانده نباید بیشتر از مبلغ نهایی باشد."
            })

        if remaining_payment_amount > 0 and remaining_payment_amount > final_price:
            raise ValidationError(
                "پرداخت باقی‌مانده ثبت‌شده بیشتر از مبلغ نهایی رزرو است. لطفاً ابتدا وضعیت مالی رزرو را بررسی کنید."
            )

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


class DamageReturnForm(forms.Form):
    """
    فرم ثبت آسیب و خسارت هنگام بازگشت لباس از مشتری
    """

    item_damaged = forms.BooleanField(
        required=False,
        label="آیا لباس آسیب‌دیده است؟",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"})
    )

    damage_amount = forms.IntegerField(
        min_value=0,
        required=False,
        label="مبلغ خسارت (تومان)",
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "min": "0",
                "placeholder": "اگر آسیب وجود دارد، مبلغ را وارد کنید"
            }
        )
    )

    damage_notes = forms.CharField(
        widget=forms.Textarea(
            attrs={"rows": 3, "class": "form-control", "placeholder": "اختیاری"}
        ),
        required=False,
        label="توضیحات خسارت"
    )

    def clean(self):
        cleaned_data = super().clean()

        item_damaged = cleaned_data.get("item_damaged")
        damage_amount = cleaned_data.get("damage_amount")
        damage_notes = cleaned_data.get("damage_notes")

        # اگر خسارت وجود دارد، باید مبلغ خسارت وارد شود
        if item_damaged:
            if damage_amount is None or damage_amount <= 0:
                raise ValidationError(
                    "اگر لباس آسیب‌دیده است، باید مبلغ خسارت را وارد کنید."
                )

        # اگر مبلغ خسارت وارد شده، باید خسارت علامت‌گذاری شود
        if damage_amount and damage_amount > 0:
            if not item_damaged:
                raise ValidationError(
                    "اگر مبلغ خسارت را وارد کردید، باید آسیب لباس را علامت‌گذاری کنید."
                )

        return cleaned_data

