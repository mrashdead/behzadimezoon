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

    def test_customer_search_matches_multiple_name_tokens(self):
        customer = Customer.objects.create(
            bride_first_name='هانیه',
            bride_last_name='شریفی',
            bride_phone='09121111111',
            ceremony_date=jdatetime.date(1404, 3, 1),
            how_to_know='اینستاگرام',
        )

        response = self.client.get(reverse('customers:list'), {'search': 'هانیه شریفی'})

        self.assertEqual(response.status_code, 200)
        self.assertIn(customer, response.context['customers'])

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

    def test_customer_list_exposes_crm_status_and_last_activity(self):
        crm_only_customer = Customer.objects.create(
            bride_first_name='فقط', bride_last_name='CRM', bride_phone='09120000001',
            ceremony_date=jdatetime.date(1404, 4, 1), how_to_know='اینستاگرام',
        )
        contract_customer = Customer.objects.create(
            bride_first_name='قرارداد', bride_last_name='فعال', bride_phone='09120000002',
            ceremony_date=jdatetime.date(1404, 4, 2), how_to_know='اینستاگرام',
        )
        completed_customer = Customer.objects.create(
            bride_first_name='رزرو', bride_last_name='پایان‌یافته', bride_phone='09120000003',
            ceremony_date=jdatetime.date(1404, 4, 3), how_to_know='اینستاگرام',
        )
        cancelled_customer = Customer.objects.create(
            bride_first_name='رزرو', bride_last_name='لغوشده', bride_phone='09120000004',
            ceremony_date=jdatetime.date(1404, 4, 4), how_to_know='اینستاگرام',
        )
        dress = Dress.objects.create(code='DTEST4', daily_rent_price=150000)

        def create_reservation(customer, status, contract_number=''):
            return Reservation.objects.create(
                customer=customer, dress=dress,
                start_date=jdatetime.date(1404, 4, 1), rental_days=1,
                end_date=jdatetime.date(1404, 4, 1), rent_price=150000,
                deposit_amount=0, final_price=150000, remaining_amount=150000,
                payment_method='CASH', payment_tracking_code='TEST',
                remaining_payment_amount=150000, guarantee1_type='CASH',
                guarantee1_tracking_code='G', status=status,
                contract_number=contract_number, created_by=self.user,
            )

        contract_reservation = create_reservation(contract_customer, 'CONFIRMED', 'CN-CRM-1')
        create_reservation(completed_customer, 'RETURNED')
        create_reservation(cancelled_customer, 'CANCELLED')

        response = self.client.get(reverse('customers:list'), {'sort': 'last_activity'})
        customers = {customer.pk: customer for customer in response.context['customers']}

        self.assertEqual(customers[crm_only_customer.pk].crm_status, 'CRM_ONLY')
        self.assertEqual(customers[contract_customer.pk].crm_status, 'HAS_CONTRACT')
        self.assertEqual(customers[completed_customer.pk].crm_status, 'COMPLETED')
        self.assertEqual(customers[cancelled_customer.pk].crm_status, 'CANCELLED')
        self.assertEqual(customers[contract_customer.pk].last_activity_at, contract_reservation.updated_at)

        filtered_response = self.client.get(
            reverse('customers:list'),
            {'crm_status': 'HAS_CONTRACT'},
        )
        filtered_customers = list(filtered_response.context['customers'])
        self.assertEqual(filtered_customers, [contract_customer])
        self.assertContains(filtered_response, 'دارای قرارداد اجاره')

    def test_customer_status_filter_supports_all_customer_states_and_ajax(self):
        customers_by_status = {}
        for key, status, contract_number in (
            ('CRM_ONLY', None, ''),
            ('HAS_RESERVATION', 'DRAFT', ''),
            ('HAS_CONTRACT', 'CONFIRMED', 'CN-CRM-2'),
            ('COMPLETED', 'RETURNED', ''),
            ('CANCELLED', 'CANCELLED', ''),
        ):
            customer = Customer.objects.create(
                bride_first_name=key,
                bride_last_name='Test',
                bride_phone=f'091200000{len(customers_by_status) + 1:02d}',
                ceremony_date=jdatetime.date(1404, 5, len(customers_by_status) + 1),
                how_to_know='تست',
            )
            customers_by_status[key] = customer

        dress = Dress.objects.create(code='DTEST5', daily_rent_price=150000)
        for key, status in (
            ('HAS_RESERVATION', 'DRAFT'),
            ('HAS_CONTRACT', 'CONFIRMED'),
            ('COMPLETED', 'RETURNED'),
            ('CANCELLED', 'CANCELLED'),
        ):
            Reservation.objects.create(
                customer=customers_by_status[key], dress=dress,
                start_date=jdatetime.date(1404, 5, 1), rental_days=1,
                end_date=jdatetime.date(1404, 5, 1), rent_price=150000,
                deposit_amount=0, final_price=150000, remaining_amount=150000,
                payment_method='CASH', payment_tracking_code=f'TEST-{key}',
                remaining_payment_amount=150000, guarantee1_type='CASH',
                guarantee1_tracking_code='G', status=status,
                contract_number='CN-CRM-2' if key == 'HAS_CONTRACT' else '',
                created_by=self.user,
            )

        for key, expected_customer in customers_by_status.items():
            response = self.client.get(
                reverse('customers:list'),
                {'crm_status': key, 'ajax': '1'},
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(list(response.context['customers']), [expected_customer])
            self.assertContains(response, expected_customer.bride_first_name)

    def test_status_priority_prefers_contract_then_active_then_completed_then_cancelled(self):
        customers = {}
        for name in ('contract', 'active', 'completed', 'cancelled'):
            customers[name] = Customer.objects.create(
                bride_first_name=name,
                bride_last_name='Priority',
                bride_phone=f'091211111{len(customers) + 1:02d}',
                ceremony_date=jdatetime.date(1404, 6, len(customers) + 1),
                how_to_know='تست',
            )
        dress = Dress.objects.create(code='DTEST6', daily_rent_price=150000)

        def add_reservation(customer, status, contract_number=''):
            return Reservation.objects.create(
                customer=customer, dress=dress,
                start_date=jdatetime.date(1404, 6, 1), rental_days=1,
                end_date=jdatetime.date(1404, 6, 1), rent_price=150000,
                deposit_amount=0, final_price=150000, remaining_amount=150000,
                payment_method='CASH', payment_tracking_code='PRIORITY',
                remaining_payment_amount=150000, guarantee1_type='CASH',
                guarantee1_tracking_code='G', status=status,
                contract_number=contract_number, created_by=self.user,
            )

        add_reservation(customers['contract'], 'CONFIRMED', 'CN-PRIORITY')
        add_reservation(customers['contract'], 'RETURNED')
        add_reservation(customers['active'], 'DRAFT')
        add_reservation(customers['active'], 'CANCELLED')
        add_reservation(customers['completed'], 'RETURNED')
        add_reservation(customers['completed'], 'CANCELLED')
        add_reservation(customers['cancelled'], 'CANCELLED')

        response = self.client.get(reverse('customers:list'))
        result = {customer.bride_first_name: customer.crm_status for customer in response.context['customers']}

        self.assertEqual(result['contract'], 'HAS_CONTRACT')
        self.assertEqual(result['active'], 'HAS_RESERVATION')
        self.assertEqual(result['completed'], 'COMPLETED')
        self.assertEqual(result['cancelled'], 'CANCELLED')

    def test_invalid_status_filter_is_ignored_without_hiding_customers(self):
        customer = Customer.objects.create(
            bride_first_name='فیلتر', bride_last_name='نامعتبر',
            bride_phone='09122222222', ceremony_date=jdatetime.date(1404, 6, 10),
            how_to_know='تست',
        )

        response = self.client.get(reverse('customers:list'), {'crm_status': 'UNKNOWN'})

        self.assertEqual(response.status_code, 200)
        self.assertIn(customer, response.context['customers'])
        self.assertEqual(response.context['crm_status'], 'UNKNOWN')

    def test_status_filter_can_be_combined_with_search_and_sorting(self):
        matching_customer = Customer.objects.create(
            bride_first_name='سارا', bride_last_name='فیلترشده',
            bride_phone='09123333333', ceremony_date=jdatetime.date(1404, 6, 11),
            how_to_know='تست',
        )
        other_customer = Customer.objects.create(
            bride_first_name='سارا', bride_last_name='بدون قرارداد',
            bride_phone='09124444444', ceremony_date=jdatetime.date(1404, 6, 12),
            how_to_know='تست',
        )
        dress = Dress.objects.create(code='DTEST7', daily_rent_price=150000)
        Reservation.objects.create(
            customer=matching_customer, dress=dress,
            start_date=jdatetime.date(1404, 6, 1), rental_days=1,
            end_date=jdatetime.date(1404, 6, 1), rent_price=150000,
            deposit_amount=0, final_price=150000, remaining_amount=150000,
            payment_method='CASH', payment_tracking_code='SEARCH',
            remaining_payment_amount=150000, guarantee1_type='CASH',
            guarantee1_tracking_code='G', status='CONFIRMED',
            contract_number='CN-SEARCH', created_by=self.user,
        )

        response = self.client.get(
            reverse('customers:list'),
            {
                'search': 'سارا',
                'crm_status': 'HAS_CONTRACT',
                'sort': 'bride_first_name',
                'order': 'asc',
            },
        )

        self.assertEqual(list(response.context['customers']), [matching_customer])
        self.assertNotIn(other_customer, response.context['customers'])
        self.assertContains(response, 'crm_status=HAS_CONTRACT')


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
