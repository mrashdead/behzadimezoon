from django import forms
import jdatetime
from .models import LeaveRequest


class LeaveRequestForm(forms.ModelForm):
    # Jalali date inputs as plain text; JS widget will provide Persian datepicker
    start_date_j = forms.CharField(label='تاریخ شروع', widget=forms.TextInput(attrs={'class': 'form-control jalali-date'}))
    end_date_j = forms.CharField(label='تاریخ پایان', required=False, widget=forms.TextInput(attrs={'class': 'form-control jalali-date'}))

    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'category', 'start_date_j', 'end_date_j', 'from_time', 'to_time', 'message']
        widgets = {
            'leave_type': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'from_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'to_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean(self):
        cleaned = super().clean()
        sd = cleaned.get('start_date_j')
        ed = cleaned.get('end_date_j')

        if sd:
            try:
                jd = jdatetime.datetime.strptime(sd, '%Y/%m/%d')
                cleaned['start_date'] = jd.togregorian().date()
            except Exception:
                raise forms.ValidationError('فرمت تاریخ شروع صحیح نیست (YYYY/MM/DD)')

        if ed:
            try:
                jd2 = jdatetime.datetime.strptime(ed, '%Y/%m/%d')
                cleaned['end_date'] = jd2.togregorian().date()
            except Exception:
                raise forms.ValidationError('فرمت تاریخ پایان صحیح نیست (YYYY/MM/DD)')

        # Normalize dates and times based on leave type
        lt = cleaned.get('leave_type')
        if lt == LeaveRequest.LeaveType.DAILY:
            cleaned['from_time'] = None
            cleaned['to_time'] = None
            if cleaned.get('start_date') and not cleaned.get('end_date'):
                cleaned['end_date'] = cleaned['start_date']
        elif lt == LeaveRequest.LeaveType.HOURLY:
            if not cleaned.get('from_time') or not cleaned.get('to_time'):
                raise forms.ValidationError('برای مرخصی ساعتی باید زمان شروع و پایان مشخص شود.')

        if cleaned.get('start_date') and cleaned.get('end_date'):
            if cleaned['end_date'] < cleaned['start_date']:
                raise forms.ValidationError('تاریخ پایان نمی‌تواند قبل از تاریخ شروع باشد.')

        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        cleaned = self.cleaned_data
        if 'start_date' in cleaned:
            obj.start_date = cleaned.get('start_date')
        if 'end_date' in cleaned:
            obj.end_date = cleaned.get('end_date')
        if commit:
            obj.save()
        return obj
