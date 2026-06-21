from django.test import TestCase, Client
from django.urls import reverse
import jdatetime

from accounts.models import User
from customers.models import Customer
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
