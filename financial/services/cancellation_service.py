from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from financial.models import CancellationRecord
from financial.services.transaction_service import TransactionService
from financial.services.reservation_financial_service import ReservationFinancialService


class CancellationService:
    @staticmethod
    def create_cancellation_record(reservation, reason, created_by, refund_amount=0, penalty_amount=0, payment_method=None, external_reference=None, note=None):
        if refund_amount < 0:
            raise ValidationError('مبلغ بازپرداخت نمی‌تواند منفی باشد.')
        if penalty_amount < 0:
            raise ValidationError('مبلغ جریمه نمی‌تواند منفی باشد.')

        allowable_refund = ReservationFinancialService.allowable_refund_amount(reservation)
        if refund_amount > allowable_refund:
            raise ValidationError('مبلغ بازپرداخت نمی‌تواند بیشتر از مقدار مجاز باشد.')

        with transaction.atomic():
            cancellation = CancellationRecord.objects.create(
                reservation=reservation,
                reason=reason,
                cancelled_by=created_by,
                deposit_at_cancel=reservation.deposit_amount,
                refund_amount=refund_amount,
                refund_method=payment_method,
                refund_posted_at=timezone.now() if refund_amount else None,
                refund_status=CancellationRecord.REFUND_POSTED if refund_amount else CancellationRecord.REFUND_REQUESTED,
                penalty_amount=penalty_amount,
                approved_by=created_by,
                approval_date=timezone.now(),
                approval_notes=note or '',
                notes=note or '',
            )

            if refund_amount > 0:
                tx = TransactionService.create_refund(
                    reservation=reservation,
                    amount=refund_amount,
                    created_by=created_by,
                    payment_method=payment_method,
                    external_reference=external_reference,
                    note=note or 'بازپرداخت لغو رزرو',
                )
                cancellation.related_transaction = tx
                cancellation.save()

            if penalty_amount > 0:
                TransactionService.create_cancellation_fee(
                    reservation=reservation,
                    amount=penalty_amount,
                    created_by=created_by,
                    note=note or 'جریمه لغو رزرو',
                )

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
