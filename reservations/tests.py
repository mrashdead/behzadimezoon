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


class ReservationStatusTransitionTests(TestCase):

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
        cls.seller = create_user('seller_user', 'SELLER')
        cls.manager = create_user('manager_user', 'MANAGER')
        cls.admin = create_user('admin_user', 'SUPER_ADMIN')

    def setUp(self):
        self.client = Client()

    def test_seller_cannot_mark_delivered_or_returned(self):
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.CONFIRMED,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=50000,
            discount_amount=0,
            final_price=50000,
            remaining_amount=0,
            payment_method='CASH',
            payment_tracking_code='PAY123',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            created_by=self.seller
        )

        self.client.login(username='seller_user', password='password123')

        delivered_url = reverse('reservations:delivered', args=[reservation.pk])
        returned_url = reverse('reservations:returned', args=[reservation.pk])

        response = self.client.post(delivered_url)
        self.assertEqual(response.status_code, 403)

        response = self.client.post(returned_url)
        self.assertEqual(response.status_code, 403)

    def test_manager_can_mark_delivered_and_returned(self):
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.CONFIRMED,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=50000,
            discount_amount=0,
            final_price=50000,
            remaining_amount=0,
            payment_method='CASH',
            payment_tracking_code='PAY123',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            created_by=self.manager
        )

        self.client.login(username='manager_user', password='password123')

        delivered_url = reverse('reservations:delivered', args=[reservation.pk])
        response = self.client.post(delivered_url)
        self.assertEqual(response.status_code, 302)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, ReservationStatus.DELIVERED)

        returned_url = reverse('reservations:returned', args=[reservation.pk])
        response = self.client.post(returned_url)
        self.assertEqual(response.status_code, 302)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, ReservationStatus.RETURNED)

    def test_super_admin_can_mark_delivered_and_returned(self):
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.CONFIRMED,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=50000,
            discount_amount=0,
            final_price=50000,
            remaining_amount=0,
            payment_method='CASH',
            payment_tracking_code='PAY123',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            created_by=self.admin
        )

        self.client.login(username='admin_user', password='password123')

        delivered_url = reverse('reservations:delivered', args=[reservation.pk])
        response = self.client.post(delivered_url)
        self.assertEqual(response.status_code, 302)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, ReservationStatus.DELIVERED)

        returned_url = reverse('reservations:returned', args=[reservation.pk])
        response = self.client.post(returned_url)
        self.assertEqual(response.status_code, 302)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, ReservationStatus.RETURNED)

    def test_cannot_cancel_if_already_cancelled_or_returned(self):
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.RETURNED,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=50000,
            discount_amount=0,
            final_price=50000,
            remaining_amount=0,
            payment_method='CASH',
            payment_tracking_code='PAY123',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            created_by=self.admin
        )

        self.client.login(username='admin_user', password='password123')
        delete_url = reverse('reservations:delete', args=[reservation.pk])
        response = self.client.post(delete_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {
            "success": False,
            "message": "انتقال وضعیت از بازگشت داده شده به لغو شده مجاز نیست."
        })
