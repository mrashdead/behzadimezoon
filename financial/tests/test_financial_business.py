from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

import jdatetime

from accounts.models import User
from customers.models import Customer
from financial.models import CancellationRecord, DamageRecord, Guarantee, Transaction
from financial.services import (
    CancellationService,
    DamageService,
    GuaranteeService,
    PaymentService,
    RefundService,
    ReservationFinancialService,
)
from financial.services.reconciliation_service import ReconciliationService
from financial.services.transaction_service import TransactionService
from products.models import Dress
from reservations.constants import PaymentMethod, ReservationStatus
from reservations.models import Reservation


class FinancialBusinessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user('admin', password='pw', is_superuser=True, role='SUPER_ADMIN')
        cls.seller1 = User.objects.create_user('seller1', password='pw', role='SELLER')
        cls.seller2 = User.objects.create_user('seller2', password='pw', role='SELLER')

        cls.customer = Customer.objects.create(
            bride_first_name='A',
            bride_last_name='B',
            bride_phone='09120000000',
            ceremony_date=jdatetime.date(1402, 1, 1),
            how_to_know='test',
            allow_contact=True,
        )
        cls.dress = Dress.objects.create(code='D001', daily_rent_price=100000)

    def create_reservation(self, **kwargs):
        defaults = {
            'customer': self.customer,
            'dress': self.dress,
            'start_date': jdatetime.date(1402, 1, 1),
            'rental_days': 3,
            'status': ReservationStatus.CONFIRMED,
            'rent_price': self.dress.daily_rent_price,
            'deposit_amount': 0,
            'discount_type': 'NONE',
            'discount_value': 0,
            'discount_amount': 0,
            'final_price': 100000,
            'remaining_amount': 100000,
            'remaining_payment_amount': 0,
            'refunded_amount': 0,
            'payment_method': 'CASH',
            'payment_tracking_code': 'TXN1',
            'guarantee1_type': 'CASH',
            'guarantee1_tracking_code': 'G1',
            'created_by': self.seller1,
        }
        defaults.update(kwargs)
        return Reservation.objects.create(**defaults)

    def test_deposit_and_final_settlement_updates_reservation_balance(self):
        reservation = self.create_reservation(deposit_amount=0, remaining_payment_amount=0, final_price=100000, remaining_amount=100000)

        PaymentService.record_deposit(
            reservation=reservation,
            amount=50000,
            created_by=self.admin,
            payment_method=PaymentMethod.CASH,
            note='Initial deposit',
        )
        reservation.refresh_from_db()
        self.assertEqual(reservation.deposit_amount, 50000)
        self.assertEqual(reservation.financial_snapshot['event_type'], 'deposit')
        self.assertEqual(reservation.financial_snapshot['deposit_amount'], 50000)

        PaymentService.record_balance_payment(
            reservation=reservation,
            amount=50000,
            created_by=self.admin,
            payment_method=PaymentMethod.CASH,
            note='Final settlement',
        )
        reservation.refresh_from_db()

        self.assertEqual(reservation.remaining_payment_amount, 50000)
        self.assertEqual(reservation.remaining_amount, 0)
        self.assertEqual(reservation.net_cash_inflow, 100000)
        self.assertEqual(reservation.financial_snapshot['event_type'], 'balance_payment')
        self.assertEqual(TransactionService.reservation_cash_inflow(reservation), 100000)

    def test_discount_calculation_and_invalid_discount_rejected(self):
        reservation = self.create_reservation()
        reservation.discount_amount = 20000
        ReservationFinancialService.calculate_final_price(reservation)
        self.assertEqual(reservation.final_price, 80000)

        reservation.discount_amount = 120000
        with self.assertRaises(ValidationError):
            ReservationFinancialService.validate_discount(reservation)

        reservation.discount_amount = -100
        with self.assertRaises(ValidationError):
            ReservationFinancialService.validate_discount(reservation)

    def test_multiple_payments_and_refund_validation(self):
        reservation = self.create_reservation(deposit_amount=0, remaining_payment_amount=0, final_price=100000, remaining_amount=100000)

        PaymentService.record_deposit(
            reservation=reservation,
            amount=20000,
            created_by=self.admin,
            payment_method=PaymentMethod.CASH,
            note='Deposit',
        )
        PaymentService.record_balance_payment(
            reservation=reservation,
            amount=50000,
            created_by=self.admin,
            payment_method=PaymentMethod.CASH,
            note='First payment',
        )
        PaymentService.record_balance_payment(
            reservation=reservation,
            amount=40000,
            created_by=self.admin,
            payment_method=PaymentMethod.CASH,
            note='Overpayment',
        )
        reservation.refresh_from_db()

        self.assertEqual(reservation.remaining_amount, 0)
        self.assertEqual(reservation.remaining_payment_amount, 90000)
        self.assertEqual(ReservationFinancialService.allowable_refund_amount(reservation), 10000)

        with self.assertRaises(ValidationError):
            RefundService.record_refund(
                reservation=reservation,
                amount=20000,
                created_by=self.admin,
                payment_method=PaymentMethod.CASH,
                note='Too much refund',
            )

        refund_tx = RefundService.record_refund(
            reservation=reservation,
            amount=10000,
            created_by=self.admin,
            payment_method=PaymentMethod.CASH,
            note='Refund overpayment',
        )
        self.assertEqual(refund_tx.type, Transaction.Type.REFUND)
        reservation.refresh_from_db()
        self.assertEqual(reservation.refunded_amount, 10000)

    def test_cancellation_with_full_refund_generates_refund_transaction(self):
        reservation = self.create_reservation(deposit_amount=0, remaining_payment_amount=0)
        PaymentService.record_deposit(
            reservation=reservation,
            amount=100000,
            created_by=self.admin,
            payment_method=PaymentMethod.CASH,
            note='Deposit for cancellation',
        )
        PaymentService.record_balance_payment(
            reservation=reservation,
            amount=10000,
            created_by=self.admin,
            payment_method=PaymentMethod.CASH,
            note='Overpayment before cancellation',
        )
        reservation.refresh_from_db()

        cancellation = CancellationService.create_cancellation_record(
            reservation=reservation,
            reason='Customer cancelled',
            created_by=self.admin,
            refund_amount=10000,
            penalty_amount=0,
            payment_method=PaymentMethod.CASH,
            note='Full refund',
        )

        self.assertIsInstance(cancellation, CancellationRecord)
        self.assertEqual(cancellation.refund_amount, 10000)
        self.assertEqual(cancellation.penalty_amount, 0)
        self.assertIsNotNone(cancellation.related_transaction)
        self.assertEqual(cancellation.related_transaction.type, Transaction.Type.REFUND)

    def test_cancellation_partial_refund_and_penalty_creates_both_transactions(self):
        reservation = self.create_reservation(deposit_amount=0, remaining_payment_amount=0)
        PaymentService.record_deposit(
            reservation=reservation,
            amount=100000,
            created_by=self.admin,
            payment_method=PaymentMethod.CASH,
            note='Deposit for partial cancellation',
        )
        PaymentService.record_balance_payment(
            reservation=reservation,
            amount=10000,
            created_by=self.admin,
            payment_method=PaymentMethod.CASH,
            note='Overpayment before partial cancellation',
        )
        reservation.refresh_from_db()

        cancellation = CancellationService.create_cancellation_record(
            reservation=reservation,
            reason='Partial refund on cancellation',
            created_by=self.admin,
            refund_amount=5000,
            penalty_amount=2000,
            payment_method=PaymentMethod.CASH,
            note='Partial refund',
        )

        self.assertEqual(cancellation.refund_amount, 5000)
        self.assertEqual(cancellation.penalty_amount, 2000)
        self.assertEqual(Transaction.objects.filter(type=Transaction.Type.REFUND, reservation=reservation).count(), 1)
        self.assertEqual(Transaction.objects.filter(type=Transaction.Type.CANCELLATION_FEE, reservation=reservation).count(), 1)

    def test_damage_registration_and_payment_links_consistently(self):
        reservation = self.create_reservation(deposit_amount=5000, remaining_payment_amount=0, final_price=5000, remaining_amount=0)

        damage_record = DamageService.record_damage(
            reservation=reservation,
            customer=self.customer,
            damage_type='Tear',
            amount=20000,
            description='Minor tear',
            created_by=self.admin,
            payment_method=PaymentMethod.CASH,
            external_reference='D1',
        )
        self.assertIsInstance(damage_record, DamageRecord)
        self.assertFalse(damage_record.collected)
        self.assertEqual(damage_record.related_transaction.type, Transaction.Type.DAMAGE_CHARGE)
        self.assertEqual(damage_record.related_transaction.reservation_id, reservation.pk)

        payment_tx = DamageService.record_damage_payment(
            damage_record=damage_record,
            amount=20000,
            created_by=self.admin,
            payment_method=PaymentMethod.CASH,
            external_reference='D1PAY',
            note='Damage payment',
        )
        damage_record.refresh_from_db()
        self.assertTrue(damage_record.collected)
        self.assertEqual(payment_tx.type, Transaction.Type.DAMAGE_PAYMENT)
        self.assertEqual(damage_record.related_transaction_id, payment_tx.pk)

    def test_guarantee_registration_and_return_flow(self):
        reservation = self.create_reservation()
        guarantee = GuaranteeService.create_guarantee(
            reservation=reservation,
            customer=self.customer,
            tracking_code='G-100',
            guarantee_type='CASH',
            estimated_value=50000,
            notes='Guarantee created',
        )
        self.assertIsInstance(guarantee, Guarantee)
        self.assertEqual(guarantee.status, Guarantee.RECEIVED)

        duplicate = GuaranteeService.create_guarantee(
            reservation=reservation,
            customer=self.customer,
            tracking_code='G-100',
            guarantee_type='CASH',
        )
        self.assertEqual(Guarantee.objects.filter(tracking_code='G-100').count(), 2)

        self.client.login(username='admin', password='pw')
        response = self.client.post(reverse('financial:return_guarantee', args=[guarantee.pk]))
        self.assertEqual(response.status_code, 200)
        guarantee.refresh_from_db()
        self.assertEqual(guarantee.status, Guarantee.RETURNED)

    def test_reconciliation_detects_mismatch_between_snapshot_and_ledger(self):
        reservation = self.create_reservation(deposit_amount=50000, remaining_payment_amount=100000, final_price=100000, remaining_amount=0)
        TransactionService.create_deposit(
            reservation=reservation,
            amount=50000,
            created_by=self.admin,
            payment_method=PaymentMethod.CASH,
            note='Deposit',
        )
        TransactionService.create_final_payment(
            reservation=reservation,
            amount=50000,
            created_by=self.admin,
            payment_method=PaymentMethod.CASH,
            note='Partial settlement',
        )

        discrepancy = ReconciliationService.reservation_discrepancies(reservation)
        self.assertTrue(discrepancy['has_discrepancy'])
        self.assertLess(discrepancy['cash_difference'], 0)
        self.assertEqual(discrepancy['suggested_action'], 'adjustment')
        self.assertEqual(discrepancy['expected_cash'], 100000)

    def test_adjustment_transaction_resolves_reconciliation_discrepancy(self):
        reservation = self.create_reservation(deposit_amount=50000, remaining_payment_amount=100000, final_price=100000, remaining_amount=0)
        TransactionService.create_deposit(
            reservation=reservation,
            amount=50000,
            created_by=self.admin,
            payment_method=PaymentMethod.CASH,
            note='Deposit',
        )
        TransactionService.create_final_payment(
            reservation=reservation,
            amount=50000,
            created_by=self.admin,
            payment_method=PaymentMethod.CASH,
            note='Final payment',
        )

        discrepancy = ReconciliationService.reservation_discrepancies(reservation)
        self.assertTrue(discrepancy['has_discrepancy'])
        self.assertEqual(discrepancy['suggested_action'], 'adjustment')

        TransactionService.create(
            reservation=reservation,
            transaction_type=Transaction.Type.ADJUSTMENT,
            amount=50000,
            created_by=self.admin,
            note='Reconciliation adjustment',
        )

        discrepancy_after = ReconciliationService.reservation_discrepancies(reservation)
        self.assertFalse(discrepancy_after['has_discrepancy'])
        self.assertEqual(discrepancy_after['cash_difference'], 0)

    def test_financial_snapshot_updates_on_each_transaction(self):
        reservation = self.create_reservation(deposit_amount=0, remaining_payment_amount=0, final_price=100000, remaining_amount=100000)

        PaymentService.record_deposit(
            reservation=reservation,
            amount=40000,
            created_by=self.admin,
            payment_method=PaymentMethod.CASH,
            note='Deposit snapshot',
        )
        reservation.refresh_from_db()
        self.assertEqual(reservation.financial_snapshot['event_type'], 'deposit')
        self.assertEqual(reservation.total_cash_collected_snapshot, 40000)

        PaymentService.record_balance_payment(
            reservation=reservation,
            amount=60000,
            created_by=self.admin,
            payment_method=PaymentMethod.CASH,
            note='Payment snapshot',
        )
        reservation.refresh_from_db()
        self.assertEqual(reservation.financial_snapshot['event_type'], 'balance_payment')

        RefundService.record_refund(
            reservation=reservation,
            amount=0,
            created_by=self.admin,
            payment_method=PaymentMethod.CASH,
            note='No refund',
        )
        reservation.refresh_from_db()
        self.assertIn('final_price', reservation.financial_snapshot)

    def test_operational_views_reject_invalid_inputs_and_access(self):
        reservation = self.create_reservation(created_by=self.seller1)
        self.client.login(username='seller2', password='pw')

        response = self.client.post(reverse('financial:add_guarantee', args=[reservation.pk]), {
            'tracking_code': 'X1',
            'guarantee_type': 'CASH',
        })
        self.assertEqual(response.status_code, 403)

        self.client.login(username='admin', password='pw')
        response = self.client.post(reverse('financial:create_transaction', args=[reservation.pk]), {
            'type': 'DEPOSIT',
            'amount': -100,
            'payment_method': PaymentMethod.CASH,
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('amount', response.json()['error'])

        response = self.client.post(reverse('financial:add_damage', args=[reservation.pk]), {
            'damage_type': 'Leak',
            'amount': -5000,
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('amount', response.json()['error'])

        response = self.client.post(reverse('financial:cancel_reservation', args=[reservation.pk]), {
            'refund_amount': -1000,
            'penalty_amount': 0,
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('refund_amount', response.json()['error'])

    def test_reservation_financial_view_renders_summary(self):
        reservation = self.create_reservation()
        self.client.login(username='admin', password='pw')
        response = self.client.get(reverse('financial:reservation_financial', args=[reservation.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'بهای پایه')
