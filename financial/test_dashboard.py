from django.test import TestCase, Client
from django.urls import reverse
import jdatetime

from accounts.models import User
from customers.models import Customer
from financial.services import DashboardService
from financial.services.transaction_service import TransactionService
from products.models import Dress
from reservations.models import Reservation
from reservations.constants import ReservationStatus


def create_user(username, role, password='password123'):
    return User.objects.create_user(username=username, password=password, role=role)


class FinancialDashboardTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.customer = Customer.objects.create(
            bride_first_name='A',
            bride_last_name='B',
            bride_phone='09120000000',
            ceremony_date=jdatetime.date(1402, 1, 1),
            how_to_know='test',
            allow_contact=True
        )
        cls.dress = Dress.objects.create(code='D001', daily_rent_price=100000)
        cls.user = create_user('finance_user', 'MANAGER')

    def setUp(self):
        self.client = Client()
        self.client.login(username='finance_user', password='password123')

    def test_financial_list_excludes_cancelled_remaining_amount(self):
        Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.DELIVERED,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=50000,
            discount_amount=0,
            final_price=100000,
            remaining_amount=50000,
            payment_method='CASH',
            payment_tracking_code='PAY123',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            created_by=self.user
        )

        Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 4),
            rental_days=3,
            status=ReservationStatus.CANCELLED,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=20000,
            discount_amount=0,
            final_price=100000,
            remaining_amount=80000,
            payment_method='CASH',
            payment_tracking_code='PAY456',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G2',
            created_by=self.user
        )

        response = self.client.get(reverse('financial:list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['totals']['total_revenue'], 100000)
        self.assertEqual(response.context['totals']['total_deposit'], 50000)
        self.assertEqual(response.context['totals']['total_remaining'], 50000)

        self.assertEqual(response.context['cancelled_totals']['total_cancelled_reservations'], 1)
        self.assertEqual(response.context['cancelled_totals']['cancelled_received_amount'], 20000)

    def test_dashboard_service_uses_transactions_for_cash_inflow(self):
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.DELIVERED,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=50000,
            discount_amount=0,
            final_price=100000,
            remaining_payment_amount=100000,
            payment_method='CASH',
            payment_tracking_code='PAY123',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            created_by=self.user
        )

        TransactionService.create_deposit(
            reservation=reservation,
            amount=50000,
            created_by=self.user,
            payment_method='CASH',
            note='Initial deposit'
        )
        TransactionService.create_final_payment(
            reservation=reservation,
            amount=100000,
            created_by=self.user,
            payment_method='CASH',
            note='Final payment'
        )

        ctx = DashboardService.get_financial_context()
        self.assertEqual(ctx['totals']['total_cash_inflow'], 150000)
        self.assertEqual(ctx['totals']['total_revenue'], 150000)
        self.assertTrue(ctx['uses_transaction_ledger'])
        self.assertEqual(ctx['open_reconciliation_issues'], 0)

    def test_dashboard_shows_transaction_ledger_mode(self):
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.DELIVERED,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=50000,
            discount_amount=0,
            final_price=100000,
            remaining_payment_amount=100000,
            payment_method='CASH',
            payment_tracking_code='PAY123',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            created_by=self.user
        )

        TransactionService.create_deposit(
            reservation=reservation,
            amount=50000,
            created_by=self.user,
            payment_method='CASH',
            note='Initial deposit'
        )
        TransactionService.create_final_payment(
            reservation=reservation,
            amount=100000,
            created_by=self.user,
            payment_method='CASH',
            note='Final payment'
        )

        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'دفتر تراکنش‌محور فعال است')

    def test_dashboard_uses_legacy_fields_when_no_transactions(self):
        Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.DELIVERED,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=50000,
            discount_amount=0,
            final_price=100000,
            remaining_payment_amount=100000,
            payment_method='CASH',
            payment_tracking_code='PAY123',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            created_by=self.user
        )

        ctx = DashboardService.get_financial_context()
        self.assertFalse(ctx['uses_transaction_ledger'])
        self.assertEqual(ctx['totals']['total_cash_inflow'], 150000)
        self.assertEqual(ctx['totals']['total_revenue'], 100000)

    def test_reconciliation_marks_mismatched_reservations(self):
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.DELIVERED,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=50000,
            discount_amount=0,
            final_price=100000,
            remaining_payment_amount=100000,
            refunded_amount=10000,
            payment_method='CASH',
            payment_tracking_code='PAY123',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            created_by=self.user
        )

        TransactionService.create_deposit(
            reservation=reservation,
            amount=50000,
            created_by=self.user,
            payment_method='CASH',
            note='Initial deposit'
        )
        TransactionService.create_final_payment(
            reservation=reservation,
            amount=80000,
            created_by=self.user,
            payment_method='CASH',
            note='Partial final payment'
        )

        ctx = DashboardService.get_financial_context()
        self.assertTrue(ctx['uses_transaction_ledger'])
        self.assertEqual(ctx['open_reconciliation_issues'], 1)
