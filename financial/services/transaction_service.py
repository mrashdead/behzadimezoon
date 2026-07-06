from django.db import transaction
from django.db.models import Sum, Case, When, Value, BigIntegerField
from django.utils import timezone

from financial.models import Transaction
from reservations.constants import ReservationStatus


class TransactionService:
    @staticmethod
    def create(
        reservation,
        transaction_type,
        amount,
        created_by,
        payment_method=None,
        external_reference=None,
        note=None,
        related_transaction=None,
        transaction_date=None,
    ):
        if amount is None or amount < 0:
            raise ValueError("مبلغ تراکنش باید عددی صفر یا مثبت باشد.")

        transaction_date = transaction_date or timezone.now()

        tx = Transaction.objects.create(
            reservation=reservation,
            type=transaction_type,
            amount=amount,
            transaction_date=transaction_date,
            payment_method=payment_method,
            external_reference=external_reference,
            note=note or "",
            related_transaction=related_transaction,
            created_by=created_by,
        )
        return tx

    @staticmethod
    def create_deposit(reservation, amount, created_by, payment_method=None, external_reference=None, note=None, transaction_date=None):
        return TransactionService.create(
            reservation=reservation,
            transaction_type=Transaction.Type.DEPOSIT,
            amount=amount,
            created_by=created_by,
            payment_method=payment_method,
            external_reference=external_reference,
            note=note,
            transaction_date=transaction_date,
        )

    @staticmethod
    def create_final_payment(reservation, amount, created_by, payment_method=None, external_reference=None, note=None, transaction_date=None):
        return TransactionService.create(
            reservation=reservation,
            transaction_type=Transaction.Type.FINAL_PAYMENT,
            amount=amount,
            created_by=created_by,
            payment_method=payment_method,
            external_reference=external_reference,
            note=note,
            transaction_date=transaction_date,
        )

    @staticmethod
    def create_refund(reservation, amount, created_by, payment_method=None, external_reference=None, note=None, related_transaction=None, transaction_date=None):
        return TransactionService.create(
            reservation=reservation,
            transaction_type=Transaction.Type.REFUND,
            amount=amount,
            created_by=created_by,
            payment_method=payment_method,
            external_reference=external_reference,
            note=note,
            related_transaction=related_transaction,
            transaction_date=transaction_date,
        )

    @staticmethod
    def create_damage_charge(reservation, amount, created_by, payment_method=None, external_reference=None, note=None, related_transaction=None, transaction_date=None):
        return TransactionService.create(
            reservation=reservation,
            transaction_type=Transaction.Type.DAMAGE_CHARGE,
            amount=amount,
            created_by=created_by,
            payment_method=payment_method,
            external_reference=external_reference,
            note=note,
            related_transaction=related_transaction,
            transaction_date=transaction_date,
        )

    @staticmethod
    def create_damage_payment(reservation, amount, created_by, payment_method=None, external_reference=None, note=None, related_transaction=None, transaction_date=None):
        return TransactionService.create(
            reservation=reservation,
            transaction_type=Transaction.Type.DAMAGE_PAYMENT,
            amount=amount,
            created_by=created_by,
            payment_method=payment_method,
            external_reference=external_reference,
            note=note,
            related_transaction=related_transaction,
            transaction_date=transaction_date,
        )

    @staticmethod
    def create_cancellation_fee(reservation, amount, created_by, note=None, transaction_date=None):
        return TransactionService.create(
            reservation=reservation,
            transaction_type=Transaction.Type.CANCELLATION_FEE,
            amount=amount,
            created_by=created_by,
            note=note,
            transaction_date=transaction_date,
        )

    @staticmethod
    def aggregate_reservation_totals(reservation):
        return reservation.transactions.aggregate(
            total_deposit=Sum(Case(When(type=Transaction.Type.DEPOSIT, then='amount'), default=Value(0), output_field=BigIntegerField())),
            total_final_payment=Sum(Case(When(type=Transaction.Type.FINAL_PAYMENT, then='amount'), default=Value(0), output_field=BigIntegerField())),
            total_damage_payment=Sum(Case(When(type=Transaction.Type.DAMAGE_PAYMENT, then='amount'), default=Value(0), output_field=BigIntegerField())),
            total_refund=Sum(Case(When(type=Transaction.Type.REFUND, then='amount'), default=Value(0), output_field=BigIntegerField())),
            total_damage_charge=Sum(Case(When(type=Transaction.Type.DAMAGE_CHARGE, then='amount'), default=Value(0), output_field=BigIntegerField())),
            total_discount=Sum(Case(When(type=Transaction.Type.DISCOUNT, then='amount'), default=Value(0), output_field=BigIntegerField())),
            total_cancellation_fee=Sum(Case(When(type=Transaction.Type.CANCELLATION_FEE, then='amount'), default=Value(0), output_field=BigIntegerField())),
            total_adjustment=Sum(Case(When(type=Transaction.Type.ADJUSTMENT, then='amount'), default=Value(0), output_field=BigIntegerField())),
        )

    @staticmethod
    def reservation_cash_inflow(reservation):
        totals = TransactionService.aggregate_reservation_totals(reservation)
        return (
            (totals.get('total_deposit') or 0)
            + (totals.get('total_final_payment') or 0)
            + (totals.get('total_damage_payment') or 0)
            - (totals.get('total_refund') or 0)
        )

    @staticmethod
    def reservation_accrual_revenue(reservation):
        totals = TransactionService.aggregate_reservation_totals(reservation)
        gross = reservation.final_price or 0
        discount = totals.get('total_discount') or 0
        cancellation = totals.get('total_cancellation_fee') or 0
        damage_charge = totals.get('total_damage_charge') or 0
        return gross - discount + cancellation + damage_charge

    @staticmethod
    def reservation_open_receivable(reservation):
        totals = TransactionService.aggregate_reservation_totals(reservation)
        receivable = (
            (totals.get('total_damage_charge') or 0)
            + (totals.get('total_cancellation_fee') or 0)
        )
        collected = (totals.get('total_damage_payment') or 0)
        return receivable - collected
