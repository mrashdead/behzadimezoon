from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from customers.models import Customer
from products.models import Dress
from reservations.models import Reservation


class FinancialUIFlowsTests(TestCase):
    def setUp(self):
        # admin
        self.admin = User.objects.create_user('admin_user', password='pw', is_superuser=True, role='SUPER_ADMIN')
        # two sellers
        self.seller1 = User.objects.create_user('seller1', password='pw', role='SELLER')
        self.seller2 = User.objects.create_user('seller2', password='pw', role='SELLER')

        import jdatetime

        self.customer = Customer.objects.create(
            bride_first_name='A', bride_last_name='B', bride_phone='09120000000', ceremony_date=jdatetime.date(1402,1,1), how_to_know='t', allow_contact=False
        )
        self.dress = Dress.objects.create(code='D1', daily_rent_price=100000)

        self.reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
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
            payment_tracking_code='P1',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            created_by=self.seller1
        )

    def test_admin_can_add_guarantee(self):
        self.client.login(username='admin_user', password='pw')
        url = reverse('financial:add_guarantee', args=[self.reservation.pk])
        resp = self.client.post(url, {'tracking_code': 'X1', 'guarantee_type': 'CASH', 'estimated_value': 10000})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('guarantee_id', data)

    def test_seller_cannot_modify_other_seller_reservation(self):
        self.client.login(username='seller2', password='pw')
        url = reverse('financial:add_guarantee', args=[self.reservation.pk])
        resp = self.client.post(url, {'tracking_code': 'X1', 'guarantee_type': 'CASH'})
        self.assertEqual(resp.status_code, 403)
        self.assertIn('error', resp.json())
