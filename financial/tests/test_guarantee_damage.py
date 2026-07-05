from django.test import TestCase

from accounts.models import User


class GuaranteeDamageTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', password='pw', is_superuser=True)

    def test_create_guarantee_and_damage(self):
        from customers.models import Customer
        from products.models import Dress
        from reservations.models import Reservation
        from financial.services.guarantee_service import GuaranteeService
        from financial.services.damage_service import DamageService

        import jdatetime

        customer = Customer.objects.create(
            bride_first_name='A', bride_last_name='B', bride_phone='09120000000',
            ceremony_date=jdatetime.date(1402,1,1), how_to_know='test', allow_contact=False
        )
        dress = Dress.objects.create(code='D1', daily_rent_price=100000)

        reservation = Reservation.objects.create(
            customer=customer,
            dress=dress,
            start_date=jdatetime.date(1402,1,1),
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

        g = GuaranteeService.create_guarantee(reservation, customer, tracking_code='G1', guarantee_type='CASH', estimated_value=100000)
        self.assertEqual(g.reservation_id, reservation.pk)
        self.assertEqual(g.customer_id, customer.pk)

        dr = DamageService.record_damage(reservation, customer, 'خراش', amount=20000, description='خراش سطحی', created_by=self.admin)
        self.assertEqual(dr.reservation_id, reservation.pk)
        self.assertTrue(dr.amount == 20000)
