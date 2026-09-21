"""
تست‌های «بیعانه‌های مرحله‌ای» (پرداخت‌های چندمرحله‌ای رزرو).

پوشش:
    * سناریوهای موفق (افزودن/ویرایش/حذف پرداخت، شماره‌گذاری مرحله،
      تسویه، اضافه‌پرداخت، سازگاری داده قدیمی، فاکتور، یکسانی منبع محاسبات)
    * سناریوهای خطا (مبلغ، نوع، روش پرداخت، تاریخ‌ها، سقف مبلغ،
      ManagementForm، ویرایش هم‌زمان، حذف تصادفی داده قدیمی، دسترسی)

همه محاسبات از ``ReservationPaymentService`` خوانده می‌شوند تا ثابت شود
منبع حقیقت واحدی وجود دارد.
"""

from unittest.mock import patch

import jdatetime
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from customers.models import Customer
from financial.models import Transaction
from products.models import Dress
from reservations.constants import ReservationStatus
from reservations.forms import (
    ReservationPaymentFormSet,
    build_payment_formset,
    payment_formset_prefix,
)
from reservations.models import Reservation
from reservations.services.payment_stage_service import (
    LEGACY_BALANCE_ROW_ID,
    LEGACY_DEPOSIT_ROW_ID,
    ReservationPaymentService,
)


def create_user(username, role, password='password123'):
    extra_fields = {'role': role}
    if role == 'SUPER_ADMIN':
        extra_fields['is_superuser'] = True
        extra_fields['is_staff'] = True
    return User.objects.create_user(username=username, password=password, **extra_fields)


def today_jalali():
    return jdatetime.date.today().strftime('%Y/%m/%d')


class StagedPaymentTestBase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.customer = Customer.objects.create(
            bride_first_name='Staged',
            bride_last_name='Customer',
            bride_phone='09120009999',
            ceremony_date=jdatetime.date(1402, 1, 1),
            how_to_know='test',
            allow_contact=True,
        )
        cls.dress = Dress.objects.create(code='DS01', daily_rent_price=100000)
        cls.manager = create_user('stage_manager', 'MANAGER')
        cls.seller = create_user('stage_seller', 'SELLER')

    def setUp(self):
        self.client = Client()
        self.client.login(username='stage_manager', password='password123')

    # ------------------------------------------------------------------
    # ابزارهای کمکی
    # ------------------------------------------------------------------
    def make_reservation(self, **overrides):
        data = {
            'customer': self.customer,
            'dress': self.dress,
            'start_date': jdatetime.date(1402, 1, 1),
            'rental_days': 3,
            'status': ReservationStatus.CONFIRMED,
            'rent_price': 100000,
            'deposit_amount': 0,
            'remaining_payment_amount': 0,
            'discount_amount': 0,
            'final_price': 100000,
            'remaining_amount': 100000,
            'payment_method': 'CASH',
            'payment_tracking_code': 'PAY-1',
            'guarantee1_type': 'CASH',
            'guarantee1_tracking_code': 'G1',
            'created_by': self.manager,
        }
        data.update(overrides)
        return Reservation.objects.create(**data)

    def edit_payload(self, reservation, rows=None, prefix=None, revision=True):
        """Payload فرم ویرایش رزرو + ردیف‌های پرداخت مرحله‌ای."""
        prefix = prefix or payment_formset_prefix(reservation.pk)
        payload = {
            'dress': str(self.dress.pk),
            'start_date': '1402/01/02',
            'rental_days': '3',
            'discount_type': '',
            'discount_value': '0',
            'payment_method': 'CASH',
            'payment_tracking_code': 'PAY-EDIT',
            'guarantee1_type': 'CASH',
            'guarantee1_tracking_code': 'G1',
            'guarantee2_type': '',
            'guarantee2_tracking_code': '',
            'deposit_amount': '0',
        }
        if revision is True:
            payload['payment_revision'] = ReservationPaymentService.payment_revision(reservation)
        elif revision:
            payload['payment_revision'] = revision

        rows = rows or []
        payload[f'{prefix}-TOTAL_FORMS'] = str(len(rows))
        payload[f'{prefix}-INITIAL_FORMS'] = '0'
        payload[f'{prefix}-MIN_NUM_FORMS'] = '0'
        payload[f'{prefix}-MAX_NUM_FORMS'] = '1000'

        for index, row in enumerate(rows):
            for field, value in row.items():
                payload[f'{prefix}-{index}-{field}'] = value
        return payload

    def post_edit(self, reservation, rows=None, **kwargs):
        url = reverse('reservations:edit', args=[reservation.pk])
        payload = self.edit_payload(reservation, rows=rows, **kwargs)
        return self.client.post(url, payload, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

    def payments_of(self, reservation):
        return list(
            Transaction.objects.filter(
                reservation=reservation,
                transaction_type__in=ReservationPaymentService.STAGED_TYPES,
                transaction_status=Transaction.TransactionStatus.POSTED,
                is_voided=False,
            ).order_by('sequence_number', 'pk')
        )


# ======================================================================
# سناریوهای موفق
# ======================================================================
class StagedPaymentSuccessTests(StagedPaymentTestBase):

    def test_add_single_deposit_row_creates_transaction_and_syncs_caches(self):
        reservation = self.make_reservation()

        response = self.post_edit(reservation, rows=[{
            'id': '',
            'amount': '40000',
            'payment_type': 'DEPOSIT',
            'payment_date': today_jalali(),
            'due_date': '',
            'payment_method': 'CASH',
            'payment_reference': '',
            'description': 'بیعانه اول',
        }])

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['success'])

        reservation.refresh_from_db()
        payments = self.payments_of(reservation)
        self.assertEqual(len(payments), 1)
        self.assertEqual(payments[0].amount, 40000)
        self.assertEqual(payments[0].transaction_type, 'DEPOSIT')
        self.assertEqual(payments[0].sequence_number, 1)

        self.assertEqual(reservation.deposit_amount, 40000)
        self.assertEqual(reservation.remaining_amount, 60000)
        self.assertEqual(
            ReservationPaymentService.total_paid(reservation), 40000
        )

    def test_add_multiple_staged_deposits_receives_automatic_sequence_numbers(self):
        reservation = self.make_reservation()

        response = self.post_edit(reservation, rows=[
            {
                'id': '', 'amount': '20000', 'payment_type': 'DEPOSIT',
                'payment_date': today_jalali(), 'due_date': '',
                'payment_method': 'CASH', 'payment_reference': '',
                'description': 'بیعانه اول',
            },
            {
                'id': '', 'amount': '30000', 'payment_type': 'DEPOSIT',
                'payment_date': today_jalali(), 'due_date': '',
                'payment_method': 'CASH', 'payment_reference': '',
                'description': 'بیعانه دوم',
            },
            {
                'id': '', 'amount': '10000', 'payment_type': 'PARTIAL_PAYMENT',
                'payment_date': today_jalali(), 'due_date': '',
                'payment_method': 'CASH', 'payment_reference': '',
                'description': 'پرداخت تکمیلی',
            },
        ])

        self.assertEqual(response.status_code, 200, response.content)
        reservation.refresh_from_db()

        payments = self.payments_of(reservation)
        self.assertEqual([p.sequence_number for p in payments], [1, 2, 3])
        self.assertEqual([p.amount for p in payments], [20000, 30000, 10000])

        labels = [row['stage_label'] for row in ReservationPaymentService.serialize_payments(reservation)]
        self.assertEqual(labels, ['بیعانه اول', 'بیعانه دوم', 'پرداخت تکمیلی اول'])
        self.assertEqual(ReservationPaymentService.total_paid(reservation), 60000)

    def test_editing_existing_payment_updates_in_place_without_duplicate(self):
        reservation = self.make_reservation()
        self.post_edit(reservation, rows=[{
            'id': '', 'amount': '40000', 'payment_type': 'DEPOSIT',
            'payment_date': today_jalali(), 'due_date': '',
            'payment_method': 'CASH', 'payment_reference': '',
            'description': 'بیعانه اول',
        }])

        reservation.refresh_from_db()
        payment = self.payments_of(reservation)[0]

        response = self.post_edit(reservation, rows=[{
            'id': str(payment.pk),
            'amount': '55000',
            'payment_type': 'DEPOSIT',
            'payment_date': today_jalali(),
            'due_date': '',
            'payment_method': 'CASH',
            'payment_reference': '',
            'description': 'بیعانه اصلاح‌شده',
        }])

        self.assertEqual(response.status_code, 200, response.content)
        reservation.refresh_from_db()
        payments = self.payments_of(reservation)
        self.assertEqual(len(payments), 1)
        self.assertEqual(payments[0].pk, payment.pk)
        self.assertEqual(payments[0].amount, 55000)
        self.assertEqual(reservation.remaining_amount, 45000)

    def test_deleting_payment_soft_voids_and_keeps_history(self):
        reservation = self.make_reservation()
        self.post_edit(reservation, rows=[{
            'id': '', 'amount': '40000', 'payment_type': 'DEPOSIT',
            'payment_date': today_jalali(), 'due_date': '',
            'payment_method': 'CASH', 'payment_reference': '',
            'description': 'بیعانه اول',
        }])
        reservation.refresh_from_db()
        payment = self.payments_of(reservation)[0]

        # ردیف باقی‌مانده با مبلغ کمتر + حذف ردیف قبلی
        response = self.post_edit(reservation, rows=[
            {
                'id': str(payment.pk), 'amount': '40000', 'payment_type': 'DEPOSIT',
                'payment_date': today_jalali(), 'due_date': '',
                'payment_method': 'CASH', 'payment_reference': '',
                'description': 'بیعانه اول', 'DELETE': 'on',
            },
            {
                'id': '', 'amount': '15000', 'payment_type': 'DEPOSIT',
                'payment_date': today_jalali(), 'due_date': '',
                'payment_method': 'CASH', 'payment_reference': '',
                'description': 'بیعانه جدید',
            },
        ])

        self.assertEqual(response.status_code, 200, response.content)
        reservation.refresh_from_db()

        # رکورد قدیمی حذف فیزیکی نشده، فقط باطل شده است
        payment.refresh_from_db()
        self.assertEqual(payment.transaction_status, Transaction.TransactionStatus.VOIDED)
        self.assertTrue(payment.is_voided)

        active = self.payments_of(reservation)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].amount, 15000)
        self.assertEqual(ReservationPaymentService.total_paid(reservation), 15000)
        self.assertEqual(reservation.remaining_amount, 85000)

    def test_full_payment_marks_reservation_settled(self):
        reservation = self.make_reservation()

        response = self.post_edit(reservation, rows=[{
            'id': '', 'amount': '100000', 'payment_type': 'DEPOSIT',
            'payment_date': today_jalali(), 'due_date': '',
            'payment_method': 'CASH', 'payment_reference': '',
            'description': 'تسویه کامل',
        }])

        self.assertEqual(response.status_code, 200, response.content)
        reservation.refresh_from_db()
        self.assertEqual(reservation.remaining_amount, 0)

        status = ReservationPaymentService.settlement_status(reservation)
        self.assertEqual(status['code'], 'SETTLED')
        self.assertEqual(status['amount'], 0)

    def test_overpayment_is_blocked_by_model_validation(self):
        """مدل اجازه نمی‌دهد مبلغ پرداختی از مبلغ نهایی رزرو بیشتر شود."""
        from django.core.exceptions import ValidationError as DjangoValidationError

        reservation = self.make_reservation()

        with self.assertRaises((DjangoValidationError, Exception)):
            ReservationPaymentService.replace_staged_payments(
                reservation,
                [{
                    'id': None, 'amount': 150000, 'payment_type': 'DEPOSIT',
                    'payment_date': today_jalali(), 'due_date': '',
                    'payment_method': 'CASH', 'payment_reference': '',
                    'description': 'پرداخت مازاد',
                }],
                self.manager,
                allow_overpay=True,
            )

        reservation.refresh_from_db()
        self.assertEqual(self.payments_of(reservation), [])

    def test_overpaid_amount_is_reported_separately_from_remaining(self):
        """
        اگر مانده منفی شود (مثلاً پس از کاهش مبلغ نهایی)، سیستم هیچ‌گاه مانده
        منفی نشان نمی‌دهد؛ مبلغ اضافه‌پرداخت جداگانه گزارش می‌شود.
        """
        reservation = self.make_reservation()

        # مقدار در حافظه: پرداخت ۱۲۰٬۰۰۰ در برابر مبلغ کل ۱۰۰٬۰۰۰
        reservation.deposit_amount = 120000

        self.assertEqual(ReservationPaymentService.remaining_amount(reservation), -20000)
        self.assertEqual(ReservationPaymentService.outstanding_amount(reservation), 0)
        self.assertEqual(ReservationPaymentService.overpaid_amount(reservation), 20000)

        status = ReservationPaymentService.settlement_status(reservation)
        self.assertEqual(status['code'], 'OVERPAID')
        self.assertEqual(status['amount'], 20000)
        self.assertEqual(status['label'], 'اضافه‌پرداخت')

    def test_legacy_deposit_is_preserved_when_adding_new_staged_payment(self):
        """رزرو قدیمی: بیعانه کش‌شده باید حفظ شود، نه بازنویسی."""
        reservation = self.make_reservation(deposit_amount=50000)
        self.assertEqual(self.payments_of(reservation), [])

        # ردیف مجازی بیعانه قدیمی در فرم نمایش داده می‌شود
        rows = ReservationPaymentService.serialize_payments(reservation)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['id'], LEGACY_DEPOSIT_ROW_ID)
        self.assertTrue(rows[0]['is_legacy'])
        self.assertEqual(rows[0]['amount'], 50000)

        response = self.post_edit(reservation, rows=[
            {
                'id': str(LEGACY_DEPOSIT_ROW_ID), 'amount': '50000',
                'payment_type': 'DEPOSIT', 'payment_date': today_jalali(),
                'due_date': '', 'payment_method': 'CASH',
                'payment_reference': '', 'description': 'بیعانه اول',
            },
            {
                'id': '', 'amount': '20000', 'payment_type': 'DEPOSIT',
                'payment_date': today_jalali(), 'due_date': '',
                'payment_method': 'CASH', 'payment_reference': '',
                'description': 'بیعانه دوم',
            },
        ])

        self.assertEqual(response.status_code, 200, response.content)
        reservation.refresh_from_db()

        payments = self.payments_of(reservation)
        self.assertEqual([p.amount for p in payments], [50000, 20000])
        self.assertEqual(ReservationPaymentService.total_paid(reservation), 70000)
        self.assertEqual(reservation.deposit_amount, 70000)
        self.assertEqual(reservation.remaining_amount, 30000)

    def test_invoice_uses_same_calculation_source_as_reservation(self):
        reservation = self.make_reservation()
        self.post_edit(reservation, rows=[{
            'id': '', 'amount': '30000', 'payment_type': 'DEPOSIT',
            'payment_date': today_jalali(), 'due_date': '',
            'payment_method': 'CASH', 'payment_reference': 'RC-1',
            'description': 'بیعانه اول',
        }])
        reservation.refresh_from_db()

        summary = ReservationPaymentService.build_financial_summary(reservation)
        response = self.client.get(reverse('reservations:invoice', args=[reservation.pk]))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('فاکتور رزرو', content)
        self.assertIn('بیعانه اول', content)
        # مبلغ کل، مجموع پرداخت‌شده و مانده از همان سرویس می‌آیند
        self.assertEqual(summary['total_price'], 100000)
        self.assertEqual(summary['total_paid'], 30000)
        self.assertEqual(summary['remaining_amount'], 70000)
        self.assertEqual(response.context['summary']['total_paid'], summary['total_paid'])
        self.assertEqual(
            response.context['summary']['remaining_amount'], summary['remaining_amount']
        )

    def test_financial_section_and_reservation_report_identical_totals(self):
        reservation = self.make_reservation()
        self.post_edit(reservation, rows=[
            {
                'id': '', 'amount': '25000', 'payment_type': 'DEPOSIT',
                'payment_date': today_jalali(), 'due_date': '',
                'payment_method': 'CASH', 'payment_reference': '',
                'description': 'بیعانه اول',
            },
            {
                'id': '', 'amount': '15000', 'payment_type': 'PARTIAL_PAYMENT',
                'payment_date': today_jalali(), 'due_date': '',
                'payment_method': 'CASH', 'payment_reference': '',
                'description': 'پرداخت تکمیلی',
            },
        ])
        reservation.refresh_from_db()

        summary = ReservationPaymentService.build_financial_summary(reservation)

        financial_url = reverse('financial:reservation_financial', args=[reservation.pk])
        financial_response = self.client.get(financial_url)
        self.assertEqual(financial_response.status_code, 200)

        detail_response = self.client.get(
            reverse('reservations:detail', args=[reservation.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(detail_response.status_code, 200)

        self.assertEqual(summary['total_paid'], 40000)
        self.assertEqual(summary['total_deposit'], 25000)
        self.assertEqual(summary['total_balance_payments'], 15000)
        self.assertEqual(summary['remaining_amount'], 60000)
        # مجموع پرداخت‌ها هرگز دو بار شمرده نمی‌شود
        self.assertEqual(
            summary['total_paid'],
            summary['total_deposit'] + summary['total_balance_payments'],
        )
        self.assertIn('staged_payments', financial_response.context)
        self.assertEqual(
            financial_response.context['payment_summary']['total_paid'],
            summary['total_paid'],
        )

    def test_persian_digits_and_thousand_separators_are_accepted(self):
        reservation = self.make_reservation()

        response = self.post_edit(reservation, rows=[{
            'id': '', 'amount': '۱٬۲۵۰', 'payment_type': 'DEPOSIT',
            'payment_date': today_jalali(), 'due_date': '',
            'payment_method': 'CASH', 'payment_reference': '',
            'description': 'مبلغ با اعداد فارسی',
        }])

        self.assertEqual(response.status_code, 200, response.content)
        reservation.refresh_from_db()
        self.assertEqual(ReservationPaymentService.total_paid(reservation), 1250)


# ======================================================================
# سناریوهای خطا
# ======================================================================
class StagedPaymentValidationErrorTests(StagedPaymentTestBase):

    def _assert_payment_error(self, response, expected_fragment):
        self.assertIn(response.status_code, (200, 400), response.content)
        payload = response.json()
        self.assertFalse(payload['success'], payload)
        errors = payload.get('errors', {})
        joined = ' | '.join(
            str(item)
            for value in errors.values()
            for item in (value if isinstance(value, (list, tuple)) else [value])
        )
        self.assertIn(expected_fragment, joined, joined)
        return payload

    # --- اعتبارسنجی مبلغ ------------------------------------------------
    def test_error_amount_missing_but_other_fields_filled(self):
        reservation = self.make_reservation()
        response = self.post_edit(reservation, rows=[{
            'id': '', 'amount': '', 'payment_type': 'DEPOSIT',
            'payment_date': today_jalali(), 'due_date': '',
            'payment_method': 'CASH', 'payment_reference': 'RC-9',
            'description': 'بدون مبلغ',
        }])
        self._assert_payment_error(response, 'مبلغ پرداخت الزامی است.')

    def test_error_amount_zero(self):
        reservation = self.make_reservation()
        response = self.post_edit(reservation, rows=[{
            'id': '', 'amount': '0', 'payment_type': 'DEPOSIT',
            'payment_date': today_jalali(), 'due_date': '',
            'payment_method': 'CASH', 'payment_reference': '',
            'description': 'صفر',
        }])
        self._assert_payment_error(response, 'مبلغ پرداخت باید بیشتر از صفر باشد.')

    def test_error_amount_negative(self):
        reservation = self.make_reservation()
        response = self.post_edit(reservation, rows=[{
            'id': '', 'amount': '-5000', 'payment_type': 'DEPOSIT',
            'payment_date': today_jalali(), 'due_date': '',
            'payment_method': 'CASH', 'payment_reference': '',
            'description': 'منفی',
        }])
        self._assert_payment_error(response, 'مبلغ پرداخت نمی‌تواند منفی باشد.')

    def test_error_amount_not_numeric(self):
        reservation = self.make_reservation()
        response = self.post_edit(reservation, rows=[{
            'id': '', 'amount': 'abc', 'payment_type': 'DEPOSIT',
            'payment_date': today_jalali(), 'due_date': '',
            'payment_method': 'CASH', 'payment_reference': '',
            'description': 'غیرعددی',
        }])
        self._assert_payment_error(response, 'مبلغ پرداخت باید یک عدد صحیح باشد.')

    # --- اعتبارسنجی نوع/روش پرداخت -------------------------------------
    def test_error_invalid_payment_type(self):
        reservation = self.make_reservation()
        response = self.post_edit(reservation, rows=[{
            'id': '', 'amount': '10000', 'payment_type': 'NOT_A_TYPE',
            'payment_date': today_jalali(), 'due_date': '',
            'payment_method': 'CASH', 'payment_reference': '',
            'description': 'نوع نامعتبر',
        }])
        self._assert_payment_error(response, 'نوع پرداخت نامعتبر است.')

    def test_error_invalid_payment_method(self):
        reservation = self.make_reservation()
        response = self.post_edit(reservation, rows=[{
            'id': '', 'amount': '10000', 'payment_type': 'DEPOSIT',
            'payment_date': today_jalali(), 'due_date': '',
            'payment_method': 'CRYPTO', 'payment_reference': 'X',
            'description': 'روش نامعتبر',
        }])
        self._assert_payment_error(response, 'روش پرداخت نامعتبر است.')

    def test_error_non_cash_method_requires_tracking_code(self):
        reservation = self.make_reservation()
        response = self.post_edit(reservation, rows=[{
            'id': '', 'amount': '10000', 'payment_type': 'DEPOSIT',
            'payment_date': today_jalali(), 'due_date': '',
            'payment_method': 'TRANSFER', 'payment_reference': '',
            'description': 'بدون کد رهگیری',
        }])
        self._assert_payment_error(
            response, 'برای روش پرداخت غیرنقدی باید کد رهگیری وارد شود.'
        )

    # --- اعتبارسنجی تاریخ ----------------------------------------------
    def test_error_invalid_payment_date(self):
        reservation = self.make_reservation()
        response = self.post_edit(reservation, rows=[{
            'id': '', 'amount': '10000', 'payment_type': 'DEPOSIT',
            'payment_date': '1400/13/45', 'due_date': '',
            'payment_method': 'CASH', 'payment_reference': '',
            'description': 'تاریخ نامعتبر',
        }])
        self._assert_payment_error(response, 'تاریخ پرداخت نامعتبر است.')

    def test_error_invalid_due_date(self):
        reservation = self.make_reservation()
        response = self.post_edit(reservation, rows=[{
            'id': '', 'amount': '10000', 'payment_type': 'DEPOSIT',
            'payment_date': today_jalali(), 'due_date': 'not-a-date',
            'payment_method': 'CASH', 'payment_reference': '',
            'description': 'سررسید نامعتبر',
        }])
        self._assert_payment_error(response, 'تاریخ سررسید نامعتبر است.')

    def test_error_due_date_before_payment_date(self):
        reservation = self.make_reservation()
        response = self.post_edit(reservation, rows=[{
            'id': '', 'amount': '10000', 'payment_type': 'DEPOSIT',
            'payment_date': '1402/05/10', 'due_date': '1402/05/01',
            'payment_method': 'CASH', 'payment_reference': '',
            'description': 'ترتیب اشتباه',
        }])
        self._assert_payment_error(
            response, 'تاریخ سررسید نمی‌تواند قبل از تاریخ پرداخت باشد.'
        )

    def test_error_payment_date_before_reservation_creation(self):
        reservation = self.make_reservation()
        response = self.post_edit(reservation, rows=[{
            'id': '', 'amount': '10000', 'payment_type': 'DEPOSIT',
            'payment_date': '1400/01/01', 'due_date': '',
            'payment_method': 'CASH', 'payment_reference': '',
            'description': 'قبل از ثبت رزرو',
        }])
        self._assert_payment_error(
            response, 'تاریخ پرداخت نمی‌تواند قبل از تاریخ ثبت رزرو باشد.'
        )

    # --- اعتبارسنجی سقف مبلغ -------------------------------------------
    def test_error_total_exceeds_reservation_price(self):
        reservation = self.make_reservation()
        response = self.post_edit(reservation, rows=[{
            'id': '', 'amount': '150000', 'payment_type': 'DEPOSIT',
            'payment_date': today_jalali(), 'due_date': '',
            'payment_method': 'CASH', 'payment_reference': '',
            'description': 'بیش از مبلغ کل',
        }])
        self._assert_payment_error(response, 'بیشتر شود')

        reservation.refresh_from_db()
        self.assertEqual(self.payments_of(reservation), [])
        self.assertEqual(reservation.deposit_amount, 0)

    def test_error_management_form_missing_returns_persian_message(self):
        reservation = self.make_reservation()
        prefix = payment_formset_prefix(reservation.pk)

        payload = {
            'dress': str(self.dress.pk),
            'start_date': '1402/01/02',
            'rental_days': '3',
            'discount_type': '',
            'discount_value': '0',
            'payment_method': 'CASH',
            'payment_tracking_code': 'PAY-EDIT',
            'guarantee1_type': 'CASH',
            'guarantee1_tracking_code': 'G1',
            'guarantee2_type': '',
            'guarantee2_tracking_code': '',
            'deposit_amount': '0',
            f'{prefix}-0-amount': '10000',
        }

        response = self.client.post(
            reverse('reservations:edit', args=[reservation.pk]),
            payload,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self._assert_payment_error(
            response, 'فرم پرداخت‌ها ناقص ارسال شده است. لطفاً صفحه را دوباره بارگذاری کنید.'
        )

    # --- کنترل هم‌زمانی / ارسال دوباره ---------------------------------
    def test_error_stale_revision_is_rejected(self):
        reservation = self.make_reservation()
        response = self.post_edit(
            reservation,
            rows=[{
                'id': '', 'amount': '10000', 'payment_type': 'DEPOSIT',
                'payment_date': today_jalali(), 'due_date': '',
                'payment_method': 'CASH', 'payment_reference': '',
                'description': 'ویرایش هم‌زمان',
            }],
            revision='2000-01-01T00:00:00+00:00',
        )
        self._assert_payment_error(response, 'توسط کاربر دیگری تغییر کرده است')

    def test_error_stale_legacy_state_is_rejected_instead_of_wiping_data(self):
        """
        اگر بین بارگذاری صفحه و ارسال، مقدار کش‌شده قدیمی ایجاد شده باشد و
        کلاینت هیچ ردیفی نفرستد، به‌جای پاک کردن داده خطا برمی‌گردد.
        """
        reservation = self.make_reservation(deposit_amount=50000)

        url = reverse('reservations:edit', args=[reservation.pk])
        prefix = payment_formset_prefix(reservation.pk)
        response = self.client.post(url, {
            'dress': str(self.dress.pk),
            'start_date': '1402/01/02',
            'rental_days': '3',
            'discount_type': '',
            'discount_value': '0',
            'payment_method': 'CASH',
            'payment_tracking_code': 'PAY-EDIT',
            'guarantee1_type': 'CASH',
            'guarantee1_tracking_code': 'G1',
            'guarantee2_type': '',
            'guarantee2_tracking_code': '',
            'deposit_amount': '0',
            f'{prefix}-TOTAL_FORMS': '0',
            f'{prefix}-INITIAL_FORMS': '0',
            f'{prefix}-MIN_NUM_FORMS': '0',
            f'{prefix}-MAX_NUM_FORMS': '1000',
            'payment_revision': ReservationPaymentService.payment_revision(reservation),
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self._assert_payment_error(
            response, 'اطلاعات پرداخت این رزرو قدیمی است. لطفاً صفحه را دوباره بارگذاری کنید.'
        )

        reservation.refresh_from_db()
        self.assertEqual(reservation.deposit_amount, 50000)
        self.assertEqual(self.payments_of(reservation), [])

    def test_error_legacy_form_cannot_silently_zero_legacy_deposit(self):
        """
        فرم قدیمی که فیلد بیعانه را صفر می‌فرستد نباید بیعانه ثبت‌شده را
        بی‌صدا از بین ببرد.
        """
        reservation = self.make_reservation(deposit_amount=50000)

        url = reverse('reservations:edit', args=[reservation.pk])
        response = self.client.post(url, {
            'dress': str(self.dress.pk),
            'start_date': '1402/01/02',
            'rental_days': '3',
            'discount_type': '',
            'discount_value': '0',
            'payment_method': 'CASH',
            'payment_tracking_code': 'PAY-EDIT',
            'guarantee1_type': 'CASH',
            'guarantee1_tracking_code': 'G1',
            'guarantee2_type': '',
            'guarantee2_tracking_code': '',
            'deposit_amount': '0',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self._assert_payment_error(
            response, 'اطلاعات پرداخت این رزرو قدیمی است. لطفاً صفحه را دوباره بارگذاری کنید.'
        )

        reservation.refresh_from_db()
        self.assertEqual(reservation.deposit_amount, 50000)

    def test_error_legacy_form_without_payment_payload_keeps_balance_ledger(self):
        """
        فراخوانی قدیمی (بدون formset): مقدار پرداخت باقی‌مانده نباید گم شود و
        باید به یک تراکنش واقعی تبدیل شود.
        """
        reservation = self.make_reservation(
            deposit_amount=0, remaining_payment_amount=50000
        )

        url = reverse('reservations:edit', args=[reservation.pk])
        response = self.client.post(url, {
            'dress': str(self.dress.pk),
            'start_date': '1402/01/02',
            'rental_days': '3',
            'discount_type': '',
            'discount_value': '0',
            'payment_method': 'CASH',
            'payment_tracking_code': 'PAY-EDIT',
            'guarantee1_type': 'CASH',
            'guarantee1_tracking_code': 'G1',
            'guarantee2_type': '',
            'guarantee2_tracking_code': '',
            'deposit_amount': '0',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['success'])

        reservation.refresh_from_db()
        self.assertEqual(
            ReservationPaymentService.total_paid(reservation), 50000
        )
        self.assertEqual(reservation.remaining_amount, 50000)

    def test_error_seller_cannot_edit_staged_payments(self):
        reservation = self.make_reservation()
        self.client.logout()
        self.client.login(username='stage_seller', password='password123')

        response = self.post_edit(reservation, rows=[{
            'id': '', 'amount': '10000', 'payment_type': 'DEPOSIT',
            'payment_date': today_jalali(), 'due_date': '',
            'payment_method': 'CASH', 'payment_reference': '',
            'description': 'تلاش فروشنده',
        }])

        self.assertEqual(response.status_code, 403)
        reservation.refresh_from_db()
        self.assertEqual(self.payments_of(reservation), [])

    def test_error_blank_row_is_ignored_and_does_not_create_payment(self):
        reservation = self.make_reservation()
        response = self.post_edit(reservation, rows=[{
            'id': '', 'amount': '', 'payment_type': 'DEPOSIT',
            'payment_date': '', 'due_date': '',
            'payment_method': '', 'payment_reference': '',
            'description': '',
        }])

        self.assertEqual(response.status_code, 200, response.content)
        reservation.refresh_from_db()
        self.assertEqual(self.payments_of(reservation), [])

    def test_error_cancelled_reservation_cannot_receive_new_payments(self):
        reservation = self.make_reservation(status=ReservationStatus.CANCELLED)
        response = self.post_edit(reservation, rows=[{
            'id': '', 'amount': '10000', 'payment_type': 'DEPOSIT',
            'payment_date': today_jalali(), 'due_date': '',
            'payment_method': 'CASH', 'payment_reference': '',
            'description': 'رزرو لغوشده',
        }])

        payload = response.json()
        self.assertFalse(payload['success'])
        reservation.refresh_from_db()
        self.assertEqual(self.payments_of(reservation), [])


# ======================================================================
# سازگاری عقب‌رو / ضد Race Condition
# ======================================================================
class StagedPaymentBackwardCompatibilityTests(StagedPaymentTestBase):

    def test_legacy_reservation_totals_fall_back_to_cached_values(self):
        reservation = self.make_reservation(
            deposit_amount=50000, remaining_payment_amount=20000
        )

        self.assertEqual(ReservationPaymentService.total_deposit(reservation), 50000)
        self.assertEqual(ReservationPaymentService.total_balance_payments(reservation), 20000)
        self.assertEqual(ReservationPaymentService.total_paid(reservation), 70000)
        self.assertEqual(ReservationPaymentService.remaining_amount(reservation), 30000)
        self.assertTrue(reservation.has_paid_deposit)

    def test_recording_final_payment_does_not_drop_legacy_deposit(self):
        reservation = self.make_reservation(deposit_amount=50000, remaining_payment_amount=50000)

        from financial.services.payment_service import PaymentService

        PaymentService.record_balance_payment(
            reservation=reservation,
            amount=50000,
            created_by=self.manager,
            payment_method='CASH',
            external_reference='RC-FINAL',
        )

        reservation.refresh_from_db()
        # بیعانه قدیمی حفظ شده و پرداخت نهایی نیز ثبت شده است
        self.assertEqual(ReservationPaymentService.total_deposit(reservation), 50000)
        self.assertEqual(ReservationPaymentService.total_balance_payments(reservation), 50000)
        self.assertEqual(ReservationPaymentService.total_paid(reservation), 100000)
        self.assertEqual(reservation.remaining_amount, 0)
        self.assertEqual(ReservationPaymentService.settlement_status(reservation)['code'], 'SETTLED')

    def test_materialize_legacy_payments_is_idempotent(self):
        reservation = self.make_reservation(deposit_amount=50000, remaining_payment_amount=50000)

        first = ReservationPaymentService.materialize_legacy_payments(reservation, self.manager)
        second = ReservationPaymentService.materialize_legacy_payments(reservation, self.manager)

        self.assertEqual(len(first), 2)
        self.assertEqual(second, {})
        self.assertEqual(len(self.payments_of(reservation)), 2)

        reservation.refresh_from_db()
        self.assertEqual(reservation.deposit_amount, 50000)
        self.assertEqual(reservation.remaining_payment_amount, 50000)
        self.assertEqual(ReservationPaymentService.total_paid(reservation), 100000)

    def test_legacy_balance_row_is_editable_without_data_loss(self):
        reservation = self.make_reservation(deposit_amount=50000, remaining_payment_amount=50000)

        rows = ReservationPaymentService.serialize_payments(reservation)
        ids = {row['id'] for row in rows}
        self.assertEqual(ids, {LEGACY_DEPOSIT_ROW_ID, LEGACY_BALANCE_ROW_ID})

        response = self.post_edit(reservation, rows=[
            {
                'id': str(LEGACY_DEPOSIT_ROW_ID), 'amount': '50000',
                'payment_type': 'DEPOSIT', 'payment_date': today_jalali(),
                'due_date': '', 'payment_method': 'CASH',
                'payment_reference': '', 'description': 'بیعانه اول',
            },
            {
                'id': str(LEGACY_BALANCE_ROW_ID), 'amount': '20000',
                'payment_type': 'FINAL_PAYMENT', 'payment_date': today_jalali(),
                'due_date': '', 'payment_method': 'CASH',
                'payment_reference': '', 'description': 'پرداخت نهایی اصلاح‌شده',
            },
        ])

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['success'], response.json())
        reservation.refresh_from_db()

        payments = self.payments_of(reservation)
        self.assertEqual(sorted(p.amount for p in payments), [20000, 50000])
        self.assertEqual(ReservationPaymentService.total_paid(reservation), 70000)
        self.assertEqual(ReservationPaymentService.total_balance_payments(reservation), 20000)

    def test_backfill_sequence_numbers_is_idempotent(self):
        reservation = self.make_reservation()
        self.post_edit(reservation, rows=[
            {
                'id': '', 'amount': '10000', 'payment_type': 'DEPOSIT',
                'payment_date': today_jalali(), 'due_date': '',
                'payment_method': 'CASH', 'payment_reference': '',
                'description': 'اول',
            },
            {
                'id': '', 'amount': '20000', 'payment_type': 'DEPOSIT',
                'payment_date': today_jalali(), 'due_date': '',
                'payment_method': 'CASH', 'payment_reference': '',
                'description': 'دوم',
            },
        ])
        reservation.refresh_from_db()

        # پاک کردن شماره‌ها برای شبیه‌سازی داده قدیمی
        Transaction.objects.filter(reservation=reservation).update(sequence_number=None)

        first = ReservationPaymentService.backfill_sequence_numbers()
        second = ReservationPaymentService.backfill_sequence_numbers()

        self.assertEqual(first, 2)
        self.assertEqual(second, 0)
        payments = self.payments_of(reservation)
        self.assertEqual([p.sequence_number for p in payments], [1, 2])

    def test_concurrent_edit_is_blocked_by_row_lock(self):
        """اگر رکورد بین خواندن و نوشتن تغییر کند، درخواست رد می‌شود."""
        reservation = self.make_reservation()
        stale_revision = ReservationPaymentService.payment_revision(reservation)

        # شبیه‌سازی ویرایش کاربر دیگر
        reservation.payment_tracking_code = 'CHANGED-BY-OTHER'
        reservation.save(update_fields=['payment_tracking_code', 'updated_at'])

        url = reverse('reservations:edit', args=[reservation.pk])
        prefix = payment_formset_prefix(reservation.pk)
        payload = self.edit_payload(reservation, rows=[{
            'id': '', 'amount': '10000', 'payment_type': 'DEPOSIT',
            'payment_date': today_jalali(), 'due_date': '',
            'payment_method': 'CASH', 'payment_reference': '',
            'description': 'نوشتن با نسخه قدیمی',
        }])
        payload['payment_revision'] = stale_revision

        response = self.client.post(url, payload, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        payload_json = response.json()
        self.assertFalse(payload_json['success'])
        self.assertEqual(self.payments_of(reservation), [])

    def test_service_rejects_overpay_without_allow_flag(self):
        reservation = self.make_reservation()

        from reservations.services.payment_stage_service import PaymentStageError

        with self.assertRaises(PaymentStageError):
            ReservationPaymentService.replace_staged_payments(
                reservation,
                [{
                    'id': None, 'amount': 150000, 'payment_type': 'DEPOSIT',
                    'payment_date': today_jalali(), 'due_date': '',
                    'payment_method': 'CASH', 'payment_reference': '',
                    'description': 'بیش از حد',
                }],
                self.manager,
            )

        self.assertEqual(self.payments_of(reservation), [])


# ======================================================================
# فرم/Formset
# ======================================================================
class StagedPaymentFormsetTests(StagedPaymentTestBase):

    def test_formset_prefix_is_unique_per_reservation(self):
        self.assertEqual(payment_formset_prefix(12), 'payments-12')
        self.assertEqual(payment_formset_prefix(13), 'payments-13')
        self.assertNotEqual(payment_formset_prefix(12), payment_formset_prefix(13))

    def test_build_formset_prefills_existing_payments(self):
        reservation = self.make_reservation()
        self.post_edit(reservation, rows=[
            {
                'id': '', 'amount': '10000', 'payment_type': 'DEPOSIT',
                'payment_date': today_jalali(), 'due_date': '',
                'payment_method': 'CASH', 'payment_reference': '',
                'description': 'اول',
            },
            {
                'id': '', 'amount': '20000', 'payment_type': 'PARTIAL_PAYMENT',
                'payment_date': today_jalali(), 'due_date': '',
                'payment_method': 'CASH', 'payment_reference': '',
                'description': 'دوم',
            },
        ])
        reservation.refresh_from_db()

        formset = build_payment_formset(reservation)
        self.assertEqual(len(formset.forms), 2)
        amounts = sorted(form.initial['amount'] for form in formset.forms)
        self.assertEqual(amounts, [10000, 20000])
        for form in formset.forms:
            self.assertTrue(form.initial['id'])

    def test_formset_uses_correct_management_form_counts(self):
        reservation = self.make_reservation()
        formset = build_payment_formset(reservation)
        prefix = payment_formset_prefix(reservation.pk)

        rendered = formset.management_form.as_p()
        for field in ('TOTAL_FORMS', 'INITIAL_FORMS', 'MIN_NUM_FORMS', 'MAX_NUM_FORMS'):
            self.assertIn(f'{prefix}-{field}', rendered)

    def test_formset_extra_is_zero_so_no_phantom_rows(self):
        reservation = self.make_reservation()
        formset = build_payment_formset(reservation)
        self.assertEqual(len(formset.forms), 0)

    def test_formset_class_is_reused_for_every_reservation(self):
        reservation = self.make_reservation()
        formset = build_payment_formset(reservation)
        self.assertIsInstance(formset, ReservationPaymentFormSet)

    def test_validation_errors_preserve_submitted_values(self):
        reservation = self.make_reservation()
        prefix = payment_formset_prefix(reservation.pk)
        data = {
            f'{prefix}-TOTAL_FORMS': '1',
            f'{prefix}-INITIAL_FORMS': '0',
            f'{prefix}-MIN_NUM_FORMS': '0',
            f'{prefix}-MAX_NUM_FORMS': '1000',
            f'{prefix}-0-id': '',
            f'{prefix}-0-amount': '45000',
            f'{prefix}-0-payment_type': 'DEPOSIT',
            f'{prefix}-0-payment_date': '1402/01/02',
            f'{prefix}-0-due_date': '',
            f'{prefix}-0-payment_method': 'TRANSFER',
            f'{prefix}-0-payment_reference': '',
            f'{prefix}-0-description': 'توضیح حفظ‌شده',
        }

        formset = build_payment_formset(reservation, data=data)
        # روش پرداخت غیرنقدی بدون کد رهگیری -> خطا
        self.assertFalse(formset.is_valid())
        self.assertIn(
            'برای روش پرداخت غیرنقدی باید کد رهگیری وارد شود.',
            str(formset.forms[0].errors),
        )

        form = formset.forms[0]
        # مقادیر واردشده پس از خطا حفظ می‌شوند
        self.assertEqual(form['amount'].value(), '45000')
        self.assertEqual(form['payment_date'].value(), '1402/01/02')
        self.assertEqual(form['payment_method'].value(), 'TRANSFER')
        self.assertEqual(form['description'].value(), 'توضیح حفظ‌شده')
        self.assertEqual(form['payment_type'].value(), 'DEPOSIT')


# ======================================================================
# رندر قالب (رابط کاربری بخش بیعانه‌ها)
# ======================================================================
class StagedPaymentTemplateTests(StagedPaymentTestBase):

    def test_reservation_list_renders_staged_payment_section(self):
        reservation = self.make_reservation()

        response = self.client.get(reverse('reservations:list'))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('js-staged-payments', content)
        self.assertIn('js-payment-template', content)
        self.assertIn('افزودن بیعانه', content)
        self.assertIn('js-add-payment', content)

        # مدیریت فرم برای هر رزرو با پیشوند یکتا رندر می‌شود
        prefix = payment_formset_prefix(reservation.pk)
        self.assertIn(f'{prefix}-TOTAL_FORMS', content)
        self.assertIn(f'{prefix}-INITIAL_FORMS', content)
        self.assertIn(f'{prefix}-MAX_NUM_FORMS', content)

    def test_edit_modal_shows_legacy_deposit_row_with_negative_id(self):
        reservation = self.make_reservation(deposit_amount=50000)

        response = self.client.get(reverse('reservations:list'))
        content = response.content.decode('utf-8')

        prefix = payment_formset_prefix(reservation.pk)
        self.assertIn(f'value="{LEGACY_DEPOSIT_ROW_ID}"', content)
        self.assertIn('بیعانه اول (داده قدیمی)', content)

    def test_edit_modal_shows_existing_payments_for_editing(self):
        reservation = self.make_reservation()
        self.post_edit(reservation, rows=[{
            'id': '', 'amount': '30000', 'payment_type': 'DEPOSIT',
            'payment_date': today_jalali(), 'due_date': '',
            'payment_method': 'CASH', 'payment_reference': 'RC-77',
            'description': 'بیعانه اول',
        }])
        reservation.refresh_from_db()

        response = self.client.get(reverse('reservations:list'))
        content = response.content.decode('utf-8')

        self.assertIn('RC-77', content)
        self.assertIn('بیعانه اول', content)

    def test_reservation_list_does_not_duplicate_form_ids_across_reservations(self):
        first = self.make_reservation()
        second = self.make_reservation()

        response = self.client.get(reverse('reservations:list'))
        content = response.content.decode('utf-8')

        first_prefix = payment_formset_prefix(first.pk)
        second_prefix = payment_formset_prefix(second.pk)
        self.assertNotEqual(first_prefix, second_prefix)

        # هر شناسه/نام باید دقیقاً یک بار در صفحه وجود داشته باشد
        for prefix in (first_prefix, second_prefix):
            self.assertEqual(
                content.count(f'name="{prefix}-TOTAL_FORMS"'),
                1,
                f'شناسه تکراری برای {prefix}',
            )

    def test_invoice_renders_empty_state_without_payments(self):
        reservation = self.make_reservation()

        response = self.client.get(reverse('reservations:invoice', args=[reservation.pk]))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('هیچ پرداختی برای این رزرو ثبت نشده است.', content)
        self.assertEqual(response.context['summary']['total_paid'], 0)


# ======================================================================
# محافظ تحویل (رفع ایرادات بحرانی C-2 و C-3)
# ======================================================================
class DeliveryPaymentGuardTests(StagedPaymentTestBase):
    """
    محافظ تحویل نباید به‌صرفِ وجود مقدار در ``remaining_payment_amount``
    (فیلد کش) تحویل را مجاز کند. تنها معیار، ماندهٔ واقعی بر پایه
    پرداخت‌های معتبر است.

    این تست‌ها دو حفرهٔ اثبات‌شدهٔ بحرانی را قفل می‌کنند:
        * C-2: تحویل با پرداخت جزئی
        * C-3: تحویل بدون هیچ پرداخت واقعی
    """

    def setUp(self):
        super().setUp()
        from reservations.services.payment_guards import PaymentGuardService
        self.guard = PaymentGuardService

    def test_delivery_rejected_when_cache_value_is_trusted_without_real_payment(self):
        """
        C-3 (بازتولید دقیق گزارش): رزروی با ``remaining_payment_amount = 1``
        و صفر تراکنش نباید تحویل شود؛ چون کش هرگز نباید منبع حقیقت باشد.
        """
        reservation = self.make_reservation(
            final_price=100000,
            deposit_amount=0,
            remaining_payment_amount=1,  # کش بی‌پشتوانه
        )

        self.assertEqual(ReservationPaymentService.core_remaining_amount(reservation), 99999)

        with self.assertRaises(ValueError) as ctx:
            self.guard.verify_payment_for_delivery(reservation)

        self.assertIn('باقی‌مانده', str(ctx.exception))

    def test_delivery_rejected_with_partial_cache_value(self):
        """
        C-2 (بازتولید دقیق گزارش): ۱۰۰٬۰۰۰ تومان قیمت، صفر بیعانه و فقط
        ۳۰٬۰۰۰ کش پرداخت تکمیلی → مانده ۷۰٬۰۰۰ است و تحویل باید رد شود.
        """
        reservation = self.make_reservation(
            final_price=100000,
            deposit_amount=0,
            remaining_payment_amount=30000,
        )

        self.assertEqual(ReservationPaymentService.core_remaining_amount(reservation), 70000)

        with self.assertRaises(ValueError):
            self.guard.verify_payment_for_delivery(reservation)

    def test_delivery_rejected_when_only_partial_payment_registered(self):
        """C-2: پرداخت جزئی نباید تحویل را مجاز کند."""
        reservation = self.make_reservation(
            final_price=100000,
            deposit_amount=0,
            remaining_payment_amount=0,
        )
        response = self.post_edit(reservation, rows=[{
            'id': '',
            'amount': '40000',
            'payment_type': 'DEPOSIT',
            'payment_date': today_jalali(),
            'due_date': '',
            'payment_method': 'CASH',
            'payment_reference': '',
            'description': 'بیعانه جزئی',
        }])
        self.assertEqual(response.status_code, 200, response.content)
        reservation.refresh_from_db()

        # مانده واقعی = 60000 → تحویل باید رد شود
        self.assertEqual(ReservationPaymentService.core_remaining_amount(reservation), 60000)
        with self.assertRaises(ValueError):
            self.guard.verify_payment_for_delivery(reservation)

    def test_delivery_allowed_when_fully_settled_by_staged_payments(self):
        """تسویه کامل مرحله‌ای باید تحویل را مجاز کند."""
        reservation = self.make_reservation(
            final_price=100000,
            deposit_amount=0,
            remaining_payment_amount=0,
        )
        response = self.post_edit(reservation, rows=[
            {
                'id': '',
                'amount': '40000',
                'payment_type': 'DEPOSIT',
                'payment_date': today_jalali(),
                'due_date': '',
                'payment_method': 'CASH',
                'payment_reference': '',
                'description': 'بیعانه',
            },
            {
                'id': '',
                'amount': '60000',
                'payment_type': 'FINAL_PAYMENT',
                'payment_date': today_jalali(),
                'due_date': '',
                'payment_method': 'CASH',
                'payment_reference': '',
                'description': 'تسویه',
            },
        ])
        self.assertEqual(response.status_code, 200, response.content)
        reservation.refresh_from_db()

        self.assertEqual(ReservationPaymentService.core_remaining_amount(reservation), 0)
        self.assertTrue(self.guard.verify_payment_for_delivery(reservation))

    def test_delivery_allowed_for_fully_paid_legacy_reservation(self):
        """سازگاری عقب‌رو: رزرو قدیمی با بیعانهٔ کامل باید مجاز بماند."""
        reservation = self.make_reservation(
            final_price=100000,
            deposit_amount=100000,
            remaining_payment_amount=0,
        )

        self.assertEqual(ReservationPaymentService.core_remaining_amount(reservation), 0)
        self.assertTrue(self.guard.verify_payment_for_delivery(reservation))

    def test_change_status_to_delivered_is_blocked_when_balance_remains(self):
        """مسیر واقعی تغییر وضعیت هم باید تحویل با مانده را رد کند."""
        from reservations.services.change_status import ReservationStatusService

        reservation = self.make_reservation(
            status=ReservationStatus.CONFIRMED,
            final_price=100000,
            deposit_amount=0,
            remaining_payment_amount=30000,  # مانده ۷۰٬۰۰۰
        )

        with self.assertRaises(ValueError):
            ReservationStatusService.change_status(
                reservation, ReservationStatus.DELIVERED, self.manager
            )

        reservation.refresh_from_db()
        self.assertEqual(reservation.status, ReservationStatus.CONFIRMED)


# ======================================================================
# رگرسیون: ویرایش همزمان فیلدهای فرم و پرداخت‌های مرحله‌ای
# ======================================================================
class EditPreservesFormFieldsWithPaymentsTests(StagedPaymentTestBase):
    """
    وقتی فرم ویرایش رزرو همراه با «پرداخت‌های مرحله‌ای» ارسال می‌شود،
    تغییر فیلدهای غیرمالی (شماره قرارداد، تاریخ شروع، لباس) نباید از
    دست برود. این تست جلوی رگرسیون ناشی از ``refresh_from_db()``
    مخرب را می‌گیرد.
    """

    def test_contract_number_and_start_date_are_persisted_alongside_payments(self):
        reservation = self.make_reservation(
            contract_number='OLD-CONTRACT',
            start_date=jdatetime.date(1402, 1, 1),
        )

        payload = self.edit_payload(reservation, rows=[{
            'id': '',
            'amount': '25000',
            'payment_type': 'DEPOSIT',
            'payment_date': today_jalali(),
            'due_date': '',
            'payment_method': 'CASH',
            'payment_reference': '',
            'description': 'بیعانه',
        }])
        payload['contract_number'] = 'NEW-CONTRACT'
        payload['start_date'] = '1405/06/01'

        response = self.client.post(
            reverse('reservations:edit', args=[reservation.pk]),
            payload,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['success'])

        reservation.refresh_from_db()
        # تغییرات فرم باید حفظ شده باشند
        self.assertEqual(reservation.contract_number, 'NEW-CONTRACT')
        self.assertEqual(str(reservation.start_date), '1405-06-01')
        # و پرداخت مرحله‌ای هم باید ثبت شده باشد
        self.assertEqual(reservation.deposit_amount, 25000)

    def test_form_edit_without_payment_payload_still_persists(self):
        """مسیر بدون formset (سازگاری عقب‌رو) هم باید فیلدها را ذخیره کند."""
        reservation = self.make_reservation(contract_number='OLD-2')

        response = self.client.post(
            reverse('reservations:edit', args=[reservation.pk]),
            {
                'dress': str(self.dress.pk),
                'start_date': '1405/06/01',
                'rental_days': '3',
                'discount_type': '',
                'discount_value': '0',
                'payment_method': 'CASH',
                'payment_tracking_code': 'PAY-X',
                'guarantee1_type': 'CASH',
                'guarantee1_tracking_code': 'G1',
                'guarantee2_type': '',
                'guarantee2_tracking_code': '',
                'deposit_amount': '0',
                'contract_number': 'NEW-2',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200, response.content)

        reservation.refresh_from_db()
        self.assertEqual(reservation.contract_number, 'NEW-2')
        self.assertEqual(str(reservation.start_date), '1405-06-01')


class ReservationListNoDuplicateDomIdsTests(StagedPaymentTestBase):
    """
    صفحهٔ فهرست رزروها هر سه مودال (ایجاد/ویرایش/تحویل) را رندر می‌کند؛
    شناسه‌های DOM نباید تکراری باشند (رفع L-1).
    """

    def test_reservation_list_has_no_duplicate_element_ids(self):
        import re
        from collections import Counter

        for index in range(2):
            self.make_reservation(
                start_date=jdatetime.date(1402, 1, 1 + index),
                guarantee1_type='CHECK',
                guarantee1_tracking_code=f'G{index}',
                guarantee1_payee='گیرنده',
            )

        response = self.client.get(reverse('reservations:list'))
        self.assertEqual(response.status_code, 200)

        html = response.content.decode('utf-8')
        ids = re.findall(r'\sid="([^"]+)"', html)
        duplicates = {key: count for key, count in Counter(ids).items() if count > 1}

        # رشته‌های قالب جاوااسکریپت (مثل ' + toastId + ') شناسهٔ واقعی نیستند
        duplicates = {k: v for k, v in duplicates.items() if '+' not in k}

        self.assertEqual(
            duplicates, {},
            f'شناسه‌های تکراری در صفحه: {duplicates}',
        )
