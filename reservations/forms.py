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
            'total_amount',
            'deposit_amount',
            'payment_method',
            'payment_tracking_code',
            'guarantee_type_1',
            'guarantee_type_2',
            'guarantee_tracking_code',
            'product_condition',
        ]
        widgets = {
    'customer': forms.Select(attrs={'class': 'form-select'}),
    'dress': forms.Select(attrs={'class': 'form-select'}),
    'rent_days': forms.NumberInput(attrs={'class': 'form-control'}),
    'rent_date': forms.TextInput(attrs={'class': 'form-control'}),
    'ceremony_date': forms.TextInput(attrs={'class': 'form-control'}),
    'return_date': forms.TextInput(attrs={'class': 'form-control'}),
    'total_amount': forms.NumberInput(attrs={'class': 'form-control'}),
    'deposit_amount': forms.NumberInput(attrs={'class': 'form-control'}),
    'payment_method': forms.Select(attrs={'class': 'form-select'}),
    'payment_tracking_code': forms.TextInput(attrs={'class': 'form-control'}),
    'guarantee_type_1': forms.TextInput(attrs={'class': 'form-control'}),
    'guarantee_type_2': forms.TextInput(attrs={'class': 'form-control'}),
    'guarantee_tracking_code': forms.TextInput(attrs={'class': 'form-control'}),
    'product_condition': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
}
        labels = {
            'customer': 'مشتری',
            'dress': 'لباس',
            'rent_days': 'مدت اجاره (روز)',
            'rent_date': 'تاریخ اجاره',
            'ceremony_date': 'تاریخ مراسم',
            'return_date': 'تاریخ بازگشت',
            'total_amount': 'مبلغ کل اجاره',
            'deposit_amount': 'بیعانه',
            'payment_method': 'روش پرداخت',
            'payment_tracking_code': 'کد پیگیری پرداخت',
            'guarantee_type_1': 'ضمانت اول',
            'guarantee_type_2': 'ضمانت دوم',
            'guarantee_tracking_code': 'کد / توضیحات ضمانت',
            'product_condition': 'سلامت کالا',
        }
        help_texts = {
            'rent_days': 'تعداد روزهای اجاره را وارد کنید.',
            'deposit_amount': 'در صورت عدم دریافت بیعانه، صفر وارد کنید.',
            'product_condition': 'مثلاً: بدون پارگی، سنگ‌دوزی سالم، نیاز به اتوکشی ندارد.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # placeholder خالی برای selectها
        self.fields['customer'].empty_label = 'انتخاب مشتری'
        self.fields['dress'].empty_label = 'انتخاب لباس'

        # اختیاری بودن برخی فیلدها
        self.fields['payment_method'].required = False
        self.fields['payment_tracking_code'].required = False
        self.fields['guarantee_type_1'].required = False
        self.fields['guarantee_type_2'].required = False
        self.fields['guarantee_tracking_code'].required = False
        self.fields['product_condition'].required = False

        # برای نمایش بهتر در مودال
        for name, field in self.fields.items():
            css_class = field.widget.attrs.get('class', '')
            if isinstance(field.widget, forms.Select):
                if 'form-select' not in css_class:
                    field.widget.attrs['class'] = f'{css_class} form-select'.strip()
            else:
                if 'form-control' not in css_class and 'form-check-input' not in css_class:
                    field.widget.attrs['class'] = f'{css_class} form-control'.strip()

    def clean(self):
        cleaned_data = super().clean()

        rent_date = cleaned_data.get('rent_date')
        ceremony_date = cleaned_data.get('ceremony_date')
        return_date = cleaned_data.get('return_date')
        rent_days = cleaned_data.get('rent_days')

        total_amount = cleaned_data.get('total_amount') or 0
        deposit_amount = cleaned_data.get('deposit_amount') or 0
        payment_method = cleaned_data.get('payment_method')
        payment_tracking_code = cleaned_data.get('payment_tracking_code')

        # اعتبارسنجی ترتیب تاریخ‌ها
        if rent_date and ceremony_date and return_date:
            if not (rent_date <= ceremony_date <= return_date):
                self.add_error('ceremony_date', 'تاریخ مراسم باید بین تاریخ اجاره و تاریخ بازگشت باشد.')
                self.add_error('return_date', 'تاریخ بازگشت باید بعد از تاریخ مراسم باشد.')

            calculated_days = (return_date - rent_date).days
            if calculated_days < 0:
                self.add_error('return_date', 'تاریخ بازگشت نمی‌تواند قبل از تاریخ اجاره باشد.')
            elif rent_days is not None and calculated_days != rent_days:
                self.add_error('rent_days', 'مدت اجاره با بازه تاریخ‌ها همخوانی ندارد.')

        # اعتبارسنجی مبلغ کل
        if total_amount <= 0:
            self.add_error('total_amount', 'مبلغ کل باید بیشتر از صفر باشد.')

        # اعتبارسنجی بیعانه
        if deposit_amount < 0:
            self.add_error('deposit_amount', 'بیعانه نمی‌تواند منفی باشد.')

        if deposit_amount > total_amount:
            self.add_error('deposit_amount', 'بیعانه نمی‌تواند از مبلغ کل بیشتر باشد.')

        # الزام روش پرداخت وقتی بیعانه ثبت شده
        if deposit_amount > 0 and not payment_method:
            self.add_error('payment_method', 'برای بیعانه، انتخاب روش پرداخت الزامی است.')

        # اگر کد پیگیری وجود دارد، روش پرداخت هم باید باشد
        if payment_tracking_code and not payment_method:
            self.add_error('payment_method', 'بدون انتخاب روش پرداخت، کد پیگیری معتبر نیست.')

        return cleaned_data
