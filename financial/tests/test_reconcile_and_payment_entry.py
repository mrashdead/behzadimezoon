"""تست‌های رگرسیون برای صفحهٔ تسویه مالی و صفحهٔ ثبت پرداخت.

این ماژول سه دسته چیز را قفل می‌کند:

۱. **قرارداد پاسخ** ``record_payment_view`` — پیش‌تر فقط ``{"error": "..."}``
   برمی‌گرداند و قالب یک فرم HTML ساده بود که همان JSON خام را به کاربر
   نشان می‌داد. اکنون ``success`` / ``errors`` برگردانده می‌شود (با حفظ
   کلید قدیمی ``error`` برای سازگاری).

۲. **اتصال داده‌های صفحهٔ تسویه مالی** — قالب پیش‌تر به کلیدهایی مثل
   ``expected_cash_from_tx`` می‌چسبید که ``get_open_problem_reservations``
   هرگز برنمی‌گرداند؛ در نتیجه همهٔ ستون‌های مالی همیشه صفر بودند.

۳. **ساختار و مارک‌آپ** صفحهٔ تسویه مالی و صفحهٔ ثبت پرداخت.
"""

from unittest import mock

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from financial.models import Transaction
from financial.services.dashboard_service import DashboardService
from financial.services.reconciliation_service import ReconciliationService


class _FakeDress:
    code = 'DR-101'

    def __str__(self):
        return self.code


class _FakeCustomer:
    def __str__(self):
        return 'نسترن سلطانی'


class _FakeReservation:
    """حداقل شیء لازم برای پیمایش در ``get_open_problem_reservations``."""

    def __init__(self, pk):
        self.pk = pk
        self.id = pk
        self.customer = _FakeCustomer()
        self.dress = _FakeDress()


def _discrepancy(**overrides):
    data = {
        'reservation_id': 1,
        'customer_name': 'نسترن سلطانی',
        'dress_code': 'DR-101',
        'expected_cash': 900_000,
        'expected_cash_from_tx': 900_000,
        'reservation_cash_recorded': 850_000,
        'cash_difference': 50_000,
        'suggested_action': 'refund',
        'action_label': 'ثبت بازپرداخت',
        'transaction_type': Transaction.TransactionType.REFUND,
        'has_discrepancy': True,
        'open_receivable': 0,
    }
    data.update(overrides)
    return data


class OpenProblemReservationsShapeTests(TestCase):
    """کلیدهای مالی باید در خروجی سرویس موجود باشند (باگ «ستون‌های صفر»)."""

    def _call(self, discrepancies, overdue=False):
        with mock.patch.object(
            DashboardService, '_apply_reservation_filters',
            side_effect=lambda qs, filters: qs,
        ), mock.patch.object(
            ReconciliationService, 'is_payment_overdue', return_value=overdue,
        ), mock.patch.object(
            ReconciliationService, '_payment_due_date', return_value='1404/01/01',
        ), mock.patch.object(
            ReconciliationService, 'reservation_discrepancies',
            return_value=discrepancies,
        ), mock.patch(
            'financial.services.reconciliation_service.Reservation.objects.filter',
            return_value=[_FakeReservation(1)],
        ):
            return ReconciliationService.get_open_problem_reservations({})

    def test_discrepancy_row_exposes_financial_fields(self):
        rows = self._call(_discrepancy())

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['kind'], 'discrepancy')
        self.assertEqual(row['issue'], 'اختلاف مالی')
        self.assertEqual(row['expected_cash'], 900_000)
        self.assertEqual(row['recorded_cash'], 850_000)
        self.assertEqual(row['cash_difference'], 50_000)
        self.assertEqual(row['suggested_action'], 'refund')
        self.assertEqual(row['action_label'], 'ثبت بازپرداخت')

        # کلیدهای قدیمی باید دست‌نخورده باقی بمانند (دستور reconcile_finance
        # و DashboardService به آن‌ها وابسته‌اند).
        for legacy_key in ('reservation_id', 'customer_name', 'dress_code', 'issue', 'details'):
            self.assertIn(legacy_key, row)

    def test_no_discrepancy_produces_no_rows(self):
        rows = self._call(_discrepancy(has_discrepancy=False, cash_difference=0))
        self.assertEqual(rows, [])

    def test_overdue_row_has_explicit_none_financials(self):
        rows = self._call(_discrepancy(has_discrepancy=False), overdue=True)

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['kind'], 'overdue')
        self.assertEqual(row['issue'], 'پرداخت معوق')
        # ردیف معوق «اختلاف عددی» ندارد؛ باید صریحاً None باشد تا قالب
        # بتواند آن را از ردیف اختلاف واقعی تفکیک کند.
        self.assertIsNone(row['cash_difference'])
        self.assertIsNone(row['expected_cash'])
        self.assertIsNone(row['action_label'])


class RecordPaymentContractTests(TestCase):
    """قرارداد JSON نقطهٔ پایانی ثبت پرداخت."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='seller1', password='pass12345', role=User.Role.SELLER,
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse('financial:record_payment')

    def test_missing_reservation_id_returns_field_error(self):
        response = self.client.post(self.url, {'amount': '1000'})

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload['success'])
        self.assertIn('reservation_id', payload['errors'])
        # سازگاری با مصرف‌کننده‌های قدیمی که ``error`` را می‌خوانند
        self.assertIn('error', payload)

    def test_missing_amount_returns_field_error(self):
        response = self.client.post(self.url, {'reservation_id': '1'})

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload['success'])
        self.assertIn('amount', payload['errors'])

    def test_non_numeric_amount_is_rejected(self):
        response = self.client.post(
            self.url, {'reservation_id': '1', 'amount': 'abc'},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('amount', response.json()['errors'])

    def test_zero_amount_is_rejected(self):
        response = self.client.post(
            self.url, {'reservation_id': '1', 'amount': '0'},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('amount', response.json()['errors'])

    def test_persian_digits_with_separators_are_accepted(self):
        """«۴۵۰,۰۰۰» نباید با خطای «مبلغ باید عددی باشد» رد شود.

        این حالت دقیقاً همان چیزی است که ماسک پول در رابط کاربری تولید
        می‌کند؛ پیش‌تر ``int(amount)`` روی آن استثنا می‌داد.
        """
        response = self.client.post(
            self.url, {'reservation_id': '1', 'amount': '۴۵۰,۰۰۰'},
        )

        self.assertEqual(response.status_code, 404)
        payload = response.json()
        # به مرحلهٔ «رزرو یافت نشد» رسیده یعنی مبلغ درست تجزیه شده است.
        self.assertIn('reservation_id', payload['errors'])
        self.assertNotIn('amount', payload['errors'])

    def test_unknown_reservation_returns_404(self):
        response = self.client.post(
            self.url, {'reservation_id': '999999', 'amount': '1000'},
        )

        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assertFalse(payload['success'])
        self.assertIn('reservation_id', payload['errors'])

    def test_get_is_not_allowed(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)


class ReconcileAdminPageTests(TestCase):
    """رندر صفحهٔ تسویه مالی با ساختار و کلیدهای درست."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username='admin1', password='pass12345',
            role=User.Role.SUPER_ADMIN,
        )
        cls.seller = User.objects.create_user(
            username='seller2', password='pass12345',
            role=User.Role.SELLER,
        )

    def setUp(self):
        self.url = reverse('financial:reconcile_admin')

    def test_superuser_can_open_page(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'تسویه مالی')
        # بخش تراکنش‌های هماهنگ‌نشده که پیش‌تر در قالب نمایش داده نمی‌شد
        self.assertContains(response, 'هماهنگ‌نشده')

    def test_empty_state_is_shown_when_no_discrepancies(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url)

        self.assertContains(response, 'هیچ اختلاف مالی‌ای یافت نشد')
        self.assertContains(response, 'empty-state')

    def test_table_columns_bind_to_service_keys(self):
        """ستون‌های مالی باید به کلیدهای واقعی سرویس وصل باشند.

        قالب قدیمی ``expected_cash_from_tx`` را می‌خواند که هرگز وجود
        نداشت؛ در نتیجه همهٔ سلول‌ها صفر/خالی بودند.
        """
        row = {
            'reservation_id': 7,
            'customer_name': 'نسترن سلطانی',
            'dress_code': 'DR-101',
            'issue': 'اختلاف مالی',
            'kind': 'discrepancy',
            'details': 'تفاوت: 50000 | پیشنهاد: ثبت بازپرداخت',
            'expected_cash': 900_000,
            'recorded_cash': 850_000,
            'cash_difference': 50_000,
            'suggested_action': 'refund',
            'action_label': 'ثبت بازپرداخت',
            'open_receivable': 0,
        }

        self.client.force_login(self.admin)
        with mock.patch.object(
            ReconciliationService, 'get_open_problem_reservations', return_value=[row],
        ):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'انتظار (اسناد)')
        self.assertContains(response, 'ثبت‌شده (رزرو)')
        self.assertContains(response, 'اختلاف')
        self.assertContains(response, 'نسترن سلطانی')
        self.assertContains(response, 'DR-101')
        self.assertContains(response, 'ثبت بازپرداخت')
        # مبالغ واقعی باید دیده شوند، نه صفرِ ناشی از کلید ناموجود
        self.assertContains(response, '900,000')
        self.assertContains(response, '850,000')
        self.assertContains(response, '50,000')

    def test_non_superuser_is_denied(self):
        self.client.force_login(self.seller)
        response = self.client.get(self.url)

        # UserPassesTestMixin کاربر بدون دسترسی را رد می‌کند (403 یا ریدایرکت)
        self.assertIn(response.status_code, (302, 403))

    def test_reservation_id_filter_is_applied(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url, {'reservation_id': '4242'})

        self.assertEqual(response.status_code, 200)
        # فیلتر فعال باید در فرم باقی بماند (پیش‌تر نادیده گرفته می‌شد)
        self.assertContains(response, '4242')

    def test_page_has_balanced_layout_markup(self):
        """ساختار HTML نباید تگ بسته‌نشده داشته باشد.

        نسخهٔ قبلی این قالب ``row``/``col``/``card`` را بدون بستن رها کرده
        بود و کارت اصلی داخل کارت خلاصه تودرتو می‌شد.
        """
        self.client.force_login(self.admin)
        html = self.client.get(self.url).content.decode('utf-8')

        self.assertEqual(html.count('<div'), html.count('</div>'))
        self.assertEqual(html.count('<table'), html.count('</table>'))
        self.assertEqual(html.count('<tr'), html.count('</tr>'))


class PaymentEntryPageTests(TestCase):
    """رندر صفحهٔ ثبت پرداخت با انتخابگر رزرو و فرم AJAX."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username='seller3', password='pass12345', role=User.Role.SELLER,
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse('financial:payment_entry')

    def test_page_renders_with_picker_and_ajax_form(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-ajax-form')
        self.assertContains(response, 'data-reservation-picker')
        self.assertContains(response, 'reservation-picker.js')
        self.assertContains(response, 'js-form-error-summary')

    def test_form_posts_to_record_payment_endpoint(self):
        response = self.client.get(self.url)
        self.assertContains(response, reverse('financial:record_payment'))

    def test_hidden_reservation_id_field_is_present(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'name="reservation_id"')
        self.assertContains(response, 'data-reservation-picker-value')

    def test_layout_markup_is_balanced(self):
        html = self.client.get(self.url).content.decode('utf-8')
        self.assertEqual(html.count('<div'), html.count('</div>'))
        self.assertEqual(html.count('<form'), html.count('</form>'))
