from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from financial.models import Transaction


class FinancialUITests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin_user', password='password123', is_superuser=True)

    def test_transactions_list_requires_login(self):
        url = reverse('financial:transactions')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)

    def test_reconcile_admin_requires_superuser(self):
        self.client.login(username='admin_user', password='password123')
        url = reverse('financial:reconcile_admin')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_reconcile_admin_ui_rendering(self):
        self.client.login(username='admin_user', password='password123')
        url = reverse('financial:reconcile_admin_ui')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'تسویه مالی')

    def test_reconcile_resolve_creates_adjustment(self):
        from reservations.models import Reservation
        from customers.models import Customer
        from products.models import Dress
        import jdatetime

        customer = Customer.objects.create(
            bride_first_name='A',
            bride_last_name='B',
            bride_phone='09120000000',
            ceremony_date=jdatetime.date(1402,1,1),
            how_to_know='test',
            allow_contact=False
        )
        dress = Dress.objects.create(code='D1', daily_rent_price=100000)

        # create a reservation with no transactions but with a deposit
        reservation = Reservation.objects.create(
            customer=customer,
            dress=dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=1,
            status='CONFIRMED',
            rent_price=100000,
            deposit_amount=50000,
            discount_amount=0,
            final_price=100000,
            remaining_amount=50000,
            remaining_payment_amount=0,
            refunded_amount=0,
            payment_method='CASH',
            payment_tracking_code='PAY123',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            created_by=self.admin
        )
        self.client.login(username='admin_user', password='password123')
        url = reverse('financial:reconcile_resolve')
        resp = self.client.post(url, {'reservation_id': reservation.pk})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('transaction_id', data)
        tx = Transaction.objects.get(pk=data['transaction_id'])
        self.assertEqual(tx.type, Transaction.Type.ADJUSTMENT)
