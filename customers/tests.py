from datetime import date
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

import jdatetime
from reservations.models import Reservation
from products.models import Dress
from .forms import CustomerForm
from .models import Customer

User = get_user_model()


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


class CustomerCityFieldTests(TestCase):
    def test_city_is_supported_in_customer_form(self):
        form = CustomerForm(
            data={
                'bride_first_name': 'مریم',
                'bride_last_name': 'احمدی',
                'bride_phone': '09121234567',
                'ceremony_date': '۱۴۰۵/۰۳/۲۴',
                'how_to_know': 'اینستاگرام',
                'city': 'تهران',
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['city'], 'تهران')


class CustomerSelectionFieldTests(TestCase):
    def test_phone_numbers_must_have_exactly_11_digits(self):
        form = CustomerForm(
            data={
                'bride_first_name': 'مریم',
                'bride_last_name': 'احمدی',
                'bride_phone': '0912',
                'ceremony_date': '۱۴۰۵/۰۳/۲۴',
                'how_to_know': 'اینستاگرام',
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn('bride_phone', form.errors)

    def test_preferred_consultant_can_be_selected_from_choices(self):
        form = CustomerForm(
            data={
                'bride_first_name': 'مریم',
                'bride_last_name': 'احمدی',
                'bride_phone': '09121234567',
                'ceremony_date': '۱۴۰۵/۰۳/۲۴',
                'how_to_know': 'اینستاگرام',
                'preferred_consultant': 'مشاوره کامل',
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['preferred_consultant'], 'مشاوره کامل')

    def test_preferred_consultant_name_is_optional(self):
        form = CustomerForm(
            data={
                'bride_first_name': 'مریم',
                'bride_last_name': 'احمدی',
                'bride_phone': '09121234567',
                'ceremony_date': '۱۴۰۵/۰۳/۲۴',
                'how_to_know': 'اینستاگرام',
                'preferred_consultant': 'مشاوره کامل',
                'preferred_consultant_name': '',
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['preferred_consultant_name'], '')

    def test_how_to_know_can_be_set_to_no_contact(self):
        form = CustomerForm(
            data={
                'bride_first_name': 'مریم',
                'bride_last_name': 'احمدی',
                'bride_phone': '09121234567',
                'ceremony_date': '۱۴۰۵/۰۳/۲۴',
                'how_to_know': 'ندارد',
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['how_to_know'], 'ندارد')

    def test_how_to_know_detail_property_extracts_the_detail_value(self):
        customer = Customer.objects.create(
            bride_first_name='مریم',
            bride_last_name='احمدی',
            bride_phone='09121234567',
            ceremony_date=jdatetime.date(1405, 3, 24),
            how_to_know='سالن زیبایی: سالن مدرن',
        )

        self.assertEqual(customer.how_to_know_detail, 'سالن مدرن')

    def test_multi_select_services_are_joined_and_how_to_know_detail_is_preserved(self):
        form = CustomerForm(
            data={
                'bride_first_name': 'مریم',
                'bride_last_name': 'احمدی',
                'bride_phone': '09121234567',
                'ceremony_date': '۱۴۰۵/۰۳/۲۴',
                'how_to_know': 'سالن زیبایی',
                'how_to_know_detail': 'سالن مدرن',
                'requested_services': ['اجاره لباس', 'دوخت اختصاصی'],
                'estimated_budget': 'متوسط',
                'additional_services': ['آتلیه', 'گروه موسیقی'],
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['how_to_know'], 'سالن زیبایی: سالن مدرن')
        self.assertEqual(form.cleaned_data['requested_services'], 'اجاره لباس, دوخت اختصاصی')
        self.assertEqual(form.cleaned_data['additional_services'], 'آتلیه, گروه موسیقی')
        self.assertEqual(form.cleaned_data['estimated_budget'], 'متوسط')


class CustomerListFilterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='admin', password='password123')
        self.client.force_login(self.user)

    def test_show_with_reservations_excludes_ready_and_cancelled_reservations(self):
        customer_with_blocking_reservation = Customer.objects.create(
            bride_first_name='نرگس',
            bride_last_name='جعفری',
            bride_phone='09123333333',
            ceremony_date=jdatetime.date(1404, 3, 1),
            how_to_know='اینستاگرام',
        )
        customer_with_ready_reservation = Customer.objects.create(
            bride_first_name='الهام',
            bride_last_name='قاضی',
            bride_phone='09124444444',
            ceremony_date=jdatetime.date(1404, 3, 2),
            how_to_know='دوستان',
        )
        customer_with_cancelled_reservation = Customer.objects.create(
            bride_first_name='فاطمه',
            bride_last_name='کریمی',
            bride_phone='09125555555',
            ceremony_date=jdatetime.date(1404, 3, 3),
            how_to_know='تبلیغات',
        )

        dress = Dress.objects.create(code='DTEST3', daily_rent_price=150000)

        Reservation.objects.create(
            customer=customer_with_blocking_reservation,
            dress=dress,
            start_date=jdatetime.date(1404, 3, 1),
            rental_days=1,
            end_date=jdatetime.date(1404, 3, 2),
            rent_price=150000,
            deposit_amount=0,
            final_price=150000,
            remaining_amount=150000,
            payment_method='CASH',
            payment_tracking_code='ABC125',
            remaining_payment_amount=150000,
            guarantee1_type='CASH',
            guarantee1_tracking_code='G3',
            status='CONFIRMED',
            created_by=self.user,
        )
        Reservation.objects.create(
            customer=customer_with_ready_reservation,
            dress=dress,
            start_date=jdatetime.date(1404, 3, 4),
            rental_days=1,
            end_date=jdatetime.date(1404, 3, 5),
            rent_price=150000,
            deposit_amount=0,
            final_price=150000,
            remaining_amount=150000,
            payment_method='CASH',
            payment_tracking_code='ABC126',
            remaining_payment_amount=150000,
            guarantee1_type='CASH',
            guarantee1_tracking_code='G4',
            status='READY',
            created_by=self.user,
        )
        Reservation.objects.create(
            customer=customer_with_cancelled_reservation,
            dress=dress,
            start_date=jdatetime.date(1404, 3, 6),
            rental_days=1,
            end_date=jdatetime.date(1404, 3, 7),
            rent_price=150000,
            deposit_amount=0,
            final_price=150000,
            remaining_amount=150000,
            payment_method='CASH',
            payment_tracking_code='ABC127',
            remaining_payment_amount=150000,
            guarantee1_type='CASH',
            guarantee1_tracking_code='G5',
            status='CANCELLED',
            created_by=self.user,
        )

        response = self.client.get(reverse('customers:list'), {'show_with_reservations': '1'})

        self.assertEqual(response.status_code, 200)
        self.assertIn(customer_with_blocking_reservation, response.context['customers'])
        self.assertNotIn(customer_with_ready_reservation, response.context['customers'])
        self.assertNotIn(customer_with_cancelled_reservation, response.context['customers'])


class CustomerSortTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='admin', password='password123')
        self.client.force_login(self.user)

    def test_list_can_sort_customers_by_name(self):
        Customer.objects.create(
            bride_first_name='Zahra',
            bride_last_name='Rezaei',
            bride_phone='09120000000',
            ceremony_date=jdatetime.date(1404, 1, 1),
            how_to_know='اینستاگرام',
        )
        Customer.objects.create(
            bride_first_name='Arzo',
            bride_last_name='Karimi',
            bride_phone='09121111111',
            ceremony_date=jdatetime.date(1404, 2, 1),
            how_to_know='دوستان',
        )
        Customer.objects.create(
            bride_first_name='Mina',
            bride_last_name='Jafari',
            bride_phone='09122222222',
            ceremony_date=jdatetime.date(1404, 3, 1),
            how_to_know='تبلیغات',
        )

        response = self.client.get(reverse('customers:list'), {'sort': 'bride_first_name', 'order': 'asc'})

        self.assertEqual(response.status_code, 200)
        names = [f"{customer.bride_first_name} {customer.bride_last_name}" for customer in response.context['customers']]
        self.assertEqual(names, ['Arzo Karimi', 'Mina Jafari', 'Zahra Rezaei'])


class CustomerDeleteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='admin', password='password123')
        self.client.force_login(self.user)

    def test_customer_with_reservation_cannot_be_deleted(self):
        customer = Customer.objects.create(
            bride_first_name='آرزو',
            bride_last_name='حسینی',
            bride_phone='09120000000',
            ceremony_date=jdatetime.date(1404, 1, 1),
            how_to_know='اینستاگرام',
        )
        dress = Dress.objects.create(code='DTEST1', daily_rent_price=100000)
        Reservation.objects.create(
            customer=customer,
            dress=dress,
            start_date=jdatetime.date(1404, 1, 1),
            rental_days=1,
            end_date=jdatetime.date(1404, 1, 2),
            rent_price=100000,
            deposit_amount=0,
            final_price=100000,
            remaining_amount=100000,
            payment_method='CASH',
            payment_tracking_code='ABC123',
            remaining_payment_amount=100000,
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            status='CONFIRMED',
            created_by=self.user,
        )

        response = self.client.post(reverse('customers:delete', kwargs={'pk': customer.pk}))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Customer.objects.filter(pk=customer.pk).exists())
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(messages)
        self.assertTrue(any('امکان حذف مشتری' in str(message) for message in messages))

    def test_bulk_delete_skips_customers_with_active_reservations(self):
        safe_customer = Customer.objects.create(
            bride_first_name='سارا',
            bride_last_name='کریمی',
            bride_phone='09121111111',
            ceremony_date=jdatetime.date(1404, 2, 1),
            how_to_know='دوستان',
        )
        blocked_customer = Customer.objects.create(
            bride_first_name='مینا',
            bride_last_name='رضایی',
            bride_phone='09122222222',
            ceremony_date=jdatetime.date(1404, 2, 2),
            how_to_know='اینستاگرام',
        )
        dress = Dress.objects.create(code='DTEST2', daily_rent_price=120000)
        Reservation.objects.create(
            customer=blocked_customer,
            dress=dress,
            start_date=jdatetime.date(1404, 2, 1),
            rental_days=1,
            end_date=jdatetime.date(1404, 2, 2),
            rent_price=120000,
            deposit_amount=0,
            final_price=120000,
            remaining_amount=120000,
            payment_method='CASH',
            payment_tracking_code='ABC124',
            remaining_payment_amount=120000,
            guarantee1_type='CASH',
            guarantee1_tracking_code='G2',
            status='CONFIRMED',
            created_by=self.user,
        )

        response = self.client.post(
            reverse('customers:delete_selected'),
            {'customer_ids': [safe_customer.pk, blocked_customer.pk]},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Customer.objects.filter(pk=safe_customer.pk).exists())
        self.assertTrue(Customer.objects.filter(pk=blocked_customer.pk).exists())
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(messages)
        self.assertTrue(any('با موفقیت حذف شد' in str(message) for message in messages))
        self.assertTrue(any('رزرو فعال' in str(message) for message in messages))
