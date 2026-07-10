from django import forms
from django.core.exceptions import ValidationError
from reservations.constants import PaymentMethod
from reservations.utils import normalize_digits


def parse_amount_value(value):
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
        raise ValidationError("مبلغ باید یک عدد صحیح باشد.") from exc


class GuaranteeForm(forms.Form):
    tracking_code = forms.CharField(max_length=200, label='کد مرجع', required=True)
    guarantee_type = forms.CharField(max_length=50, label='نوع تضمین', required=True)
    estimated_value = forms.CharField(
        label='مبلغ تقریبی',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control money-input',
            'placeholder': '0'
        })
    )
    notes = forms.CharField(widget=forms.Textarea, label='یادداشت', required=False)

    def clean_estimated_value(self):
        return parse_amount_value(self.cleaned_data.get('estimated_value'))


class DamageForm(forms.Form):
    damage_type = forms.CharField(max_length=100, label='نوع خسارت', required=True)
    amount = forms.CharField(
        label='مبلغ خسارت (تومان)',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control money-input',
            'placeholder': '0'
        })
    )
    description = forms.CharField(widget=forms.Textarea, label='شرح', required=False)
    payment_reference = forms.CharField(max_length=200, label='کد پیگیری پرداخت', required=False)

    def clean_amount(self):
        return parse_amount_value(self.cleaned_data.get('amount'))


class CancellationForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea, label='دلیل لغو', required=False)
    refund_amount = forms.CharField(
        label='مبلغ بازپرداخت (تومان)',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control money-input',
            'placeholder': '0'
        })
    )
    penalty_amount = forms.CharField(
        label='مبلغ جریمه نگه‌داشته‌شده (تومان)',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control money-input',
            'placeholder': '0'
        })
    )
    notes = forms.CharField(widget=forms.Textarea, label='یادداشت', required=False)

    def clean_refund_amount(self):
        return parse_amount_value(self.cleaned_data.get('refund_amount'))

    def clean_penalty_amount(self):
        return parse_amount_value(self.cleaned_data.get('penalty_amount'))


class TransactionForm(forms.Form):
    type = forms.ChoiceField(label='نوع تراکنش', choices=[
        ('DEPOSIT', 'بیعانه'),
        ('FINAL_PAYMENT', 'پرداخت نهایی'),
        ('REFUND', 'بازپرداخت'),
        ('DAMAGE_PAYMENT', 'پرداخت خسارت'),
        ('CANCELLATION_FEE', 'جریمه لغو'),
        ('ADJUSTMENT', 'تعدیل دستی'),
    ])
    amount = forms.CharField(
        label='مبلغ (تومان)',
        widget=forms.TextInput(attrs={
            'class': 'form-control money-input',
            'placeholder': '0'
        })
    )
    payment_method = forms.ChoiceField(label='روش پرداخت', choices=PaymentMethod.CHOICES, required=False)
    external_reference = forms.CharField(max_length=200, label='کد پیگیری', required=False)
    note = forms.CharField(widget=forms.Textarea, label='یادداشت', required=False)

    def clean_amount(self):
        amount = parse_amount_value(self.cleaned_data.get('amount'))
        if amount <= 0:
            raise ValidationError('مبلغ باید بزرگتر از صفر باشد.')
        return amount
