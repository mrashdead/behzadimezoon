from django.db.models import Sum, Case, When, Value, BigIntegerField

from financial.models import Transaction
from reservations.models import Reservation


class ReconciliationService:
    @staticmethod
    def _action_for_difference(cash_difference):
        if cash_difference > 0:
            return {
                'suggested_action': 'refund',
                'action_label': 'ثبت بازپرداخت',
                'transaction_type': Transaction.Type.REFUND,
            }
        if cash_difference < 0:
            return {
                'suggested_action': 'adjustment',
                'action_label': 'ثبت تعدیل',
                'transaction_type': Transaction.Type.ADJUSTMENT,
            }
        return {
            'suggested_action': 'none',
            'action_label': 'بدون اختلاف',
            'transaction_type': None,
        }

    @staticmethod
    def reservation_discrepancies(reservation):
        transactions = reservation.transactions.aggregate(
            total_deposit=Sum(Case(When(type=Transaction.Type.DEPOSIT, then='amount'), default=Value(0), output_field=BigIntegerField())),
            total_final_payment=Sum(Case(When(type=Transaction.Type.FINAL_PAYMENT, then='amount'), default=Value(0), output_field=BigIntegerField())),
            total_refund=Sum(Case(When(type=Transaction.Type.REFUND, then='amount'), default=Value(0), output_field=BigIntegerField())),
            total_damage_charge=Sum(Case(When(type=Transaction.Type.DAMAGE_CHARGE, then='amount'), default=Value(0), output_field=BigIntegerField())),
            total_damage_payment=Sum(Case(When(type=Transaction.Type.DAMAGE_PAYMENT, then='amount'), default=Value(0), output_field=BigIntegerField())),
        )

        expected_cash = (transactions.get('total_deposit') or 0) + (transactions.get('total_final_payment') or 0) + (transactions.get('total_damage_payment') or 0) - (transactions.get('total_refund') or 0)
        reservation_cash = (reservation.deposit_amount or 0) + (reservation.remaining_payment_amount or 0) - (reservation.refunded_amount or 0)
        cash_difference = expected_cash - reservation_cash
        action = ReconciliationService._action_for_difference(cash_difference)

        return {
            'reservation_id': reservation.pk,
            'expected_cash': expected_cash,
            'reservation_cash': reservation_cash,
            'cash_difference': cash_difference,
            'open_receivable': (transactions.get('total_damage_charge') or 0) - (transactions.get('total_damage_payment') or 0),
            'has_discrepancy': cash_difference != 0,
            'suggested_action': action['suggested_action'],
            'action_label': action['action_label'],
            'transaction_type': action['transaction_type'],
        }

    @staticmethod
    def get_open_problem_reservations():
        reservations = Reservation.objects.all()
        return [
            discrepancy
            for reservation in reservations
            for discrepancy in [ReconciliationService.reservation_discrepancies(reservation)]
            if discrepancy['has_discrepancy']
        ]
