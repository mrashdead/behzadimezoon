# financial/services/refund_service.py

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from financial.services.transaction_service import TransactionService
from financial.services.reservation_financial_service import ReservationFinancialService
from financial.models import Transaction, FinancialAccount, TransactionCategory
from reservations.models import Reservation


class RefundService:
    @staticmethod
    def _validate_amount(amount):
        if amount is None or amount < 0:
            raise ValidationError('مبلغ بازپرداخت باید عددی صفر یا مثبت باشد.')

    @staticmethod
    @transaction.atomic
    def record_refund(reservation, amount, created_by, account=None, category_name=None,
                      payment_method=None, external_reference=None, note=None,
                      related_transaction=None): # related_transaction might be the original payment

        RefundService._validate_amount(amount)

        # Get default account and category if not provided
        if not account:
            account = FinancialAccount.objects.filter(account_type=FinancialAccount.AccountType.CASH).first()
        if not category_name:
            category_name = 'Refund' # Default category name

        try:
            category = TransactionCategory.objects.get(name=category_name)
        except TransactionCategory.DoesNotExist:
            category = None

        # Validate amount against the reservation's refundable balance
        allowable = ReservationFinancialService.allowable_refund_amount(reservation)
        if amount > allowable:
            raise ValidationError(f'مبلغ بازپرداخت نمی‌تواند بیشتر از مبلغ مجاز ({allowable} تومان) باشد.')

        tx = TransactionService.create_refund(
            reservation=reservation,
            amount=amount,
            created_by=created_by,
            account=account,
            category=category,
            payment_method=payment_method,
            external_reference=external_reference,
            note=note or 'بازپرداخت',
            related_transaction=related_transaction,
            transaction_date=timezone.now(),
        )

        # Update reservation refunded amount and financial fields
        reservation.refunded_amount = (reservation.refunded_amount or 0) + amount
        ReservationFinancialService.update_financial_status(reservation)
        reservation.save()

        return tx
