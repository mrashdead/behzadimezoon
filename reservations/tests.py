from django.test import TestCase, Client
from django.urls import reverse
import jdatetime

from accounts.models import User
from customers.models import Customer
from products.models import Dress
from reservations.models import Reservation
from reservations.constants import ReservationStatus


def create_user(username, role, password='password123'):
    extra_fields = {'role': role}
    if role == 'SUPER_ADMIN':
        extra_fields['is_superuser'] = True
        extra_fields['is_staff'] = True
    return User.objects.create_user(username=username, password=password, **extra_fields)


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

    def test_manager_can_edit_reservation_via_ajax(self):
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
        url = reverse('reservations:edit', args=[reservation.pk])
        response = self.client.post(url, {
            'dress': str(self.dress.pk),
            'start_date': '1402/01/02',
            'rental_days': '3',
            'discount_type': '',
            'discount_value': '0',
            'payment_method': 'CASH',
            'payment_tracking_code': 'UPDATED',
            'guarantee1_type': 'CASH',
            'guarantee1_tracking_code': 'G1',
            'guarantee2_type': '',
            'guarantee2_tracking_code': '',
            'deposit_amount': '50000',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {'success': True, 'message': 'رزرو با موفقیت به‌روز شد.'}
        )

        reservation.refresh_from_db()
        self.assertEqual(reservation.payment_tracking_code, 'UPDATED')

    def test_manager_can_mark_delivered_and_returned(self):
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.CONFIRMED,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=100000,
            discount_amount=0,
            final_price=100000,
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

        laundry_url = reverse('reservations:laundry', args=[reservation.pk])
        response = self.client.post(laundry_url)
        self.assertEqual(response.status_code, 302)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, ReservationStatus.LAUNDRY)

        ready_url = reverse('reservations:ready', args=[reservation.pk])
        response = self.client.post(ready_url)
        self.assertEqual(response.status_code, 302)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, ReservationStatus.READY)

    def test_laundry_does_not_block_availability(self):
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.LAUNDRY,
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

        from reservations.services.availability_service import ReservationAvailabilityService

        is_available, end_date = ReservationAvailabilityService.is_dress_available(
            dress=self.dress,
            start_date=reservation.start_date,
            rental_days=reservation.rental_days,
        )

        self.assertTrue(is_available)
        self.assertEqual(end_date, reservation.end_date)

    def test_returned_does_not_block_availability(self):
        Reservation.objects.create(
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
            created_by=self.manager
        )

        from reservations.services.availability_service import ReservationAvailabilityService

        is_available, _ = ReservationAvailabilityService.is_dress_available(
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
        )

        self.assertTrue(is_available)

    def test_get_blocking_statuses_excludes_returned(self):
        from reservations.services.availability_service import ReservationAvailabilityService

        self.assertEqual(
            ReservationAvailabilityService.get_blocking_statuses(),
            [ReservationStatus.CONFIRMED, ReservationStatus.DELIVERED]
        )

    def test_super_admin_can_mark_delivered_and_returned(self):
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.CONFIRMED,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=100000,
            discount_amount=0,
            final_price=100000,
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

    def test_damage_modal_renders_damage_fields(self):
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
            remaining_amount=0,
            payment_method='CASH',
            payment_tracking_code='PAY123',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            created_by=self.manager
        )

        self.client.login(username='manager_user', password='password123')
        response = self.client.get(reverse('reservations:list'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('name="item_damaged"', content)
        self.assertIn('name="damage_amount"', content)
        self.assertIn('name="damage_notes"', content)

    def test_mark_returned_records_damage_information(self):
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.DELIVERED,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=100000,
            discount_amount=0,
            final_price=100000,
            remaining_amount=0,
            payment_method='CASH',
            payment_tracking_code='PAY123',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            created_by=self.manager
        )

        self.client.login(username='manager_user', password='password123')
        returned_url = reverse('reservations:returned', args=[reservation.pk])

        post_data = {
            'item_damaged': 'true',
            'damage_amount': '15000',
            'damage_notes': 'پارگی کوچک در آستین',
        }

        response = self.client.post(returned_url, post_data)
        self.assertEqual(response.status_code, 302)

        reservation.refresh_from_db()
        self.assertEqual(reservation.status, ReservationStatus.RETURNED)
        self.assertTrue(reservation.item_damaged)
        self.assertEqual(reservation.damage_amount, 15000)
        self.assertEqual(reservation.damage_notes, 'پارگی کوچک در آستین')

    def test_mark_returned_without_damage_records_clean_return(self):
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.DELIVERED,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=100000,
            discount_amount=0,
            final_price=100000,
            remaining_amount=0,
            payment_method='CASH',
            payment_tracking_code='PAY123',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            created_by=self.manager
        )

        self.client.login(username='manager_user', password='password123')
        returned_url = reverse('reservations:returned', args=[reservation.pk])

        response = self.client.post(returned_url)
        self.assertEqual(response.status_code, 302)

        reservation.refresh_from_db()
        self.assertEqual(reservation.status, ReservationStatus.RETURNED)
        self.assertFalse(reservation.item_damaged)
        self.assertIsNone(reservation.damage_amount)
        self.assertEqual(reservation.damage_notes, '')

    def test_superuser_can_archive_returned_reservation(self):
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
        archive_url = reverse('reservations:archive_action', args=[reservation.pk])
        response = self.client.post(archive_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {
            "success": True,
            "message": "رزرو با موفقیت آرشیو شد."
        })

        reservation.refresh_from_db()
        self.assertEqual(reservation.status, ReservationStatus.ARCHIVED)
        self.assertIsNotNone(reservation.archived_at)
        self.assertEqual(reservation.archived_by, self.admin)
        self.assertEqual(reservation.previous_status, ReservationStatus.RETURNED)

    def test_non_superuser_cannot_archive(self):
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.RETURNED,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=0,
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
        archive_url = reverse('reservations:archive_action', args=[reservation.pk])
        response = self.client.post(archive_url)
        self.assertEqual(response.status_code, 403)

    def test_archive_legacy_record_with_deposit_above_final_price_still_archives(self):
        legacy_reservation = Reservation(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            end_date=jdatetime.date(1402, 1, 4),
            status=ReservationStatus.RETURNED,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=120000,
            discount_amount=0,
            final_price=100000,
            remaining_amount=0,
            payment_method='CASH',
            payment_tracking_code='PAY123',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            created_by=self.admin
        )
        Reservation.objects.bulk_create([legacy_reservation])

        reservation = Reservation.objects.filter(
            customer=self.customer,
            dress=self.dress,
            status=ReservationStatus.RETURNED
        ).first()

        self.client.login(username='admin_user', password='password123')
        archive_url = reverse('reservations:archive_action', args=[reservation.pk])
        response = self.client.post(archive_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {
            "success": True,
            "message": "رزرو با موفقیت آرشیو شد."
        })

        reservation.refresh_from_db()
        self.assertEqual(reservation.status, ReservationStatus.ARCHIVED)
        self.assertEqual(reservation.previous_status, ReservationStatus.RETURNED)
        self.assertIsNotNone(reservation.archived_at)
        self.assertEqual(reservation.archived_by, self.admin)

    def test_permanent_delete_creates_snapshot_and_nullifies_transaction_reference(self):
        from financial.models import Transaction
        from reservations.models import ReservationArchiveSnapshot

        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.ARCHIVED,
            previous_status=ReservationStatus.CONFIRMED,
            archived_at=jdatetime.datetime(1402, 1, 5, 12, 0, 0),
            archived_by=self.admin,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=50000,
            discount_amount=0,
            final_price=100000,
            remaining_amount=50000,
            payment_method='CASH',
            payment_tracking_code='PAY123',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            created_by=self.admin
        )

        tx = Transaction.objects.create(
            reservation=reservation,
            amount=100000,
            type=Transaction.Type.PAYMENT,
            created_by=self.admin
        )

        self.client.login(username='admin_user', password='password123')
        delete_url = reverse('reservations:delete_permanent', args=[reservation.pk])
        response = self.client.post(delete_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"success": True, "message": "رزرو با موفقیت به‌صورت کامل حذف شد."})

        with self.assertRaises(Reservation.DoesNotExist):
            Reservation.objects.get(pk=reservation.pk)

        tx.refresh_from_db()
        self.assertIsNone(tx.reservation_id)

        snapshot = ReservationArchiveSnapshot.objects.get(original_reservation_id=reservation.pk)
        self.assertEqual(snapshot.data['reservation']['id'], reservation.pk)
        self.assertEqual(snapshot.data['reservation']['previous_status'], reservation.previous_status)
        self.assertEqual(len(snapshot.data['transactions']), 1)
        self.assertEqual(snapshot.data['transactions'][0]['id'], tx.pk)
        self.assertEqual(snapshot.data['transactions'][0]['amount'], tx.amount)

    def test_permanent_delete_rejects_non_archived_reservation(self):
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.CONFIRMED,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=0,
            discount_amount=0,
            final_price=100000,
            remaining_amount=100000,
            payment_method='CASH',
            payment_tracking_code='PAY123',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            created_by=self.admin
        )

        self.client.login(username='admin_user', password='password123')
        delete_url = reverse('reservations:delete_permanent', args=[reservation.pk])
        response = self.client.post(delete_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 403)

        reservation.refresh_from_db()
        self.assertEqual(reservation.status, ReservationStatus.CONFIRMED)

    def test_superuser_can_archive_then_restore_without_conflict(self):
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.RETURNED,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=50000,
            discount_amount=0,
            final_price=100000,
            remaining_amount=50000,
            payment_method='CASH',
            payment_tracking_code='PAY123',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            created_by=self.admin
        )

        self.client.login(username='admin_user', password='password123')
        archive_url = reverse('reservations:archive_action', args=[reservation.pk])
        response = self.client.post(archive_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {
            "success": True,
            "message": "رزرو با موفقیت آرشیو شد."
        })

        reservation.refresh_from_db()
        self.assertEqual(reservation.status, ReservationStatus.ARCHIVED)
        self.assertEqual(reservation.previous_status, ReservationStatus.RETURNED)
        self.assertIsNotNone(reservation.archived_at)
        self.assertEqual(reservation.archived_by, self.admin)

        restore_url = reverse('reservations:restore', args=[reservation.pk])
        response = self.client.post(restore_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {
            "success": True,
            "message": "رزرو با موفقیت بازگردانی شد."
        })

        reservation.refresh_from_db()
        self.assertEqual(reservation.status, ReservationStatus.RETURNED)
        self.assertIsNone(reservation.previous_status)
        self.assertIsNone(reservation.archived_at)
        self.assertIsNone(reservation.archived_by)

    def test_superuser_can_restore_archived_reservation(self):
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.ARCHIVED,
            previous_status=ReservationStatus.CONFIRMED,
            archived_at=jdatetime.datetime(1402, 1, 5, 12, 0, 0),
            archived_by=self.admin,
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
        restore_url = reverse('reservations:restore', args=[reservation.pk])
        response = self.client.post(restore_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {
            "success": True,
            "message": "رزرو با موفقیت بازگردانی شد."
        })

        reservation.refresh_from_db()
        self.assertEqual(reservation.status, ReservationStatus.CONFIRMED)
        self.assertIsNone(reservation.previous_status)
        self.assertIsNone(reservation.archived_at)
        self.assertIsNone(reservation.archived_by)

    def test_non_superuser_cannot_restore_archived_reservation(self):
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.ARCHIVED,
            previous_status=ReservationStatus.CONFIRMED,
            archived_at=jdatetime.datetime(1402, 1, 5, 12, 0, 0),
            archived_by=self.admin,
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
        restore_url = reverse('reservations:restore', args=[reservation.pk])
        response = self.client.post(restore_url)
        self.assertEqual(response.status_code, 403)

    def test_non_superuser_cannot_delete_permanent(self):
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.ARCHIVED,
            previous_status=ReservationStatus.CONFIRMED,
            archived_at=jdatetime.datetime(1402, 1, 5, 12, 0, 0),
            archived_by=self.admin,
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

        self.client.login(username='manager_user', password='password123')
        delete_url = reverse('reservations:delete_permanent', args=[reservation.pk])
        response = self.client.post(delete_url)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Reservation.objects.filter(pk=reservation.pk).exists())

    def test_restore_archived_record_without_previous_status_uses_status_logs(self):
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.ARCHIVED,
            archived_at=jdatetime.datetime(1402, 1, 5, 12, 0, 0),
            archived_by=self.admin,
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
        reservation.status_logs.create(
            old_status=ReservationStatus.CONFIRMED,
            new_status=ReservationStatus.ARCHIVED,
            changed_by=self.admin
        )

        self.client.login(username='admin_user', password='password123')
        restore_url = reverse('reservations:restore', args=[reservation.pk])
        response = self.client.post(restore_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {
            "success": True,
            "message": "رزرو با موفقیت بازگردانی شد."
        })

        reservation.refresh_from_db()
        self.assertEqual(reservation.status, ReservationStatus.CONFIRMED)
        self.assertIsNone(reservation.previous_status)
        self.assertIsNone(reservation.archived_at)
        self.assertIsNone(reservation.archived_by)

    def test_restore_archived_reservation_with_final_previous_status_is_rejected(self):
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.ARCHIVED,
            previous_status=ReservationStatus.RETURNED,
            archived_at=jdatetime.datetime(1402, 1, 5, 12, 0, 0),
            archived_by=self.admin,
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

        # After rule change: final previous statuses should NOT block restore.
        self.client.login(username='admin_user', password='password123')
        restore_url = reverse('reservations:restore', args=[reservation.pk])
        response = self.client.post(restore_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {
            "success": True,
            "message": "رزرو با موفقیت بازگردانی شد."
        })

        reservation.refresh_from_db()
        self.assertEqual(reservation.status, ReservationStatus.RETURNED)
        self.assertIsNone(reservation.previous_status)
        self.assertIsNone(reservation.archived_at)
        self.assertIsNone(reservation.archived_by)

    def test_restore_archived_reservation_when_dress_unavailable_is_rejected(self):
        Reservation.objects.create(
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
            payment_tracking_code='PAY999',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G9',
            created_by=self.manager
        )

        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.ARCHIVED,
            previous_status=ReservationStatus.CONFIRMED,
            archived_at=jdatetime.datetime(1402, 1, 5, 12, 0, 0),
            archived_by=self.admin,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=50000,
            discount_amount=0,
            final_price=50000,
            remaining_amount=0,
            payment_method='CASH',
            payment_tracking_code='PAY1000',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G10',
            created_by=self.admin
        )

        self.client.login(username='admin_user', password='password123')
        restore_url = reverse('reservations:restore', args=[reservation.pk])
        response = self.client.post(restore_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 400)
        self.assertIn("این محصول در بازه زمانی رزرو شده و امکان بازگردانی وجود ندارد.", response.json().get("message", ""))

    def test_duplicate_reservation_request_is_rejected(self):
        self.client.login(username='manager_user', password='password123')

        post_data = {
            'customer': str(self.customer.id),
            'dress': str(self.dress.id),
            'start_date': '1402/01/01',
            'rental_days': '3',
            'payment_method': 'CASH',
            'payment_tracking_code': 'PAY123',
            'guarantee1_type': 'CASH',
            'guarantee1_tracking_code': 'G1',
            'deposit_amount': '50000',
            'discount_amount': '0',
        }

        url = reverse('reservations:create')
        response1 = self.client.post(url, post_data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response1.status_code, 200)
        self.assertJSONEqual(response1.content, {"success": True, "message": "رزرو با موفقیت ثبت شد."})

        response2 = self.client.post(url, post_data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response2.status_code, 200)
        self.assertJSONEqual(response2.content, {
            "success": False,
            "message": "این لباس در این بازه زمانی رزرو شده است."
        })

    def test_overlapping_reservation_is_rejected(self):
        Reservation.objects.create(
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
        create_url = reverse('reservations:create')
        post_data = {
            'customer': str(self.customer.id),
            'dress': str(self.dress.id),
            'start_date': '1402/01/01',
            'rental_days': '3',
            'payment_method': 'CASH',
            'payment_tracking_code': 'PAY456',
            'guarantee1_type': 'CASH',
            'guarantee1_tracking_code': 'G2',
            'deposit_amount': '50000',
            'discount_amount': '0',
        }

        response = self.client.post(create_url, post_data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {
            "success": False,
            "message": "این لباس در این بازه زمانی رزرو شده است."
        })

    def test_seller_cannot_delete_reservation(self):
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

        self.client.login(username='seller_user', password='password123')
        delete_url = reverse('reservations:archive_action', args=[reservation.pk])
        response = self.client.post(delete_url)
        self.assertEqual(response.status_code, 403)


class RemainingPaymentTests(TestCase):
    """Tests for remaining payment at delivery feature"""

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
        cls.manager = create_user('manager_user', 'MANAGER')
        cls.seller = create_user('seller_user', 'SELLER')

    def setUp(self):
        self.client = Client()

    def test_delivery_blocked_when_remaining_unpaid(self):
        """Test that delivery is blocked if remaining_amount > 0 and no payment registered"""
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.CONFIRMED,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=50000,
            discount_amount=0,
            final_price=100000,
            remaining_amount=50000,
            payment_method='CASH',
            payment_tracking_code='PAY123',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            created_by=self.manager
        )

        self.client.login(username='manager_user', password='password123')
        finalize_url = reverse('reservations:finalize_delivery', args=[reservation.pk])

        response = self.client.post(finalize_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 400)

        reservation.refresh_from_db()
        self.assertEqual(reservation.status, ReservationStatus.CONFIRMED)

    def test_delivery_allowed_after_valid_remaining_payment(self):
        """Test that delivery succeeds after registering valid remaining payment"""
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.CONFIRMED,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=50000,
            discount_amount=0,
            final_price=100000,
            remaining_amount=50000,
            payment_method='CASH',
            payment_tracking_code='PAY123',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            created_by=self.manager
        )

        self.client.login(username='manager_user', password='password123')
        finalize_url = reverse('reservations:finalize_delivery', args=[reservation.pk])

        post_data = {
            'remaining_payment_amount': '50000',
            'remaining_payment_method': 'CASH',
            'remaining_payment_tracking_code': 'REC001',
        }

        response = self.client.post(finalize_url, post_data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {
            "success": True,
            "message": "لباس با موفقیت تحویل شد."
        })

        reservation.refresh_from_db()
        self.assertEqual(reservation.status, ReservationStatus.DELIVERED)
        self.assertEqual(reservation.remaining_payment_amount, 50000)
        self.assertEqual(reservation.remaining_payment_method, 'CASH')
        self.assertEqual(reservation.remaining_payment_tracking_code, 'REC001')
        self.assertEqual(reservation.remaining_amount, 0)
        self.assertIsNotNone(reservation.remaining_paid_at)

    def test_invalid_remaining_payment_amount_blocks_delivery(self):
        """Test that incorrect payment amount blocks delivery"""
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.CONFIRMED,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=50000,
            discount_amount=0,
            final_price=100000,
            remaining_amount=50000,
            payment_method='CASH',
            payment_tracking_code='PAY123',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            created_by=self.manager
        )

        self.client.login(username='manager_user', password='password123')
        finalize_url = reverse('reservations:finalize_delivery', args=[reservation.pk])

        post_data = {
            'remaining_payment_amount': '30000',
            'remaining_payment_method': 'CASH',
            'remaining_payment_tracking_code': 'REC001',
        }

        response = self.client.post(finalize_url, post_data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 400)

        reservation.refresh_from_db()
        self.assertEqual(reservation.status, ReservationStatus.CONFIRMED)
        self.assertIsNone(reservation.remaining_paid_at)

    def test_partial_remaining_payment_data_blocks_delivery(self):
        """Test that partial payment data blocks delivery"""
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.CONFIRMED,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=50000,
            discount_amount=0,
            final_price=100000,
            remaining_amount=50000,
            payment_method='CASH',
            payment_tracking_code='PAY123',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            created_by=self.manager
        )

        self.client.login(username='manager_user', password='password123')
        finalize_url = reverse('reservations:finalize_delivery', args=[reservation.pk])

        post_data = {
            'remaining_payment_amount': '50000',
            'remaining_payment_method': 'CASH',
        }

        response = self.client.post(finalize_url, post_data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 400)

        reservation.refresh_from_db()
        self.assertEqual(reservation.status, ReservationStatus.CONFIRMED)

    def test_delivery_without_payment_when_already_settled(self):
        """Test that delivery works without payment form if remaining_amount is 0"""
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.CONFIRMED,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=100000,
            discount_amount=0,
            final_price=100000,
            remaining_amount=0,
            payment_method='CASH',
            payment_tracking_code='PAY123',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            created_by=self.manager
        )

        self.client.login(username='manager_user', password='password123')
        finalize_url = reverse('reservations:finalize_delivery', args=[reservation.pk])

        response = self.client.post(finalize_url, {}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)

        reservation.refresh_from_db()
        self.assertEqual(reservation.status, ReservationStatus.DELIVERED)

    def test_permission_check_on_remaining_payment(self):
        """Test that only authorized users can register remaining payment"""
        reservation = Reservation.objects.create(
            customer=self.customer,
            dress=self.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.CONFIRMED,
            rent_price=self.dress.daily_rent_price,
            deposit_amount=50000,
            discount_amount=0,
            final_price=100000,
            remaining_amount=50000,
            payment_method='CASH',
            payment_tracking_code='PAY123',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            created_by=self.manager
        )

        self.client.login(username='seller_user', password='password123')
        finalize_url = reverse('reservations:finalize_delivery', args=[reservation.pk])

        post_data = {
            'remaining_payment_amount': '50000',
            'remaining_payment_method': 'CASH',
            'remaining_payment_tracking_code': 'REC001',
        }

        response = self.client.post(finalize_url, post_data)
        self.assertEqual(response.status_code, 403)


class SellerDataIsolationTests(TestCase):
    """Test that sellers only see their own reservations."""

    @classmethod
    def setUpTestData(cls):
        cls.customer1 = Customer.objects.create(
            bride_first_name='Bride',
            bride_last_name='One',
            bride_phone='09120000001',
            ceremony_date=jdatetime.date(1402, 1, 1),
            how_to_know='test',
            allow_contact=True
        )
        cls.customer2 = Customer.objects.create(
            bride_first_name='Bride',
            bride_last_name='Two',
            bride_phone='09120000002',
            ceremony_date=jdatetime.date(1402, 1, 1),
            how_to_know='test',
            allow_contact=True
        )
        cls.dress = Dress.objects.create(code='D001', daily_rent_price=100000)

        cls.seller1 = create_user('seller1', 'SELLER')
        cls.seller2 = create_user('seller2', 'SELLER')
        cls.manager = create_user('manager', 'MANAGER')

        # Seller1 creates a reservation
        cls.res_seller1 = Reservation.objects.create(
            customer=cls.customer1,
            dress=cls.dress,
            start_date=jdatetime.date(1402, 1, 1),
            rental_days=3,
            status=ReservationStatus.CONFIRMED,
            rent_price=100000,
            deposit_amount=50000,
            discount_amount=0,
            final_price=100000,
            remaining_amount=50000,
            payment_method='CASH',
            payment_tracking_code='PAY001',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G1',
            created_by=cls.seller1
        )

        # Seller2 creates a different reservation
        cls.res_seller2 = Reservation.objects.create(
            customer=cls.customer2,
            dress=cls.dress,
            start_date=jdatetime.date(1402, 5, 1),
            rental_days=3,
            status=ReservationStatus.CONFIRMED,
            rent_price=100000,
            deposit_amount=50000,
            discount_amount=0,
            final_price=100000,
            remaining_amount=50000,
            payment_method='CASH',
            payment_tracking_code='PAY002',
            guarantee1_type='CASH',
            guarantee1_tracking_code='G2',
            created_by=cls.seller2
        )

    def setUp(self):
        self.client = Client()

    # C1: Seller sees only their own reservations in list
    def test_seller_sees_only_own_reservations_in_list(self):
        self.client.login(username='seller1', password='password123')
        response = self.client.get(reverse('reservations:list'))
        self.assertEqual(response.status_code, 200)

        reservations = response.context['reservations']
        reservation_ids = [r.id for r in reservations]

        self.assertIn(self.res_seller1.id, reservation_ids)
        self.assertNotIn(self.res_seller2.id, reservation_ids)

    # C2: Seller does not see other sellers' reservations in list
    def test_seller_does_not_see_other_sellers_in_list(self):
        self.client.login(username='seller2', password='password123')
        response = self.client.get(reverse('reservations:list'))

        reservations = response.context['reservations']
        reservation_ids = [r.id for r in reservations]

        self.assertIn(self.res_seller2.id, reservation_ids)
        self.assertNotIn(self.res_seller1.id, reservation_ids)

    # C3: Seller cannot access another seller's reservation detail
    def test_seller_cannot_access_other_seller_reservation_detail(self):
        self.client.login(username='seller1', password='password123')
        detail_url = reverse('reservations:detail', args=[self.res_seller2.pk])
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 403)

    # C4: Seller can access own reservation detail
    def test_seller_can_access_own_reservation_detail(self):
        self.client.login(username='seller1', password='password123')
        detail_url = reverse('reservations:detail', args=[self.res_seller1.pk])
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)

    # C5: Manager sees all reservations
    def test_manager_sees_all_reservations(self):
        self.client.login(username='manager', password='password123')
        response = self.client.get(reverse('reservations:list'))

        reservations = response.context['reservations']
        reservation_ids = [r.id for r in reservations]

        self.assertIn(self.res_seller1.id, reservation_ids)
        self.assertIn(self.res_seller2.id, reservation_ids)

