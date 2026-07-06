from django.core.exceptions import ValidationError
from django.db import transaction

from financial.services.transaction_service import TransactionService
from financial.services.reservation_financial_service import ReservationFinancialService


class RefundService:
    @staticmethod
    def _validate_amount(amount):
        if amount is None or amount < 0:
            raise ValidationError('مبلغ بازپرداخت باید عددی صفر یا مثبت باشد.')

    @staticmethod
    def record_refund(reservation, amount, created_by, payment_method=None, external_reference=None, note=None, related_transaction=None):
        RefundService._validate_amount(amount)

        allowable = ReservationFinancialService.allowable_refund_amount(reservation)
        if amount > allowable:
            raise ValidationError('مبلغ بازپرداخت نمی‌تواند بیشتر از مبلغ مجاز باشد.')

        with transaction.atomic():
            tx = TransactionService.create_refund(
                reservation=reservation,
                amount=amount,
                created_by=created_by,
                payment_method=payment_method,
                external_reference=external_reference,
                note=note or 'بازپرداخت',
                related_transaction=related_transaction,
            )
            reservation.refunded_amount = (reservation.refunded_amount or 0) + amount
            ReservationFinancialService.synchronize_snapshot_fields(reservation)
            ReservationFinancialService.capture_financial_snapshot(reservation, 'refund')
            reservation.save()
            return tx
