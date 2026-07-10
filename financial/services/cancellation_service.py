# financial/services/cancellation_service.py

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from financial.services.transaction_service import TransactionService
from financial.services.reservation_financial_service import ReservationFinancialService
from financial.models import CancellationRecord, Transaction, FinancialAccount, TransactionCategory
from reservations.constants import PaymentMethod
from reservations.models import Reservation


class CancellationService:
    @staticmethod
    def _validate_amounts(refund_amount, penalty_amount):
        if refund_amount < 0:
            raise ValidationError('مبلغ بازپرداخت نمی‌تواند منفی باشد.')
        if penalty_amount < 0:
            raise ValidationError('مبلغ جریمه نمی‌تواند منفی باشد.')

    @staticmethod
    @transaction.atomic
    def create_cancellation_record(reservation, reason, created_by,
                                   refund_amount=0, penalty_amount=0,
                                   payment_method=None, external_reference=None,
                                   notes=None, note=None, account=None, refund_category_name=None, penalty_category_name=None):

        CancellationService._validate_amounts(refund_amount, penalty_amount)

        # Get default account and categories if not provided
        if not account:
            account = FinancialAccount.objects.filter(account_type=FinancialAccount.AccountType.CASH).first()
        if not refund_category_name:
            refund_category_name = 'Refund' # Default category name
        if not penalty_category_name:
            penalty_category_name = 'Cancellation Fee' # Default category name

        try:
            refund_category = TransactionCategory.objects.get(name=refund_category_name)
        except TransactionCategory.DoesNotExist:
            refund_category = None # Handle case where category doesn't exist

        try:
            penalty_category = TransactionCategory.objects.get(name=penalty_category_name)
        except TransactionCategory.DoesNotExist:
            penalty_category = None

        # Validate refund amount against allowable amount
        allowable_refund = ReservationFinancialService.allowable_refund_amount(reservation)
        if refund_amount > allowable_refund:
            raise ValidationError('مبلغ بازپرداخت نمی‌تواند بیشتر از مقدار مجاز باشد.')

        # Create CancellationRecord instance
        cancellation = CancellationRecord.objects.create(
            reservation=reservation,
            reason=reason,
            cancelled_by=created_by,
            deposit_at_cancel=reservation.deposit_amount, # Snapshot
            refund_amount=refund_amount,
            refund_method=payment_method,
            refund_posted_at=timezone.now() if refund_amount > 0 else None,
            refund_status=CancellationRecord.REFUND_POSTED if refund_amount > 0 else CancellationRecord.REFUND_REQUESTED,
            penalty_amount=penalty_amount,
            approved_by=created_by, # Assuming creator is also approver initially
            approval_date=timezone.now(),
            notes=notes or note or '',
        )

        # Sync the penalty and refund values onto the reservation itself so the UI can display them.
        if penalty_amount > 0:
            reservation.cancellation_fee = penalty_amount
        elif penalty_amount == 0:
            reservation.cancellation_fee = 0

        if refund_amount > 0:
            reservation.refunded_amount = (reservation.refunded_amount or 0) + refund_amount

        # Create associated transactions if amounts are positive
        if refund_amount > 0 and account: # Only create TX if account exists
            tx_refund = TransactionService.create_refund(
                reservation=reservation,
                amount=refund_amount,
                created_by=created_by,
                account=account,
                category=refund_category,
                payment_method=payment_method,
                external_reference=external_reference,
                note='بازپرداخت وجه رزرو لغو شده',
                transaction_date=timezone.now()
            )
            cancellation.related_transaction = tx_refund
            # save() is handled within create_cancellation_record if needed

        if penalty_amount > 0 and account: # Only create TX if account exists
            TransactionService.create_cancellation_fee(
                reservation=reservation,
                amount=penalty_amount,
                created_by=created_by,
                account=account,
                category=penalty_category,
                note='جریمه لغو رزرو',
                transaction_date=timezone.now()
            )

        # Update reservation's financial status and save
        ReservationFinancialService.update_financial_status(reservation)
        reservation.save()

        return cancellation

    @staticmethod
    def summary(cancellation_record):
        return {
            'reservation_id': cancellation_record.reservation_id,
            'refund_amount': cancellation_record.refund_amount,
            'penalty_amount': cancellation_record.penalty_amount,
            'deposit_at_cancel': cancellation_record.deposit_at_cancel,
            'refund_status': cancellation_record.refund_status,
        }
