from datetime import date
from django.test import TestCase
from .forms import CustomerForm


class CustomerFormDateParsingTests(TestCase):
    def test_parse_jalali_date_input(self):
        form = CustomerForm(
            data={
                'bride_first_name': 'مریم',
                'bride_last_name': 'احمدی',
                'bride_phone': '09121234567',
                'ceremony_date': '۱۴۰۵/۰۳/۲۴',
                'how_to_know': 'اینستاگرام',
            }
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['ceremony_date'], date(2026, 6, 14))

    def test_parse_gregorian_date_input(self):
        form = CustomerForm(
            data={
                'bride_first_name': 'مریم',
                'bride_last_name': 'احمدی',
                'bride_phone': '09121234567',
                'ceremony_date': '2026/06/14',
                'how_to_know': 'اینستاگرام',
            }
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['ceremony_date'], date(2026, 6, 14))
