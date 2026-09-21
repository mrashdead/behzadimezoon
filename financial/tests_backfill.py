"""
تست‌های دستورات مدیریتی مالی (بازسازی داده و تطبیق).

این تست‌ها سه ایراد رفع‌شده را قفل می‌کنند:
    * C-1 — ``backfill_transactions`` نباید پول را دو برابر کند.
    * H-2 — ``reconcile_financials`` نباید با ``posting_status`` کرش کند.
    * H-1/H-3 — ``reconcile_finance`` و ``backfill_financials`` باید اجرا شوند.
"""

import io
import jdatetime
from django.core.management import call_command
from django.test import TestCase

from accounts.models import User
from customers.models import Customer
from financial.models import Transaction
from products.models import Dress
from reservations.constants import ReservationStatus
from reservations.models import Reservation
from reservations.services.payment_stage_service import ReservationPaymentService


class ManagementCommandTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.customer = Customer.objects.create(
            bride_first_name='Cmd', bride_last_name='Test', bride_phone='09120001234',
            ceremony_date=jdatetime.date(1402, 1, 1), how_to_know='t', allow_contact=True,
        )
        cls.dress = Dress.objects.create(code='CMD1', daily_rent_price=100000)
        cls.manager = User.objects.create_user(
            username='cmd_manager', password='password123', role='MANAGER',
        )

    def _make_reservation(self, **overrides):
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
            'payment_tracking_code': 'CMD-PAY',
            'guarantee1_type': 'CASH',
            'guarantee1_tracking_code': 'CMD-G1',
            'created_by': self.manager,
        }
        data.update(overrides)
        return Reservation.objects.create(**data)

    # ------------------------------------------------------------------
    # C-1: پول نباید دو برابر شود
    # ------------------------------------------------------------------
    def test_backfill_does_not_double_count_when_real_payments_exist(self):
        """
        رزروی که از قبل «پرداخت مرحله‌ای واقعی» دارد نباید با اجرای دستور
        بازسازی، دوباره بیعانه بسازد (رفع ایراد بحرانی C-1).
        """
        # لباس گران‌تر تا مبلغ نهایی ۳۰۰٬۰۰۰ شود
        expensive_dress = Dress.objects.create(code='CMD-EXP', daily_rent_price=300000)
        reservation = self._make_reservation(
            dress=expensive_dress, rent_price=300000, final_price=300000,
            remaining_amount=300000,
        )

        # یک بیعانه واقعی ۲۷۰٬۰۰۰ تومانی ثبت می‌کنیم (کش هم همگام می‌شود)
        ReservationPaymentService.replace_staged_payments(
            reservation,
            [{
                'id': '',
                'amount': '270000',
                'payment_type': 'DEPOSIT',
                'payment_date': jdatetime.date.today().strftime('%Y/%m/%d'),
                'payment_method': 'CASH',
                'description': 'بیعانه اول',
            }],
            self.manager,
        )
        reservation.refresh_from_db()

        self.assertEqual(ReservationPaymentService.total_paid(reservation), 270000)

        # اجرای دستور منسوخ‌شده (shim) + دستور canonical
        call_command('backfill_transactions', '--dry-run', stdout=io.StringIO())
        call_command('backfill_staged_payments', '--dry-run', stdout=io.StringIO())

        reservation.refresh_from_db()
        # مجموع پرداخت نباید ۵۴۰٬۰۰۰ شود
        self.assertEqual(ReservationPaymentService.total_paid(reservation), 270000)
        self.assertEqual(
            Transaction.objects.filter(
                reservation=reservation,
                transaction_type=Transaction.TransactionType.DEPOSIT,
                transaction_status=Transaction.TransactionStatus.POSTED,
                is_voided=False,
            ).count(),
            1,
        )

    def test_backfill_staged_payments_is_idempotent_on_real_run(self):
        """اجرای واقعی (بدون dry-run) نباید رکورد تکراری بسازد."""
        reservation = self._make_reservation(deposit_amount=50000)

        call_command('backfill_staged_payments', stdout=io.StringIO())
        reservation.refresh_from_db()
        first_total = ReservationPaymentService.total_paid(reservation)

        call_command('backfill_staged_payments', stdout=io.StringIO())
        reservation.refresh_from_db()
        second_total = ReservationPaymentService.total_paid(reservation)

        self.assertEqual(first_total, 50000)
        self.assertEqual(second_total, 50000)

    # ------------------------------------------------------------------
    # H-1 / H-2 / H-3: دستورات نباید کرش کنند
    # ------------------------------------------------------------------
    def test_reconcile_financials_runs_without_field_error(self):
        self._make_reservation(deposit_amount=50000)
        # نباید FieldError بدهد
        call_command('reconcile_financials', stdout=io.StringIO())

    def test_reconcile_finance_runs_and_prints_aligned_columns(self):
        self._make_reservation(deposit_amount=50000, payment_status=Reservation.PAYMENT_PARTIAL)

        out = io.StringIO()
        call_command('reconcile_finance', stdout=out)
        text = out.getvalue()

        self.assertIn('reservation_id', text)
        self.assertIn('customer_name', text)
        # ستون‌ها نباید همه None باشند
        self.assertNotIn('\tNone\t', text)

    def test_backfill_financials_shim_runs(self):
        self._make_reservation(deposit_amount=25000)
        call_command('backfill_financials', '--dry-run', stdout=io.StringIO())

    def test_reconcile_finance_detects_overdue_partial_payment(self):
        """پرداخت معوق باید بر پایه تاریخ تحویل (نه فیلد ناموجود due_date) تشخیص داده شود."""
        self._make_reservation(
            deposit_amount=30000,
            payment_status=Reservation.PAYMENT_PARTIAL,
            delivery_date=jdatetime.date(1402, 1, 1),  # گذشته
        )

        from financial.services.reconciliation_service import ReconciliationService
        problems = ReconciliationService.get_open_problem_reservations({})
        issues = [row['issue'] for row in problems]

        self.assertIn('پرداخت معوق', issues)
