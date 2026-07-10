import jdatetime
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from customers.models import Customer
from products.models import Dress
from reservations.constants import ReservationStatus
from reservations.models import Reservation


User = get_user_model()


def create_user(username, role, password='password123', is_superuser=False, is_staff=False):
    if is_superuser:
        return User.objects.create_superuser(username=username, password=password)

    return User.objects.create_user(username=username, password=password, role=role)


class ProductPermissionAndStatusTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.seller = create_user('seller_user', role='SELLER')
        cls.manager = create_user('manager_user', role='MANAGER')
        cls.admin = create_user('admin_user', role='SUPER_ADMIN', is_superuser=True)

        cls.customer = Customer.objects.create(
            bride_first_name='ساناز',
            bride_last_name='احمدی',
            bride_phone='09120000000',
            ceremony_date=jdatetime.date(1402, 5, 1),
            how_to_know='اینترنت',
            allow_contact=True,
        )

    def setUp(self):
        self.client = Client()

    def test_dress_availability_label_reflects_current_rental(self):
        dress = Dress.objects.create(code='D100', daily_rent_price=250000)

        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=dress,
            start_date=jdatetime.date.today(),
            rental_days=2,
            deposit_amount=0,
            discount_amount=0,
            final_price=0,
            remaining_amount=0,
            payment_method='CASH',
            payment_tracking_code='TRX123',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G123',
            status=ReservationStatus.CONFIRMED,
            created_by=self.admin,
        )

        self.assertTrue(dress.is_currently_rented)
        self.assertEqual(dress.availability_label, 'در اجاره')

    def test_seller_can_create_but_cannot_update_or_delete_product(self):
        self.client.login(username='seller_user', password='password123')

        add_url = reverse('products:add')
        edit_url = reverse('products:edit', kwargs={'pk': 1})
        delete_url = reverse('products:delete', kwargs={'pk': 1})

        response_add = self.client.get(add_url)
        self.assertEqual(response_add.status_code, 200)

        response_post = self.client.post(add_url, {
            'code': 'D103',
            'daily_rent_price': 350000,
        })
        self.assertEqual(response_post.status_code, 302)
        self.assertTrue(Dress.objects.filter(code='D103').exists())

        response_edit = self.client.get(edit_url)
        response_delete = self.client.post(delete_url)

        self.assertEqual(response_edit.status_code, 403)
        self.assertEqual(response_delete.status_code, 403)

    def test_manager_can_create_product(self):
        self.client.login(username='manager_user', password='password123')

        add_url = reverse('products:add')
        response = self.client.post(add_url, {
            'code': 'D101',
            'daily_rent_price': 300000,
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Dress.objects.filter(code='D101').exists())

    def test_manager_can_update_and_delete_product(self):
        dress = Dress.objects.create(code='D102', daily_rent_price=310000)
        self.client.login(username='manager_user', password='password123')

        edit_url = reverse('products:edit', kwargs={'pk': dress.pk})
        response_edit = self.client.post(edit_url, {
            'code': 'D102-UPDATED',
            'daily_rent_price': 320000,
        })
        self.assertEqual(response_edit.status_code, 302)

        dress.refresh_from_db()
        self.assertEqual(dress.code, 'D102-UPDATED')

        delete_url = reverse('products:delete', kwargs={'pk': dress.pk})
        response_delete = self.client.post(delete_url)
        self.assertEqual(response_delete.status_code, 302)
        self.assertFalse(Dress.objects.filter(pk=dress.pk).exists())

    def test_list_context_hides_manage_buttons_for_sellers(self):
        self.client.login(username='seller_user', password='password123')
        response = self.client.get(reverse('products:list'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['can_create_product'])
        self.assertFalse(response.context['can_manage_product'])

    def test_row_number_continues_across_paginated_product_pages(self):
        for i in range(25):
            Dress.objects.create(code=f'D{i:03d}', daily_rent_price=100000)

        response = self.client.get(reverse('products:list'), {'page': 2})

        self.assertEqual(response.status_code, 200)
        self.assertIn('>21</span>', response.content.decode())

    def test_list_can_sort_products_by_code(self):
        Dress.objects.create(code='Z100', daily_rent_price=100000)
        Dress.objects.create(code='A100', daily_rent_price=200000)
        Dress.objects.create(code='M100', daily_rent_price=300000)

        response = self.client.get(reverse('products:list'), {'sort': 'code', 'order': 'asc'})

        self.assertEqual(response.status_code, 200)
        codes = [dress.code for dress in response.context['dresses']]
        self.assertEqual(codes, ['A100', 'M100', 'Z100'])
