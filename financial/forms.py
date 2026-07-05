from django import forms
from reservations.constants import PaymentMethod


class GuaranteeForm(forms.Form):
    tracking_code = forms.CharField(max_length=200, label='کد مرجع', required=True)
    guarantee_type = forms.CharField(max_length=50, label='نوع تضمین', required=True)
    estimated_value = forms.IntegerField(label='مبلغ تقریبی', required=False, min_value=0)
    notes = forms.CharField(widget=forms.Textarea, label='یادداشت', required=False)


class DamageForm(forms.Form):
    damage_type = forms.CharField(max_length=100, label='نوع خسارت', required=True)
    amount = forms.IntegerField(label='مبلغ خسارت (تومان)', required=False, min_value=0)
    description = forms.CharField(widget=forms.Textarea, label='شرح', required=False)
    payment_reference = forms.CharField(max_length=200, label='کد پیگیری پرداخت', required=False)


class CancellationForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea, label='دلیل لغو', required=False)
    refund_amount = forms.IntegerField(label='مبلغ بازپرداخت (تومان)', required=False, min_value=0)
    penalty_amount = forms.IntegerField(label='مبلغ جریمه نگه‌داشته‌شده (تومان)', required=False, min_value=0)
    notes = forms.CharField(widget=forms.Textarea, label='یادداشت', required=False)


class TransactionForm(forms.Form):
    type = forms.ChoiceField(label='نوع تراکنش', choices=[
        ('DEPOSIT', 'بیعانه'),
        ('FINAL_PAYMENT', 'پرداخت نهایی'),
        ('REFUND', 'بازپرداخت'),
        ('DAMAGE_PAYMENT', 'پرداخت خسارت'),
        ('CANCELLATION_FEE', 'جریمه لغو'),
        ('ADJUSTMENT', 'تعدیل دستی'),
    ])
    amount = forms.IntegerField(label='مبلغ (تومان)', min_value=0)
    payment_method = forms.ChoiceField(label='روش پرداخت', choices=PaymentMethod.CHOICES, required=False)
    external_reference = forms.CharField(max_length=200, label='کد پیگیری', required=False)
    note = forms.CharField(widget=forms.Textarea, label='یادداشت', required=False)
